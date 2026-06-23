from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.models import BouncedEmail, OutreachMessage, OutreachMessageEvent

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
    secret = settings.resend_webhook_secret
    if secret:
        try:
            from svix.webhooks import Webhook as SvixWebhook
            wh = SvixWebhook(secret)
            wh.verify(raw_body, {
                "svix-id":        svix_id,
                "svix-timestamp": svix_ts,
                "svix-signature": svix_signature,
            })
        except Exception as exc:
            logger.warning("webhook.resend.signature_invalid", error=str(exc))
            raise ValueError("invalid_signature") from exc

    payload = json.loads(raw_body)

    event_type_raw: str = payload.get("type", "")
    event_type = event_type_raw.removeprefix("email.")
    is_inbound_reply = event_type == "received"

    data = payload.get("data", {})
    created_at_str: str = payload.get("created_at", "")

    try:
        event_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        event_at = _utcnow()

    if is_inbound_reply:
        # Resend's email.received webhook carries no body text.
        # Full body is only available when Resend inbound routing POSTs to
        # /webhooks/inbound/replies. Here we capture from + subject from the
        # webhook metadata so the thread at least shows the reply happened.
        from app.webhooks import reply_handler

        email_id: str = data.get("email_id", "")

        # Resend sends "from" as "Name <email@addr>" — split out each part
        raw_from: str = data.get("from") or ""
        from_name: str | None = None
        if "<" in raw_from:
            from_name = raw_from.split("<")[0].strip() or None
            raw_from = raw_from.split("<")[-1].rstrip(">")
        from_email = raw_from.strip().lower()

        # Fetch full body from Resend receiving API
        body_text = ""
        try:
            resp = httpx.get(
                f"https://api.resend.com/emails/receiving/{email_id}",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                timeout=10,
            )
            if resp.is_success:
                body_data = resp.json()
                body_text = body_data.get("text") or body_data.get("html") or ""
                logger.info("resend.receiving.fetched", email_id=email_id, has_body=bool(body_text))
            else:
                logger.warning("resend.receiving.fetch_failed", email_id=email_id, status=resp.status_code, body=resp.text[:200])
        except Exception as exc:
            logger.warning("resend.receiving.fetch_error", email_id=email_id, error=str(exc))

        normalized = {
            "from":           from_email,
            "from_name":      from_name,
            "subject":        data.get("subject"),
            "text":           body_text,
            "smtp_message_id": data.get("message_id"),  # SMTP Message-ID for threading
        }

        logger.info(
            "webhook.resend.inbound_reply",
            email_id=email_id,
            from_email=from_email,
            has_body=bool(body_text),
        )

        reply_handler.handle_reply(db, normalized)
        return

    # ── All other event types (delivered, opened, clicked, bounced, etc.) ──

    provider_message_id: str = data.get("email_id", "")
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

    # Record bounced recipient so future campaigns skip this address
    if event_type == "bounced":
        bounced_email = message.email_to.strip().lower()
        existing = db.query(BouncedEmail).filter_by(email=bounced_email).first()
        if existing is None:
            db.add(BouncedEmail(
                id=uuid.uuid4(),
                email=bounced_email,
                bounced_at=event_at,
                provider_message_id=message.provider_message_id,
            ))
            logger.info("bounce_list.added", email=bounced_email)

    db.commit()

    logger.info(
        "webhook.resend.event_processed",
        provider_message_id=provider_message_id,
        event_type=event_type,
        message_id=str(message.id),
    )
