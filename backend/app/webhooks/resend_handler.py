from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.models import OutreachMessage, OutreachMessageEvent

logger = structlog.get_logger(__name__)

_STATUS_RANK = {
    "sent": 0,
    "delivered": 1,
    "opened": 2,
    "clicked": 3,
    "replied": 4,
    "bounced": 5,
    "failed": 5,
}

_TIMESTAMP_FIELD = {
    "delivered": "delivered_at",
    "opened": "opened_at",
    "clicked": "clicked_at",
    "replied": "replied_at",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def handle_event(
    db: Session,
    raw_body: bytes,
    svix_id: str,
    svix_ts: str,
    svix_signature: str,
) -> None:
    import resend as resend_sdk

    wh = resend_sdk.Webhooks(settings.resend_webhook_secret)
    try:
        payload = wh.verify(
            raw_body,
            {
                "svix-id": svix_id,
                "svix-timestamp": svix_ts,
                "svix-signature": svix_signature,
            },
        )
    except Exception as exc:
        logger.warning("webhook.resend.signature_invalid", error=str(exc))
        raise ValueError("invalid_signature") from exc

    event_type_raw: str = payload.get("type", "")
    event_type = event_type_raw.removeprefix("email.")

    data = payload.get("data", {})
    provider_message_id: str = data.get("email_id", "")
    created_at_str: str = payload.get("created_at", "")

    try:
        event_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        event_at = _utcnow()

    epoch_ms = int(event_at.timestamp() * 1000)
    idempotency_key = f"{provider_message_id}::{event_type}::{epoch_ms}"

    message = db.query(OutreachMessage).filter_by(provider_message_id=provider_message_id).first()
    if message is None:
        logger.info(
            "webhook.resend.message_not_found",
            provider_message_id=provider_message_id,
            event_type=event_type,
        )
        return

    event = OutreachMessageEvent(
        id=uuid.uuid4(),
        message_id=message.id,
        event_type=event_type,
        event_at=event_at,
        raw_payload=json.dumps(payload),
        idempotency_key=idempotency_key,
    )
    try:
        db.add(event)
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info("webhook.resend.duplicate_event", idempotency_key=idempotency_key)
        return

    # Advance message status if this event represents a higher state
    current_rank = _STATUS_RANK.get(message.status, -1)
    new_rank = _STATUS_RANK.get(event_type, -1)
    if new_rank > current_rank and event_type in _STATUS_RANK:
        message.status = event_type

    ts_field = _TIMESTAMP_FIELD.get(event_type)
    if ts_field and getattr(message, ts_field) is None:
        setattr(message, ts_field, event_at)

    db.commit()

    logger.info(
        "webhook.resend.event_processed",
        provider_message_id=provider_message_id,
        event_type=event_type,
        message_id=str(message.id),
    )
