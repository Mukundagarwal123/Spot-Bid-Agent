from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy.orm import Session

from app.db.models import CarrierOutreachRow, OutreachBatch, OutreachMessage, OutreachReply
from app.portal.outreach.schemas import CarrierResponseItem, LaneMetricsResponse

logger = structlog.get_logger(__name__)

_STATUS_ORDER = ("sent", "delivered", "opened", "clicked", "replied", "failed", "bounced")


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def _fmt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def lane_metrics(db: Session, lane_id: uuid.UUID, exclude_test: bool = True) -> LaneMetricsResponse:
    q = db.query(OutreachBatch).filter(OutreachBatch.lane_id == lane_id)
    if exclude_test:
        q = q.filter(OutreachBatch.test_mode.is_(False))
    batch = q.order_by(OutreachBatch.created_at.desc()).first()

    if batch is None:
        return LaneMetricsResponse(
            lane_id=str(lane_id),
            batch_id=None,
            sent=0,
            delivered=0,
            opened=0,
            clicked=0,
            replied=0,
            open_rate=0.0,
            click_through_rate=0.0,
            reply_rate=0.0,
            test_mode=False,
            sent_at=None,
            carrier_responses=[],
        )

    messages = db.query(OutreachMessage).filter(OutreachMessage.batch_id == batch.id).all()

    sent = len(messages)
    delivered = sum(1 for m in messages if m.delivered_at)
    opened = sum(1 for m in messages if m.opened_at)
    clicked = sum(1 for m in messages if m.clicked_at)
    replied = sum(1 for m in messages if m.replied_at)

    responses = _build_carrier_responses(db, messages)

    return LaneMetricsResponse(
        lane_id=str(lane_id),
        batch_id=str(batch.id),
        sent=sent,
        delivered=delivered,
        opened=opened,
        clicked=clicked,
        replied=replied,
        open_rate=_rate(opened, sent),
        click_through_rate=_rate(clicked, sent),
        reply_rate=_rate(replied, sent),
        test_mode=batch.test_mode,
        sent_at=_fmt(batch.sent_at),
        carrier_responses=responses,
    )


def _build_carrier_responses(db: Session, messages: list[OutreachMessage]) -> list[CarrierResponseItem]:
    engaged = [m for m in messages if m.opened_at or m.clicked_at or m.replied_at]
    if not engaged:
        return []

    message_ids = [m.id for m in engaged]
    replies_by_msg: dict[uuid.UUID, OutreachReply] = {}
    for reply in db.query(OutreachReply).filter(OutreachReply.message_id.in_(message_ids)).all():
        if reply.message_id not in replies_by_msg:
            replies_by_msg[reply.message_id] = reply

    row_ids = [m.outreach_row_id for m in engaged if m.outreach_row_id]
    rows_by_id: dict[uuid.UUID, CarrierOutreachRow] = {}
    if row_ids:
        for row in db.query(CarrierOutreachRow).filter(CarrierOutreachRow.id.in_(row_ids)).all():
            rows_by_id[row.id] = row

    items: list[CarrierResponseItem] = []
    for msg in sorted(engaged, key=lambda m: m.replied_at or m.clicked_at or m.opened_at or m.sent_at, reverse=True):
        row = rows_by_id.get(msg.outreach_row_id) if msg.outreach_row_id else None
        reply = replies_by_msg.get(msg.id)

        last_event, last_event_at = _last_event(msg)
        snippet = reply.reply_body[:200] if reply and reply.reply_body else None

        items.append(CarrierResponseItem(
            carrier_name=msg.carrier_name,
            email=msg.email_to,
            phone=row.phone if row else "",
            source=row.source if row else "",
            status=msg.status,
            last_event=last_event,
            last_event_at=_fmt(last_event_at),
            reply_snippet=snippet,
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
