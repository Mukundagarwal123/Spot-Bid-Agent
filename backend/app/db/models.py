from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, DateTime, Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_config_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")
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


class PortalLaneCarrierSource(Base):
    """One row per DAT/internal import event for a lane."""

    __tablename__ = "portal_lane_carrier_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PortalLaneCarrierRecord(Base):
    """Individual carrier row extracted from an import source."""

    __tablename__ = "portal_lane_carrier_records"

    __table_args__ = (Index("ix_plcr_lane_source", "lane_id", "source_type"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portal_lane_carrier_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    carrier_name: Mapped[str] = mapped_column(String(500), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    mc_number: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    source_notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CarrierRelevancyRun(Base):
    """One row per FreightX model invocation for a lane (Source 3)."""

    __tablename__ = "carrier_relevancy_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    origin_zip: Mapped[str] = mapped_column(String(10), nullable=False)
    destination_zip: Mapped[str] = mapped_column(String(10), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CarrierRelevancyRecord(Base):
    """One carrier row from a FreightX relevancy model run (Source 3)."""

    __tablename__ = "carrier_relevancy_records"

    __table_args__ = (Index("ix_crr_lane_run", "lane_id", "run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("carrier_relevancy_runs.id", ondelete="CASCADE"), nullable=False
    )
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    docket_number: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    legal_name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    email_address: Mapped[str] = mapped_column(String(254), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    label: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="freightx_relevancy")
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CarrierOutreachSet(Base):
    """Metadata for one aggregation build across all three carrier sources for a lane."""

    __tablename__ = "carrier_outreach_sets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="building")
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dedupe_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CarrierOutreachRow(Base):
    """One canonical outreach-ready carrier row produced by the multi-source aggregator."""

    __tablename__ = "carrier_outreach_rows"

    __table_args__ = (Index("ix_cor_lane_set", "lane_id", "outreach_set_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outreach_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("carrier_outreach_sets.id", ondelete="CASCADE"), nullable=False
    )
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    carrier_name: Mapped[str] = mapped_column(String(500), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(254), nullable=False, default="")
    mc_number: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    source_row_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    dedupe_key: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OutreachBatch(Base):
    """One send campaign (production or test) for a lane."""

    __tablename__ = "outreach_batches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    outreach_set_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("carrier_outreach_sets.id", ondelete="SET NULL"), nullable=True
    )
    test_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    include_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_dat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_freightx: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    send_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    send_whatsapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    whatsapp_template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    whatsapp_language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False, default="")
    email_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    email_sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    whatsapp_sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OutreachMessage(Base):
    """One email sent to one carrier address within a batch."""

    __tablename__ = "outreach_messages"

    __table_args__ = (Index("ix_om_batch_lane", "batch_id", "lane_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("outreach_batches.id", ondelete="CASCADE"), nullable=False
    )
    lane_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="CASCADE"), nullable=False
    )
    outreach_row_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("carrier_outreach_rows.id", ondelete="SET NULL"), nullable=True
    )
    carrier_name: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    email_to: Mapped[str] = mapped_column(String(254), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="resend")
    provider_message_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")
    test_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_follow_up: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OutreachMessageEvent(Base):
    """Append-only audit log; one row per provider webhook callback."""

    __tablename__ = "outreach_message_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("outreach_messages.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)


class BouncedEmail(Base):
    """Global bounce list — emails that Resend has reported as bounced."""

    __tablename__ = "bounced_emails"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    bounced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    provider_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class OutreachReply(Base):
    """Inbound reply from a carrier, matched back to an outreach message when possible."""

    __tablename__ = "outreach_replies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("outreach_messages.id", ondelete="SET NULL"), nullable=True
    )
    lane_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="SET NULL"), nullable=True
    )
    from_email: Mapped[str] = mapped_column(String(254), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reply_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reply_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_headers: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── WhatsApp Inbox (Feature 008) ─────────────────────────────────────────────


class MessagingContact(Base):
    """One row per unique WhatsApp contact (phone number)."""

    __tablename__ = "messaging_contacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    wa_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    labels_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MessagingConversation(Base):
    """One thread per contact × channel. Currently only channel='whatsapp'."""

    __tablename__ = "messaging_conversations"
    __table_args__ = (
        UniqueConstraint("contact_id", "channel", name="uq_conv_contact_channel"),
        Index("ix_conv_channel_activity", "channel", "last_activity_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("messaging_contacts.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="whatsapp")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    unread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MessagingMessage(Base):
    """One row per inbound or outbound WhatsApp message."""

    __tablename__ = "messaging_messages"
    __table_args__ = (
        Index("ix_msg_conv_created", "conversation_id", "created_at"),
        Index("ix_msg_provider_id", "provider_message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("messaging_conversations.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("messaging_contacts.id", ondelete="CASCADE"), nullable=False
    )
    lane_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portal_lanes.id", ondelete="SET NULL"), nullable=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("outreach_batches.id", ondelete="SET NULL"), nullable=True
    )
    outreach_row_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("carrier_outreach_rows.id", ondelete="SET NULL"), nullable=True
    )
    carrier_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="meta_whatsapp")
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MessagingMessageEvent(Base):
    """Append-only event log — one row per webhook callback, idempotency-keyed."""

    __tablename__ = "messaging_message_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("messaging_messages.id", ondelete="CASCADE"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
