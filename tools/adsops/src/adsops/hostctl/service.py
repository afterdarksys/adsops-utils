"""hostctl service layer — CRUD operations returning HostRecord protos."""
import asyncio
import datetime
from typing import Optional

import asyncssh
from google.protobuf import timestamp_pb2
from google.protobuf.json_format import ParseDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from adsops.hostctl.db import get_session
from adsops.hostctl.models import Resource
from adsops.v1 import host_pb2

VALID_TYPES = ["server", "container", "vm", "k8s-node", "load-balancer", "database"]
VALID_PROVIDERS = ["oci", "gcp", "onprem", "other"]
VALID_ENVIRONMENTS = ["production", "staging", "development"]
VALID_STATUSES = ["active", "inactive", "build", "blackout", "maintenance", "decommissioned"]


def _to_proto(r: Resource) -> host_pb2.HostRecord:
    """Convert SQLAlchemy Resource ORM row to HostRecord proto (D-11)."""
    rec = host_pb2.HostRecord(
        id=r.id,
        resource_name=r.resource_name or "",
        hostname=r.hostname,
        type=r.type,
        provider=r.provider,
        region=r.region or "",
        status=r.status,
        environment=r.environment,
        external_id=r.external_id or "",
        external_url=r.external_url or "",
        average_daily_cost=r.average_daily_cost or 0.0,
        average_monthly_cost=r.average_monthly_cost or 0.0,
    )
    rec.owners.extend(r.owners or [])
    rec.mail_groups.extend(r.mail_groups or [])

    # Map metadata dict to proto Struct
    if r.metadata_:
        ParseDict(r.metadata_, rec.metadata)

    # Map timestamps
    if r.created_at:
        ts = timestamp_pb2.Timestamp()
        ts.FromDatetime(r.created_at.replace(tzinfo=datetime.timezone.utc) if r.created_at.tzinfo is None else r.created_at)
        rec.created_at.CopyFrom(ts)

    if r.updated_at:
        ts = timestamp_pb2.Timestamp()
        ts.FromDatetime(r.updated_at.replace(tzinfo=datetime.timezone.utc) if r.updated_at.tzinfo is None else r.updated_at)
        rec.updated_at.CopyFrom(ts)

    return rec


def list_resources(
    status: Optional[str] = None,
    environment: Optional[str] = None,
    type_: Optional[str] = None,
    provider: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 0,
) -> list[host_pb2.HostRecord]:
    """List inventory resources with optional filters. Returns HostRecord protos."""
    with get_session() as session:
        stmt = select(Resource)
        if status:
            stmt = stmt.where(Resource.status == status)
        if environment:
            stmt = stmt.where(Resource.environment == environment)
        if type_:
            stmt = stmt.where(Resource.type == type_)
        if provider:
            stmt = stmt.where(Resource.provider == provider)
        if region:
            stmt = stmt.where(Resource.region == region)
        stmt = stmt.order_by(Resource.hostname)
        if limit > 0:
            stmt = stmt.limit(limit)

        try:
            rows = session.scalars(stmt).all()
            return [_to_proto(r) for r in rows]
        except SQLAlchemyError as e:
            raise RuntimeError(f"failed to query resources: {e}") from e


def add_resource(
    hostname: str,
    type_: str,
    provider: str,
    environment: str,
    status: str = "active",
    resource_name: str = "",
    region: Optional[str] = None,
    owners: Optional[list[str]] = None,
    mail_groups: Optional[list[str]] = None,
    external_id: Optional[str] = None,
    external_url: Optional[str] = None,
) -> host_pb2.HostRecord:
    """Insert a new resource into inventory. Returns HostRecord proto."""
    if type_ not in VALID_TYPES:
        raise ValueError(f"invalid type: {type_} (must be one of: {', '.join(VALID_TYPES)})")
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"invalid provider: {provider} (must be one of: {', '.join(VALID_PROVIDERS)})")
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError(f"invalid environment: {environment} (must be one of: {', '.join(VALID_ENVIRONMENTS)})")
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status} (must be one of: {', '.join(VALID_STATUSES)})")

    now = datetime.datetime.utcnow()
    resource = Resource(
        resource_name=resource_name or hostname,
        hostname=hostname,
        type=type_,
        provider=provider,
        environment=environment,
        status=status,
        region=region,
        owners=owners or [],
        mail_groups=mail_groups or [],
        metadata_={},
        external_id=external_id,
        external_url=external_url,
        created_at=now,
        updated_at=now,
    )

    with get_session() as session:
        try:
            session.add(resource)
            session.commit()
            session.refresh(resource)
            return _to_proto(resource)
        except SQLAlchemyError as e:
            session.rollback()
            raise RuntimeError(f"failed to insert resource: {e}") from e


def update_resource(hostname: str, **fields) -> host_pb2.HostRecord:
    """Update resource fields by hostname. Returns updated HostRecord proto."""
    if not hostname:
        raise ValueError("hostname is required")

    # Validate fields if provided
    if "type_" in fields and fields["type_"] not in VALID_TYPES:
        raise ValueError(f"invalid type: {fields['type_']}")
    if "provider" in fields and fields["provider"] not in VALID_PROVIDERS:
        raise ValueError(f"invalid provider: {fields['provider']}")
    if "environment" in fields and fields["environment"] not in VALID_ENVIRONMENTS:
        raise ValueError(f"invalid environment: {fields['environment']}")
    if "status" in fields and fields["status"] not in VALID_STATUSES:
        raise ValueError(f"invalid status: {fields['status']}")

    with get_session() as session:
        try:
            stmt = select(Resource).where(Resource.hostname == hostname)
            resource = session.scalars(stmt).first()
            if resource is None:
                raise ValueError(f"resource not found: {hostname}")

            # Apply field updates (translate type_ -> type)
            for key, val in fields.items():
                attr = "type" if key == "type_" else key
                if val is not None and hasattr(resource, attr):
                    setattr(resource, attr, val)

            resource.updated_at = datetime.datetime.utcnow()
            session.commit()
            session.refresh(resource)
            return _to_proto(resource)
        except SQLAlchemyError as e:
            session.rollback()
            raise RuntimeError(f"failed to update resource: {e}") from e


def import_ssh_config(path: str = "~/.ssh/config") -> list[host_pb2.HostRecord]:
    """Parse SSH config file, add hosts not already in DB. Returns added HostRecords."""
    from adsops.hostctl.ssh_config import parse_ssh_config
    import os

    expanded = os.path.expanduser(path)
    hosts = parse_ssh_config(expanded)
    added = []

    with get_session() as session:
        for host_entry in hosts:
            hostname = host_entry.get("hostname") or host_entry.get("host")
            if not hostname:
                continue

            # Check if already in DB
            stmt = select(Resource).where(Resource.hostname == hostname)
            existing = session.scalars(stmt).first()
            if existing:
                continue

            alias = host_entry.get("host", hostname)
            now = datetime.datetime.utcnow()
            resource = Resource(
                resource_name=alias,
                hostname=hostname,
                type="server",
                provider="onprem",
                environment="production",
                status="active",
                owners=[],
                mail_groups=[],
                metadata_={},
                created_at=now,
                updated_at=now,
            )
            try:
                session.add(resource)
                session.commit()
                session.refresh(resource)
                added.append(_to_proto(resource))
            except SQLAlchemyError:
                session.rollback()

    return added


async def _probe(hostname: str) -> dict:
    """Async SSH probe — attempt connection and run echo ok."""
    try:
        async with asyncssh.connect(hostname, known_hosts=None) as conn:
            await conn.run("echo ok", check=False)
            return {"host": hostname, "reachable": True, "error": None}
    except Exception as e:
        return {"host": hostname, "reachable": False, "error": str(e)}


def probe_host(hostname: str) -> dict:
    """Probe a host via SSH to check reachability. Returns dict with reachable/error."""
    return asyncio.run(_probe(hostname))
