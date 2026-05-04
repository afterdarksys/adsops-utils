"""hostctl CLI sub-app — manage host inventory."""
import sys
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage host inventory", no_args_is_help=True)
console = Console()

VALID_TYPES = ["server", "container", "vm", "k8s-node", "load-balancer", "database"]
VALID_PROVIDERS = ["oci", "gcp", "onprem", "other"]
VALID_ENVIRONMENTS = ["production", "staging", "development"]
VALID_STATUSES = ["active", "inactive", "build", "blackout", "maintenance", "decommissioned"]


def _fmt(json_out: bool, proto_out: bool) -> str:
    if json_out:
        return "json"
    if proto_out:
        return "proto"
    return "text"


def _print_host_table(records: list) -> None:
    """Render a list of HostRecord protos as a rich table."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Hostname")
    table.add_column("Type")
    table.add_column("Provider")
    table.add_column("Environment")
    table.add_column("Status")
    table.add_column("Region")
    for r in records:
        table.add_row(
            str(r.id),
            r.hostname,
            r.type,
            r.provider,
            r.environment,
            r.status,
            r.region or "",
        )
    console.print(table)


@app.command("list")
def list_hosts(
    status: Optional[str] = typer.Option(None, help="Filter by status"),
    environment: Optional[str] = typer.Option(None, "--env", help="Filter by environment"),
    type_: Optional[str] = typer.Option(None, "--type", help="Filter by type"),
    provider: Optional[str] = typer.Option(None, help="Filter by provider"),
    region: Optional[str] = typer.Option(None, help="Filter by region"),
    limit: int = typer.Option(0, help="Limit results (0=unlimited)"),
    json_out: Annotated[bool, typer.Option("--json")] = False,
    proto_out: Annotated[bool, typer.Option("--proto")] = False,
) -> None:
    """List hosts from inventory."""
    from adsops.hostctl.service import list_resources
    from adsops.output import print_protos

    records = list_resources(
        status=status,
        environment=environment,
        type_=type_,
        provider=provider,
        region=region,
        limit=limit,
    )

    fmt = _fmt(json_out, proto_out)
    if fmt == "text":
        if not records:
            typer.echo("No hosts found.")
            return
        _print_host_table(records)
    else:
        print_protos(records, fmt)


@app.command("add")
def add_host(
    hostname: str = typer.Argument(..., help="Hostname to add"),
    type_: str = typer.Option("server", "--type", help=f"Host type ({', '.join(VALID_TYPES)})"),
    provider: str = typer.Option("onprem", "--provider", help=f"Provider ({', '.join(VALID_PROVIDERS)})"),
    environment: str = typer.Option("production", "--env", help=f"Environment ({', '.join(VALID_ENVIRONMENTS)})"),
    status: str = typer.Option("active", "--status", help=f"Status ({', '.join(VALID_STATUSES)})"),
    resource_name: str = typer.Option("", "--name", help="Resource display name (defaults to hostname)"),
    region: Optional[str] = typer.Option(None, "--region", help="Region"),
    json_out: Annotated[bool, typer.Option("--json")] = False,
    proto_out: Annotated[bool, typer.Option("--proto")] = False,
) -> None:
    """Add a host to inventory."""
    from adsops.hostctl.service import add_resource
    from adsops.output import print_proto

    try:
        record = add_resource(
            hostname=hostname,
            type_=type_,
            provider=provider,
            environment=environment,
            status=status,
            resource_name=resource_name,
            region=region,
        )
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    fmt = _fmt(json_out, proto_out)
    if fmt == "text":
        typer.echo(f"Successfully added host: {hostname}")
        _print_host_table([record])
    else:
        print_proto(record, fmt)


@app.command("update")
def update_host(
    hostname: str = typer.Argument(..., help="Hostname to update"),
    type_: Optional[str] = typer.Option(None, "--type", help="New type"),
    provider: Optional[str] = typer.Option(None, "--provider", help="New provider"),
    environment: Optional[str] = typer.Option(None, "--env", help="New environment"),
    status: Optional[str] = typer.Option(None, "--status", help="New status"),
    region: Optional[str] = typer.Option(None, "--region", help="New region"),
    json_out: Annotated[bool, typer.Option("--json")] = False,
    proto_out: Annotated[bool, typer.Option("--proto")] = False,
) -> None:
    """Update a host in inventory."""
    from adsops.hostctl.service import update_resource
    from adsops.output import print_proto

    updates = {}
    if type_ is not None:
        updates["type_"] = type_
    if provider is not None:
        updates["provider"] = provider
    if environment is not None:
        updates["environment"] = environment
    if status is not None:
        updates["status"] = status
    if region is not None:
        updates["region"] = region

    if not updates:
        typer.echo("No fields to update specified.", err=True)
        raise typer.Exit(code=1)

    try:
        record = update_resource(hostname, **updates)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    fmt = _fmt(json_out, proto_out)
    if fmt == "text":
        typer.echo(f"Successfully updated host: {hostname}")
        _print_host_table([record])
    else:
        print_proto(record, fmt)


@app.command("import-ssh-config")
def import_ssh(
    path: str = typer.Option("~/.ssh/config", help="Path to SSH config file"),
    json_out: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Import hosts from SSH config file into inventory."""
    from adsops.hostctl.service import import_ssh_config
    from adsops.output import print_protos

    try:
        added = import_ssh_config(path)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if not added:
        typer.echo("No new hosts imported (all already exist in inventory).")
        return

    typer.echo(f"Imported {len(added)} host(s).")
    if json_out:
        print_protos(added, "json")
    else:
        _print_host_table(added)


@app.command("probe")
def probe(
    hostname: str = typer.Argument(..., help="Hostname to probe via SSH"),
) -> None:
    """Probe a host via SSH to check reachability (PY-02)."""
    from adsops.hostctl.service import probe_host

    result = probe_host(hostname)
    if result["reachable"]:
        typer.echo(f"{hostname}: reachable")
    else:
        typer.echo(f"{hostname}: unreachable — {result['error']}", err=True)
        raise typer.Exit(code=1)
