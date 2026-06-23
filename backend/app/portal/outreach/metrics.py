from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy.orm import Session

from app.db.models import CarrierOutreachRow, OutreachBatch, OutreachMessage, OutreachReply, PortalLane
from app.portal.outreach.schemas import CarrierResponseItem, LaneMetricsResponse, SourceMetrics

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
        sent=0, delivered=0, opened=0, clicked=0, replied=0,
        open_rate=0.0, click_through_rate=0.0, reply_rate=0.0,
        test_mode=False, sent_at=None,
        carrier_responses=[],
        source_metrics={},
        campaign_ended=campaign_ended,
        follow_up_eligible_count=0,
        batch_status="none",
    )
    if latest_batch is None:
        return _empty

    batch_ids = [b.id for b in batches]
    messages = db.query(OutreachMessage).filter(OutreachMessage.batch_id.in_(batch_ids)).all()

    sent = len(messages)
    delivered = sum(1 for m in messages if m.delivered_at)
    opened = sum(1 for m in messages if m.opened_at or m.replied_at)
    clicked = sum(1 for m in messages if m.clicked_at)
    replied = sum(1 for m in messages if m.replied_at)

    # Follow-up eligible: initial sends (not follow-ups) that haven't replied
    initial_msgs = [m for m in messages if not m.is_follow_up]
    replied_emails = {m.email_to for m in messages if m.replied_at}
    follow_up_eligible = sum(1 for m in initial_msgs if m.email_to not in replied_emails)

    source_metrics = _build_source_metrics(messages)
    responses = _build_carrier_responses(db, messages)

    return LaneMetricsResponse(
        lane_id=str(lane_id),
        batch_id=str(latest_batch.id),
        sent=sent,
        delivered=delivered,
        opened=opened,
        clicked=clicked,
        replied=replied,
        open_rate=_rate(opened, sent),
        click_through_rate=_rate(clicked, sent),
        reply_rate=_rate(replied, sent),
        test_mode=latest_batch.test_mode,
        sent_at=_fmt(latest_batch.sent_at),
        carrier_responses=responses,
        source_metrics=source_metrics,
        campaign_ended=campaign_ended,
        follow_up_eligible_count=follow_up_eligible,
        batch_status=latest_batch.status,
    )


def _build_source_metrics(messages: list[OutreachMessage]) -> dict[str, SourceMetrics]:
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
