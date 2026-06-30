from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import requests
import structlog

from app.core.settings import settings
from app.db.models import (
    MessagingContact,
    MessagingConversation,
    MessagingMessage,
    MessagingMessageEvent,
)
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)

_META_API_URL = "https://graph.facebook.com/v22.0/{phone_number_id}/messages"

# Add your approved templates here after creating them in WhatsApp Manager.
# Meta sample templates (hello_world, jaspers_market_*) only work from Meta test numbers,
# not from a real business phone number.
# Format: {"name": "template_name_in_meta", "language": "en_US", "label": "Display name"}
try:
    APPROVED_TEMPLATES: list[dict] = json.loads(settings.whatsapp_templates_json)
except (TypeError, json.JSONDecodeError):
    logger.warning("whatsapp.templates.invalid_json")
    APPROVED_TEMPLATES = []


class WhatsAppSendError(Exception):
    pass


def _extract_meta_error(exc: requests.HTTPError) -> str:
    """Pull the human-readable error message out of a Meta API 4xx response."""
    if exc.response is None:
        return str(exc)
    try:
        body = exc.response.json()
        err = body.get("error", {})
        msg = err.get("message", "")
        code = err.get("code", "")
        fbtrace = err.get("fbtrace_id", "")
        parts = [p for p in [f"[{code}]" if code else "", msg] if p]
        detail = " ".join(parts) or exc.response.text
        return f"{detail} (fbtrace: {fbtrace})" if fbtrace else detail
    except Exception:
        return exc.response.text or str(exc)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts(unix_str: str) -> datetime:
    return datetime.fromtimestamp(int(unix_str), timezone.utc).replace(tzinfo=None)


# ── Contact / Conversation helpers ───────────────────────────────────────────

def _get_or_create_contact(db: Session, phone: str, display_name: str | None, wa_id: str | None) -> MessagingContact:
    contact = db.query(MessagingContact).filter_by(phone=phone).first()
    if contact:
        # Update name/wa_id if we now have better data
        if display_name and not contact.display_name:
            contact.display_name = display_name
        if wa_id and not contact.wa_id:
            contact.wa_id = wa_id
        contact.updated_at = _now()
    else:
        contact = MessagingContact(
            id=uuid.uuid4(),
            phone=phone,
            display_name=display_name or phone,
            wa_id=wa_id,
            labels_json="[]",
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(contact)
        db.flush()
    return contact


def _get_or_create_conversation(db: Session, contact: MessagingContact) -> MessagingConversation:
    conv = db.query(MessagingConversation).filter_by(
        contact_id=contact.id, channel="whatsapp"
    ).first()
    if not conv:
        conv = MessagingConversation(
            id=uuid.uuid4(),
            contact_id=contact.id,
            channel="whatsapp",
            status="open",
            unread_count=0,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(conv)
        db.flush()
    elif conv.status != "open":
        # Re-open archived/closed conversations when a new inbound message arrives
        conv.status = "open"
    return conv


# ── Startup: deduplicate contacts that differ only by missing country code ────

def dedup_contacts(db: Session) -> None:
    """
    Merge contacts where one phone is a suffix of another.
    E.g. "8057332428" and "918057332428" are the same person — keep the longer one.
    Called once at startup.
    """
    contacts = db.query(MessagingContact).order_by(MessagingContact.phone).all()
    phones = {c.phone: c for c in contacts}
    merged = 0

    for phone, contact in list(phones.items()):
        if phone not in phones:
            continue  # already merged this one
        for other_phone, other_contact in list(phones.items()):
            if phone == other_phone:
                continue
            if not (other_phone.endswith(phone) and len(other_phone) > len(phone)):
                continue

            # other_phone has the country code — keep it, remove the shorter one
            canonical = other_contact
            duplicate = contact
            logger.info("whatsapp.dedup", keeping=canonical.phone, removing=duplicate.phone)

            # For each duplicate conversation, merge into canonical's conversation
            dup_convs = db.query(MessagingConversation).filter_by(contact_id=duplicate.id).all()
            for dup_conv in dup_convs:
                canon_conv = db.query(MessagingConversation).filter_by(
                    contact_id=canonical.id, channel=dup_conv.channel
                ).first()

                if canon_conv:
                    # Canonical already has a conversation — move messages there, delete dup conv
                    db.query(MessagingMessage).filter_by(conversation_id=dup_conv.id).update(
                        {"conversation_id": canon_conv.id, "contact_id": canonical.id},
                        synchronize_session=False,
                    )
                    db.delete(dup_conv)
                else:
                    # No canonical conversation — just re-point this one
                    dup_conv.contact_id = canonical.id

            # Re-point any remaining messages that reference the duplicate contact
            db.query(MessagingMessage).filter_by(contact_id=duplicate.id).update(
                {"contact_id": canonical.id}, synchronize_session=False
            )
            db.flush()
            db.delete(duplicate)
            phones.pop(phone, None)
            merged += 1
            break

    if merged:
        db.commit()
        logger.info("whatsapp.dedup.done", merged=merged)


# ── Inbound message ingestion ─────────────────────────────────────────────────

def ingest_inbound_message(db: Session, value: dict) -> None:
    """Process a Meta webhook value dict that contains a messages array."""
    msg = value["messages"][0]
    contacts_info = value.get("contacts", [{}])
    contact_info = contacts_info[0] if contacts_info else {}

    phone = msg["from"]
    wamid = msg["id"]
    msg_type = msg.get("type", "text")

    if msg_type == "text":
        body = msg.get("text", {}).get("body", "")
    else:
        body = f"[{msg_type}]"

    ts = _ts(msg["timestamp"])
    display_name = contact_info.get("profile", {}).get("name")
    wa_id = contact_info.get("wa_id")

    idempotency_key = f"{wamid}:received"
    if db.query(MessagingMessageEvent).filter_by(idempotency_key=idempotency_key).first():
        logger.info("whatsapp.ingest.duplicate", wamid=wamid)
        return

    contact = _get_or_create_contact(db, phone, display_name, wa_id)
    conv = _get_or_create_conversation(db, contact)
    latest_campaign_message = (
        db.query(MessagingMessage)
        .filter(
            MessagingMessage.conversation_id == conv.id,
            MessagingMessage.direction == "outbound",
            MessagingMessage.lane_id.is_not(None),
        )
        .order_by(MessagingMessage.created_at.desc())
        .first()
    )

    conv.unread_count = (conv.unread_count or 0) + 1
    conv.last_message_preview = body[:120]
    conv.last_activity_at = ts
    conv.last_inbound_at = ts
    conv.updated_at = _now()

    message = MessagingMessage(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        contact_id=contact.id,
        lane_id=latest_campaign_message.lane_id if latest_campaign_message else None,
        batch_id=latest_campaign_message.batch_id if latest_campaign_message else None,
        outreach_row_id=latest_campaign_message.outreach_row_id if latest_campaign_message else None,
        carrier_name=(
            latest_campaign_message.carrier_name if latest_campaign_message else display_name
        ),
        source_type=latest_campaign_message.source_type if latest_campaign_message else None,
        direction="inbound",
        body=body,
        provider="meta_whatsapp",
        provider_message_id=wamid,
        status="received",
        received_at=ts,
        created_at=_now(),
    )
    db.add(message)
    db.flush()

    event = MessagingMessageEvent(
        id=uuid.uuid4(),
        message_id=message.id,
        event_type="received",
        event_at=ts,
        raw_payload=json.dumps(value),
        idempotency_key=idempotency_key,
        created_at=_now(),
    )
    db.add(event)
    db.commit()
    logger.info("whatsapp.ingest.inbound", wamid=wamid, phone=phone, conv_id=str(conv.id))

    from app.services.sse_broker import whatsapp_sse

    def _iso(dt: datetime | None) -> str | None:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None

    whatsapp_sse.publish({
        "type": "new_message",
        "convId": str(conv.id),
        "message": {
            "id": str(message.id),
            "direction": "inbound",
            "body": message.body,
            "status": "received",
            "isTemplate": False,
            "templateName": None,
            "providerMessageId": message.provider_message_id,
            "sentAt": None,
            "receivedAt": _iso(message.received_at),
            "deliveredAt": None,
            "readAt": None,
            "failedAt": None,
            "errorCode": None,
            "createdAt": _iso(message.created_at),
        },
        "convUpdate": {
            "lastMessagePreview": conv.last_message_preview,
            "lastActivityAt": _iso(conv.last_activity_at),
            "unreadCount": conv.unread_count,
            "status": conv.status,
        },
    })


# ── Status update ingestion ───────────────────────────────────────────────────

def ingest_status_update(db: Session, value: dict) -> None:
    """Process a Meta webhook value dict that contains a statuses array."""
    st = value["statuses"][0]
    wamid = st["id"]
    status = st["status"]
    ts = _ts(st["timestamp"])

    idempotency_key = f"{wamid}:{status}"
    if db.query(MessagingMessageEvent).filter_by(idempotency_key=idempotency_key).first():
        return

    message = db.query(MessagingMessage).filter_by(provider_message_id=wamid).first()
    if message is None:
        # Unknown WAMID — log and drop; don't raise so Meta gets 200
        logger.warning("whatsapp.status.unknown_wamid", wamid=wamid, status=status)
        event = MessagingMessageEvent(
            id=uuid.uuid4(),
            message_id=None,
            event_type=status,
            event_at=ts,
            raw_payload=json.dumps(value),
            idempotency_key=idempotency_key,
            created_at=_now(),
        )
        db.add(event)
        db.commit()
        return

    if status == "delivered":
        message.delivered_at = ts
    elif status == "read":
        message.read_at = ts
    elif status == "failed":
        message.failed_at = ts
        errors = st.get("errors", [])
        message.error_code = str(errors[0].get("code", "")) if errors else "unknown"
    message.status = status

    event = MessagingMessageEvent(
        id=uuid.uuid4(),
        message_id=message.id,
        event_type=status,
        event_at=ts,
        raw_payload=json.dumps(value),
        idempotency_key=idempotency_key,
        created_at=_now(),
    )
    db.add(event)
    db.commit()
    logger.info("whatsapp.status.updated", wamid=wamid, status=status)

    from app.services.sse_broker import whatsapp_sse
    whatsapp_sse.publish({
        "type": "status_update",
        "convId": str(message.conversation_id),
        "messageId": str(message.id),
        "providerMessageId": wamid,
        "status": status,
    })


# ── Outbound send ─────────────────────────────────────────────────────────────

def send_message(
    db: Session,
    conversation_id: uuid.UUID,
    body: str,
    *,
    lane_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
    outreach_row_id: uuid.UUID | None = None,
    carrier_name: str | None = None,
    source_type: str | None = None,
) -> MessagingMessage:
    """Send a free-form text message. Insert DB row first, then call Meta API."""
    conv = db.query(MessagingConversation).filter_by(id=conversation_id).first()
    if not conv:
        raise ValueError(f"Conversation {conversation_id} not found")

    contact = db.query(MessagingContact).filter_by(id=conv.contact_id).first()
    if not contact:
        raise ValueError("Contact not found")

    now = _now()
    message = MessagingMessage(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        contact_id=contact.id,
        lane_id=lane_id,
        batch_id=batch_id,
        outreach_row_id=outreach_row_id,
        carrier_name=carrier_name or contact.display_name,
        source_type=source_type,
        direction="outbound",
        body=body,
        provider="meta_whatsapp",
        provider_message_id=None,
        status="pending",
        sent_at=now,
        created_at=now,
    )
    db.add(message)
    db.flush()

    phone_to = f"+{contact.phone}" if not contact.phone.startswith("+") else contact.phone
    url = _META_API_URL.format(phone_number_id=settings.whatsapp_phone_number_id)
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_to,
        "type": "text",
        "text": {"body": body},
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        wamid = data["messages"][0]["id"]
    except requests.HTTPError as exc:
        message.status = "failed"
        message.failed_at = _now()
        message.error_code = str(exc.response.status_code) if exc.response is not None else "http_error"
        db.commit()
        # Extract the actual Meta error message for surfacing to the UI
        meta_error = _extract_meta_error(exc)
        logger.error("whatsapp.send.failed", error=meta_error, phone=phone_to, status=message.error_code)
        raise WhatsAppSendError(meta_error) from exc
    except Exception as exc:
        message.status = "failed"
        message.failed_at = _now()
        message.error_code = "send_error"
        db.commit()
        logger.error("whatsapp.send.exception", error=str(exc), phone=phone_to)
        raise WhatsAppSendError(str(exc)) from exc

    message.provider_message_id = wamid
    message.status = "sent"

    event = MessagingMessageEvent(
        id=uuid.uuid4(),
        message_id=message.id,
        event_type="sent",
        event_at=_now(),
        raw_payload=None,
        idempotency_key=f"{wamid}:sent",
        created_at=_now(),
    )
    db.add(event)

    conv.last_message_preview = body[:120]
    conv.last_activity_at = _now()
    conv.updated_at = _now()
    db.commit()

    logger.info("whatsapp.send.ok", wamid=wamid, phone=phone_to, conv_id=str(conv.id))
    return message


def send_template(
    db: Session,
    conversation_id: uuid.UUID,
    template_name: str,
    language: str = "en_US",
    *,
    lane_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
    outreach_row_id: uuid.UUID | None = None,
    carrier_name: str | None = None,
    source_type: str | None = None,
) -> MessagingMessage:
    """Send an approved template message (used when session window has expired)."""
    conv = db.query(MessagingConversation).filter_by(id=conversation_id).first()
    if not conv:
        raise ValueError(f"Conversation {conversation_id} not found")

    contact = db.query(MessagingContact).filter_by(id=conv.contact_id).first()
    if not contact:
        raise ValueError("Contact not found")

    now = _now()
    body = f"[template: {template_name}]"
    message = MessagingMessage(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        contact_id=contact.id,
        lane_id=lane_id,
        batch_id=batch_id,
        outreach_row_id=outreach_row_id,
        carrier_name=carrier_name or contact.display_name,
        source_type=source_type,
        direction="outbound",
        body=body,
        provider="meta_whatsapp",
        provider_message_id=None,
        status="pending",
        is_template=True,
        template_name=template_name,
        sent_at=now,
        created_at=now,
    )
    db.add(message)
    db.flush()

    phone_to = f"+{contact.phone}" if not contact.phone.startswith("+") else contact.phone
    url = _META_API_URL.format(phone_number_id=settings.whatsapp_phone_number_id)
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_to,
        "type": "template",
        "template": {"name": template_name, "language": {"code": language}},
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        wamid = data["messages"][0]["id"]
    except requests.HTTPError as exc:
        message.status = "failed"
        message.failed_at = _now()
        message.error_code = str(exc.response.status_code) if exc.response is not None else "http_error"
        db.commit()
        meta_error = _extract_meta_error(exc)
        logger.error("whatsapp.template.failed", error=meta_error, phone=phone_to)
        raise WhatsAppSendError(meta_error) from exc
    except Exception as exc:
        message.status = "failed"
        message.failed_at = _now()
        message.error_code = "send_error"
        db.commit()
        raise WhatsAppSendError(str(exc)) from exc

    message.provider_message_id = wamid
    message.status = "sent"
    event = MessagingMessageEvent(
        id=uuid.uuid4(),
        message_id=message.id,
        event_type="sent",
        event_at=_now(),
        raw_payload=None,
        idempotency_key=f"{wamid}:sent",
        created_at=_now(),
    )
    db.add(event)
    conv.last_message_preview = body[:120]
    conv.last_activity_at = _now()
    conv.updated_at = _now()
    db.commit()
    logger.info("whatsapp.template.sent", wamid=wamid, template=template_name, phone=phone_to)
    return message
