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


import re as _re

# Patterns that mark the start of a quoted reply chain
_QUOTE_PATTERNS = [
    _re.compile(r"\n_{10,}\s*\n", _re.MULTILINE),                          # Outlook: ___________
    _re.compile(r"\nOn .{10,} wrote:\s*\n", _re.MULTILINE),                # Gmail / Apple Mail
    _re.compile(r"\n-{3,} ?Original Message ?-{3,}", _re.MULTILINE | _re.IGNORECASE),
    _re.compile(r"\nFrom:\s+\S", _re.MULTILINE),                           # bare "From:" header
]

# Patterns that mark the start of an email signature block
_SIG_PATTERNS = [
    _re.compile(r"\n--\s*\n"),                                              # RFC 3676 "-- " delimiter
    _re.compile(r"\n\[[\w][\w ]*(?:Logo|Icon|Brand|Signature|Cert)\]", _re.IGNORECASE),  # [Company Logo] etc.
]


def _strip_quoted_chain(text: str) -> str:
    """Return only the latest reply text, stripping quoted chain and email signature."""
    if not text:
        return text
    earliest_cut = len(text)
    for pat in _QUOTE_PATTERNS + _SIG_PATTERNS:
        m = pat.search(text)
        if m and m.start() < earliest_cut:
            earliest_cut = m.start()
    return text[:earliest_cut].strip()


def handle_reply(db: Session, payload: dict) -> None:
    """Ingest an inbound reply forwarded by Resend inbound routing."""
    from_email: str = payload.get("from", "").strip().lower()
    from_name: str | None = payload.get("from_name") or None
    reply_subject: str | None = payload.get("subject") or None
    reply_body: str = _strip_quoted_chain(payload.get("text") or payload.get("html") or "")
    smtp_message_id: str | None = payload.get("smtp_message_id") or None
    now = _utcnow()

    message = None
    lane_id = None

    if from_email:
        # Find the most recent message sent to this email — without the replied_at
        # filter so we always get the lane_id even for already-matched replies.
        message = (
            db.query(OutreachMessage)
            .filter(OutreachMessage.email_to == from_email)
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
        raw_headers=json.dumps({
            **(payload.get("headers") or {}),
            **( {"smtp_message_id": smtp_message_id} if smtp_message_id else {} ),
        }),
    ))

    if message and message.replied_at is None:
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
