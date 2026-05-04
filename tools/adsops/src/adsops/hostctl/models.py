from typing import Optional
import datetime

from sqlalchemy import Integer, String, Float, DateTime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, mapped_column, MappedColumn


class Base(DeclarativeBase):
    pass


class Resource(Base):
    __tablename__ = "inventory_resources"

    id: MappedColumn[int] = mapped_column(Integer, primary_key=True)
    resource_name: MappedColumn[str] = mapped_column(String, nullable=False)
    hostname: MappedColumn[str] = mapped_column(String, nullable=False)
    type: MappedColumn[str] = mapped_column(String, nullable=False)
    provider: MappedColumn[str] = mapped_column(String, nullable=False)
    region: MappedColumn[Optional[str]] = mapped_column(String, nullable=True)
    status: MappedColumn[str] = mapped_column(String, nullable=False)
    environment: MappedColumn[str] = mapped_column(String, nullable=False)
    owners: MappedColumn[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    # CRITICAL: DB column is "mailgroups" (no underscore) — matches Go's mailgroups column
    mail_groups: MappedColumn[list] = mapped_column("mailgroups", ARRAY(String), nullable=False, default=list)
    # CRITICAL: "metadata" conflicts with SQLAlchemy internals — use metadata_ mapped to "metadata"
    metadata_: MappedColumn[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    average_daily_cost: MappedColumn[Optional[float]] = mapped_column(Float, nullable=True)
    average_monthly_cost: MappedColumn[Optional[float]] = mapped_column(Float, nullable=True)
    external_id: MappedColumn[Optional[str]] = mapped_column(String, nullable=True)
    external_url: MappedColumn[Optional[str]] = mapped_column(String, nullable=True)
    created_at: MappedColumn[datetime.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: MappedColumn[datetime.datetime] = mapped_column(DateTime, nullable=False)
