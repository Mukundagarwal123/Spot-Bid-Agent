from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy import Uuid
except ImportError:
    from sqlalchemy.dialects.postgresql import UUID as Uuid  # type: ignore[no-redef]

from app.db.base import Base


class PortalLane(Base):
    __tablename__ = "portal_lanes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    origin_city: Mapped[str] = mapped_column(String(120), nullable=False)
    origin_state: Mapped[str] = mapped_column(String(2), nullable=False)
    origin_zip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    destination_city: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_state: Mapped[str] = mapped_column(String(2), nullable=False)
    destination_zip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    equipment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    pickup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PortalLaneStop(Base):
    __tablename__ = "portal_lane_stops"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip: Mapped[str | None] = mapped_column(String(10), nullable=True)


class PortalLaneMetricsSnapshot(Base):
    """One row per lane. Generated once at creation and never recalculated."""

    __tablename__ = "portal_lane_metrics_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    emails_sent: Mapped[int] = mapped_column(Integer, nullable=False)
    emails_clicked: Mapped[int] = mapped_column(Integer, nullable=False)
    email_replies: Mapped[int] = mapped_column(Integer, nullable=False)
    sms_sent: Mapped[int] = mapped_column(Integer, nullable=False)
    sms_replies: Mapped[int] = mapped_column(Integer, nullable=False)
    whatsapp_sent: Mapped[int] = mapped_column(Integer, nullable=False)
    whatsapp_replies: Mapped[int] = mapped_column(Integer, nullable=False)
    carriers_contacted: Mapped[int] = mapped_column(Integer, nullable=False)
    carriers_responded: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PortalLaneActivityEvent(Base):
    """Timeline events — 4 rows per lane, deterministically generated."""

    __tablename__ = "portal_lane_activity_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    event_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class PortalCarrierCRMSnapshot(Base):
    """10–30 dummy carrier rows per lane, generated once at lane creation."""

    __tablename__ = "portal_carrier_crm_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    carrier_name: Mapped[str] = mapped_column(String(120), nullable=False)
    times_contacted: Mapped[int] = mapped_column(Integer, nullable=False)
    times_responded: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_response_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_channel: Mapped[str] = mapped_column(String(20), nullable=False)
    response_rate: Mapped[float] = mapped_column(Float, nullable=False)
    last_contacted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
