from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.db.models import OutreachMessage, OutreachMessageEvent, OutreachReply

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def handle_reply(db: Session, payload: dict) -> None:
    """Ingest an inbound reply forwarded by Resend inbound routing."""
    from_email: str = payload.get("from", "").strip().lower()
    from_name: str | None = payload.get("from_name") or None
    reply_subject: str | None = payload.get("subject") or None
    reply_body: str = payload.get("text") or payload.get("html") or ""
    now = _utcnow()

    message = None
    lane_id = None

    if from_email:
        message = (
            db.query(OutreachMessage)
            .filter(OutreachMessage.email_to == from_email)
            .filter(OutreachMessage.replied_at.is_(None))
            .order_by(OutreachMessage.sent_at.desc())
            .first()
        )

    if message:
        lane_id = message.lane_id

    db.add(OutreachReply(
        id=uuid.uuid4(),
        message_id=message.id if message else None,
        lane_id=lane_id,
        from_email=from_email,
        from_name=from_name,
        reply_subject=reply_subject,
        reply_body=reply_body,
        received_at=now,
        raw_headers=json.dumps(payload.get("headers", {})) if payload.get("headers") else None,
    ))

    if message:
        message.replied_at = now
        message.status = "replied"

        idempotency_key = f"{message.provider_message_id}::replied::{int(now.timestamp() * 1000)}"
        db.add(OutreachMessageEvent(
            id=uuid.uuid4(),
            message_id=message.id,
            event_type="replied",
            event_at=now,
            raw_payload=json.dumps(payload),
            idempotency_key=idempotency_key,
        ))

    db.commit()

    logger.info(
        "webhook.reply.processed",
        from_email=from_email,
        matched=message is not None,
        message_id=str(message.id) if message else None,
        lane_id=str(lane_id) if lane_id else None,
    )
