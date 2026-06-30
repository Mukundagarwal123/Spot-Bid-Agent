from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy.orm import Session

from app.db.models import (
    CarrierOutreachRow,
    MessagingContact,
    MessagingMessage,
    OutreachBatch,
    OutreachMessage,
    OutreachReply,
    PortalLane,
)
from app.portal.outreach.schemas import (
    CarrierResponseItem,
    ChannelMetrics,
    LaneMetricsResponse,
    SourceMetrics,
)

logger = structlog.get_logger(__name__)

_STATUS_ORDER = ("sent", "delivered", "opened", "clicked", "replied", "failed", "bounced")

_SOURCE_DISPLAY = {
    "internal": "Internal",
    "dat": "DAT",
    "crr_model": "CRR Model",
    "manual": "Manual Emails",
}


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def _fmt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def lane_metrics(db: Session, lane_id: uuid.UUID, exclude_test: bool = True) -> LaneMetricsResponse:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    campaign_ended = (lane.status == "completed") if lane else False

    q = db.query(OutreachBatch).filter(OutreachBatch.lane_id == lane_id)
    if exclude_test:
        q = q.filter(OutreachBatch.test_mode.is_(False))
    batches = q.order_by(OutreachBatch.created_at.desc()).all()

    latest_batch = batches[0] if batches else None

    _empty = LaneMetricsResponse(
        lane_id=str(lane_id),
        batch_id=None,
        sent=0, delivered=0, opened=0, clicked=0, replied=0, failed=0, bounced=0,
        open_rate=0.0, click_through_rate=0.0, reply_rate=0.0,
        test_mode=False, sent_at=None,
        carrier_responses=[],
        source_metrics={},
        channel_metrics={
            "email": ChannelMetrics(),
            "whatsapp": ChannelMetrics(),
        },
        unique_contacts=0,
        campaign_ended=campaign_ended,
        follow_up_eligible_count=0,
        batch_status="none",
    )
    if latest_batch is None:
        return _empty

    batch_ids = [b.id for b in batches]
    messages = db.query(OutreachMessage).filter(OutreachMessage.batch_id.in_(batch_ids)).all()
    whatsapp_messages = (
        db.query(MessagingMessage)
        .filter(
            MessagingMessage.batch_id.in_(batch_ids),
            MessagingMessage.direction == "outbound",
        )
        .all()
    )
    whatsapp_inbound = (
        db.query(MessagingMessage)
        .filter(
            MessagingMessage.lane_id == lane_id,
            MessagingMessage.direction == "inbound",
        )
        .all()
    )
    replied_contact_ids = {message.contact_id for message in whatsapp_inbound}

    email_sent = len(messages)
    email_delivered = sum(1 for m in messages if m.delivered_at)
    email_opened = sum(1 for m in messages if m.opened_at or m.replied_at)
    clicked = sum(1 for m in messages if m.clicked_at)
    email_replied = sum(1 for m in messages if m.replied_at)
    email_failed = sum(1 for m in messages if m.status == "failed")
    email_bounced = sum(1 for m in messages if m.status == "bounced")

    whatsapp_sent = len(whatsapp_messages)
    whatsapp_delivered = sum(1 for m in whatsapp_messages if m.delivered_at or m.read_at)
    whatsapp_opened = sum(1 for m in whatsapp_messages if m.read_at)
    whatsapp_replied = len({m.contact_id for m in whatsapp_messages if m.contact_id in replied_contact_ids})
    whatsapp_failed = sum(1 for m in whatsapp_messages if m.failed_at or m.status == "failed")

    sent = email_sent + whatsapp_sent
    delivered = email_delivered + whatsapp_delivered
    opened = email_opened + whatsapp_opened
    replied = email_replied + whatsapp_replied
    failed = email_failed + whatsapp_failed

    # Follow-up eligible: initial sends (not follow-ups) that haven't replied
    initial_msgs = [m for m in messages if not m.is_follow_up]
    replied_emails = {m.email_to for m in messages if m.replied_at}
    follow_up_eligible = sum(1 for m in initial_msgs if m.email_to not in replied_emails)

    source_metrics = _build_source_metrics(messages, whatsapp_messages, replied_contact_ids)
    responses = _build_carrier_responses(db, messages)
    responses.extend(_build_whatsapp_responses(db, whatsapp_messages, whatsapp_inbound))
    responses.sort(key=lambda item: item.last_event_at or "", reverse=True)
    unique_contacts = len({
        f"email:{message.email_to.lower()}" for message in messages
    } | {
        f"whatsapp:{message.contact_id}" for message in whatsapp_messages
    })

    return LaneMetricsResponse(
        lane_id=str(lane_id),
        batch_id=str(latest_batch.id),
        sent=sent,
        delivered=delivered,
        opened=opened,
        clicked=clicked,
        replied=replied,
        failed=failed,
        bounced=email_bounced,
        open_rate=_rate(opened, sent),
        click_through_rate=_rate(clicked, sent),
        reply_rate=_rate(replied, sent),
        test_mode=latest_batch.test_mode,
        sent_at=_fmt(latest_batch.sent_at),
        carrier_responses=responses,
        source_metrics=source_metrics,
        channel_metrics={
            "email": ChannelMetrics(
                sent=email_sent,
                delivered=email_delivered,
                opened=email_opened,
                clicked=clicked,
                replied=email_replied,
                failed=email_failed,
                bounced=email_bounced,
            ),
            "whatsapp": ChannelMetrics(
                sent=whatsapp_sent,
                delivered=whatsapp_delivered,
                opened=whatsapp_opened,
                replied=whatsapp_replied,
                failed=whatsapp_failed,
            ),
        },
        unique_contacts=unique_contacts,
        campaign_ended=campaign_ended,
        follow_up_eligible_count=follow_up_eligible,
        batch_status=latest_batch.status,
    )


def _build_source_metrics(
    messages: list[OutreachMessage],
    whatsapp_messages: list[MessagingMessage],
    replied_contact_ids: set[uuid.UUID],
) -> dict[str, SourceMetrics]:
    buckets: dict[str, dict[str, int]] = {}
    for m in messages:
        st = (m.source_type or "internal").lower()
        if st not in buckets:
            buckets[st] = {"total": 0, "delivered": 0, "opened": 0, "replied": 0}
        buckets[st]["total"] += 1
        if m.delivered_at:
            buckets[st]["delivered"] += 1
        if m.opened_at or m.replied_at:
            buckets[st]["opened"] += 1
        if m.replied_at:
            buckets[st]["replied"] += 1

    for message in whatsapp_messages:
        st = (message.source_type or "internal").lower()
        if st not in buckets:
            buckets[st] = {"total": 0, "delivered": 0, "opened": 0, "replied": 0}
        buckets[st]["total"] += 1
        if message.delivered_at or message.read_at:
            buckets[st]["delivered"] += 1
        if message.read_at:
            buckets[st]["opened"] += 1
        if message.contact_id in replied_contact_ids:
            buckets[st]["replied"] += 1

    return {
        _SOURCE_DISPLAY.get(k, k): SourceMetrics(**v)
        for k, v in buckets.items()
    }


_STATUS_RANK = {"sent": 0, "delivered": 1, "opened": 2, "clicked": 3, "replied": 4, "failed": 5, "bounced": 6}


def _build_carrier_responses(db: Session, messages: list[OutreachMessage]) -> list[CarrierResponseItem]:
    if not messages:
        return []

    # Fetch all replies linked to these messages
    message_ids = [m.id for m in messages]
    all_replies = db.query(OutreachReply).filter(OutreachReply.message_id.in_(message_ids)).all()
    replies_by_msg: dict[uuid.UUID, OutreachReply] = {}
    for reply in all_replies:
        if reply.message_id not in replies_by_msg:
            replies_by_msg[reply.message_id] = reply

    row_ids = [m.outreach_row_id for m in messages if m.outreach_row_id]
    rows_by_id: dict[uuid.UUID, CarrierOutreachRow] = {}
    if row_ids:
        for row in db.query(CarrierOutreachRow).filter(CarrierOutreachRow.id.in_(row_ids)).all():
            rows_by_id[row.id] = row

    # Group messages by carrier email — one row per carrier in the UI
    grouped: dict[str, list[OutreachMessage]] = {}
    for msg in messages:
        grouped.setdefault(msg.email_to.lower(), []).append(msg)

    items: list[CarrierResponseItem] = []
    for email, msgs in grouped.items():
        # Pick the initial (non-follow-up) message as the canonical row; fall back to first msg
        initial = next((m for m in msgs if not m.is_follow_up), msgs[0])
        # Use the highest-ranked status across all messages for this carrier
        best_msg = max(msgs, key=lambda m: (_STATUS_RANK.get(m.status, -1), m.sent_at or datetime.min))
        # Use the latest reply snippet for this carrier
        carrier_replies = [replies_by_msg[m.id] for m in msgs if m.id in replies_by_msg]
        latest_reply = max(carrier_replies, key=lambda r: r.received_at, default=None) if carrier_replies else None
        snippet = latest_reply.reply_body[:200] if latest_reply and latest_reply.reply_body else None
        # Max attempt number = total contact count
        max_attempt = max(m.attempt_number for m in msgs)

        row = rows_by_id.get(initial.outreach_row_id) if initial.outreach_row_id else None
        last_event, last_event_at = _last_event(best_msg)
        st = (initial.source_type or "internal").lower()

        items.append(CarrierResponseItem(
            carrier_name=initial.carrier_name,
            email=initial.email_to,
            phone=row.phone if row else "",
            channel="email",
            source=_SOURCE_DISPLAY.get(st, st),
            source_type=st,
            status=best_msg.status,
            last_event=last_event,
            last_event_at=_fmt(last_event_at),
            reply_snippet=snippet,
            attempt_number=max_attempt,
            is_follow_up=False,
        ))

    # Sort by most recent activity descending
    items.sort(key=lambda i: i.last_event_at or "", reverse=True)
    return items


def _build_whatsapp_responses(
    db: Session,
    messages: list[MessagingMessage],
    inbound: list[MessagingMessage],
) -> list[CarrierResponseItem]:
    if not messages:
        return []

    contacts = {
        contact.id: contact
        for contact in db.query(MessagingContact)
        .filter(MessagingContact.id.in_({message.contact_id for message in messages}))
        .all()
    }
    inbound_by_contact: dict[uuid.UUID, list[MessagingMessage]] = {}
    for message in inbound:
        inbound_by_contact.setdefault(message.contact_id, []).append(message)

    grouped: dict[uuid.UUID, list[MessagingMessage]] = {}
    for message in messages:
        grouped.setdefault(message.contact_id, []).append(message)

    items: list[CarrierResponseItem] = []
    for contact_id, contact_messages in grouped.items():
        latest = max(
            contact_messages,
            key=lambda message: message.read_at or message.delivered_at or message.sent_at or message.created_at,
        )
        replies = inbound_by_contact.get(contact_id, [])
        latest_reply = max(
            replies,
            key=lambda message: message.received_at or message.created_at,
            default=None,
        )
        if latest_reply:
            status = "replied"
            last_event_at = latest_reply.received_at or latest_reply.created_at
        elif latest.failed_at or latest.status == "failed":
            status = "failed"
            last_event_at = latest.failed_at or latest.created_at
        elif latest.read_at:
            status = "opened"
            last_event_at = latest.read_at
        elif latest.delivered_at:
            status = "delivered"
            last_event_at = latest.delivered_at
        else:
            status = "sent"
            last_event_at = latest.sent_at or latest.created_at

        contact = contacts.get(contact_id)
        source_type = (contact_messages[0].source_type or "internal").lower()
        items.append(CarrierResponseItem(
            carrier_name=(
                contact_messages[0].carrier_name
                or (contact.display_name if contact else "")
                or (contact.phone if contact else "")
            ),
            email="",
            phone=contact.phone if contact else "",
            channel="whatsapp",
            source=_SOURCE_DISPLAY.get(source_type, source_type),
            source_type=source_type,
            status=status,
            last_event=status,
            last_event_at=_fmt(last_event_at),
            reply_snippet=latest_reply.body[:200] if latest_reply and latest_reply.body else None,
            attempt_number=len(contact_messages),
            is_follow_up=False,
        ))
    return items


def _last_event(msg: OutreachMessage) -> tuple[str, datetime | None]:
    if msg.replied_at:
        return "replied", msg.replied_at
    if msg.clicked_at:
        return "clicked", msg.clicked_at
    if msg.opened_at:
        return "opened", msg.opened_at
    if msg.delivered_at:
        return "delivered", msg.delivered_at
    return "sent", msg.sent_at
