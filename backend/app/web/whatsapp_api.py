from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from flask import Blueprint, Response, jsonify, request, stream_with_context

from app.db.base import session_scope
from app.db.models import MessagingContact, MessagingConversation, MessagingMessage
from app.services import whatsapp_service
from app.services.whatsapp_service import APPROVED_TEMPLATES, WhatsAppSendError

whatsapp_api_bp = Blueprint("whatsapp_api", __name__, url_prefix="/api/whatsapp")
logger = structlog.get_logger(__name__)


@whatsapp_api_bp.after_request
def _no_cache(response):
    if "application/json" in response.content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response

_PAGE_SIZE = 40


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _session_open(conv: MessagingConversation) -> bool:
    if conv.last_inbound_at is None:
        return False
    return (_now_utc() - conv.last_inbound_at).total_seconds() < 86400


def _fmt_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _conv_to_dict(conv: MessagingConversation, contact: MessagingContact) -> dict:
    return {
        "id": str(conv.id),
        "contactId": str(contact.id),
        "contactName": contact.display_name or contact.phone,
        "phone": contact.phone,
        "waId": contact.wa_id,
        "lastMessagePreview": conv.last_message_preview,
        "lastActivityAt": _fmt_dt(conv.last_activity_at),
        "unreadCount": conv.unread_count,
        "status": conv.status,
        "sessionOpen": _session_open(conv),
        "channel": conv.channel,
        # Embedded contact — eliminates a round-trip from the browser
        "contact": {
            "id": str(contact.id),
            "phone": contact.phone,
            "displayName": contact.display_name or contact.phone,
            "waId": contact.wa_id,
            "labelsJson": contact.labels_json or "[]",
        },
    }


def _msg_to_dict(msg: MessagingMessage) -> dict:
    return {
        "id": str(msg.id),
        "direction": msg.direction,
        "body": msg.body,
        "status": msg.status,
        "isTemplate": msg.is_template,
        "templateName": msg.template_name,
        "providerMessageId": msg.provider_message_id,
        "sentAt": _fmt_dt(msg.sent_at),
        "receivedAt": _fmt_dt(msg.received_at),
        "deliveredAt": _fmt_dt(msg.delivered_at),
        "readAt": _fmt_dt(msg.read_at),
        "failedAt": _fmt_dt(msg.failed_at),
        "errorCode": msg.error_code,
        "createdAt": _fmt_dt(msg.created_at),
    }


# ── Conversations ─────────────────────────────────────────────────────────────

@whatsapp_api_bp.get("/conversations")
def list_conversations():
    status_filter = request.args.get("status", "open")
    search = request.args.get("search", "").strip().lower()
    unread_only = request.args.get("unread", "").lower() in ("1", "true")
    page = max(1, int(request.args.get("page", 1)))

    with session_scope() as db:
        q = (
            db.query(MessagingConversation, MessagingContact)
            .join(MessagingContact, MessagingConversation.contact_id == MessagingContact.id)
            .filter(MessagingConversation.channel == "whatsapp")
        )

        if status_filter != "all":
            q = q.filter(MessagingConversation.status == status_filter)

        if unread_only:
            q = q.filter(MessagingConversation.unread_count > 0)

        if search:
            like = f"%{search}%"
            q = q.filter(
                MessagingContact.display_name.ilike(like)
                | MessagingContact.phone.ilike(like)
                | MessagingConversation.last_message_preview.ilike(like)
            )

        total = q.count()
        rows = (
            q.order_by(MessagingConversation.last_activity_at.desc().nullslast())
            .offset((page - 1) * _PAGE_SIZE)
            .limit(_PAGE_SIZE)
            .all()
        )

        conversations = [_conv_to_dict(conv, contact) for conv, contact in rows]

    return jsonify({
        "conversations": conversations,
        "total": total,
        "page": page,
        "hasMore": (page * _PAGE_SIZE) < total,
    })


@whatsapp_api_bp.get("/conversations/<conv_id>")
def get_conversation(conv_id: str):
    try:
        conv_uuid = uuid.UUID(conv_id)
    except ValueError:
        return jsonify({"detail": "Invalid conversation ID"}), 400
    with session_scope() as db:
        conv = db.query(MessagingConversation).filter_by(id=conv_uuid).first()
        if not conv:
            return jsonify({"detail": "Not found"}), 404
        contact = db.query(MessagingContact).filter_by(id=conv.contact_id).first()
        return jsonify(_conv_to_dict(conv, contact))


@whatsapp_api_bp.patch("/conversations/<conv_id>")
def patch_conversation(conv_id: str):
    body = request.get_json(silent=True) or {}
    try:
        conv_uuid = uuid.UUID(conv_id)
    except ValueError:
        return jsonify({"detail": "Invalid conversation ID"}), 400
    with session_scope() as db:
        conv = db.query(MessagingConversation).filter_by(id=conv_uuid).first()
        if not conv:
            return jsonify({"detail": "Not found"}), 404

        if "unread_count" in body:
            conv.unread_count = int(body["unread_count"])
        if "status" in body and body["status"] in ("open", "closed", "archived"):
            conv.status = body["status"]
        conv.updated_at = _now_utc()
        db.commit()

        contact = db.query(MessagingContact).filter_by(id=conv.contact_id).first()
        return jsonify(_conv_to_dict(conv, contact))


# ── Messages ──────────────────────────────────────────────────────────────────

@whatsapp_api_bp.get("/conversations/<conv_id>/messages")
def get_messages(conv_id: str):
    before_id = request.args.get("before")
    after_id = request.args.get("after")
    limit = max(1, min(int(request.args.get("limit", 50)), 100))
    mark_read = request.args.get("mark_read", "").lower() in ("1", "true", "yes")

    try:
        conv_uuid = uuid.UUID(conv_id)
    except ValueError:
        return jsonify({"detail": "Invalid conversation ID"}), 400

    with session_scope() as db:
        conv = db.query(MessagingConversation).filter_by(id=conv_uuid).first()
        if not conv:
            return jsonify({"detail": "Not found"}), 404

        if mark_read and conv.unread_count > 0:
            conv.unread_count = 0
            conv.updated_at = _now_utc()
            db.commit()

        q = db.query(MessagingMessage).filter_by(conversation_id=conv.id)

        if before_id:
            try:
                before_uuid = uuid.UUID(before_id)
                anchor = db.query(MessagingMessage).filter_by(id=before_uuid).first()
                if anchor:
                    q = q.filter(MessagingMessage.created_at < anchor.created_at)
            except ValueError:
                pass  # ignore non-UUID cursor values (e.g. optimistic temp IDs)

        if after_id:
            try:
                after_uuid = uuid.UUID(after_id)
                anchor = db.query(MessagingMessage).filter_by(id=after_uuid).first()
                if anchor:
                    q = q.filter(MessagingMessage.created_at > anchor.created_at)
            except ValueError:
                pass  # optimistic IDs (opt-...) don't exist in DB — return full thread

        messages = q.order_by(MessagingMessage.created_at.asc()).limit(limit).all()
        contact = db.query(MessagingContact).filter_by(id=conv.contact_id).first()
        return jsonify({
            "messages": [_msg_to_dict(m) for m in messages],
            "conversation": _conv_to_dict(conv, contact),
        })


@whatsapp_api_bp.post("/conversations/<conv_id>/messages")
def send_reply(conv_id: str):
    body = request.get_json(silent=True) or {}
    text = (body.get("body") or "").strip()
    template_name = (body.get("template_name") or "").strip()

    if not text and not template_name:
        return jsonify({"detail": "body or template_name required"}), 400

    try:
        conv_uuid = uuid.UUID(conv_id)
    except ValueError:
        return jsonify({"detail": "Invalid conversation ID"}), 400

    try:
        with session_scope() as db:
            if template_name:
                msg = whatsapp_service.send_template(db, conv_uuid, template_name)
            else:
                msg = whatsapp_service.send_message(db, conv_uuid, text)
            return jsonify(_msg_to_dict(msg)), 201
    except WhatsAppSendError as exc:
        logger.error("whatsapp.api.send_failed", error=str(exc), conv_id=conv_id)
        return jsonify({"detail": f"Send failed: {exc}"}), 502
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 404


# ── New conversation ──────────────────────────────────────────────────────────

@whatsapp_api_bp.post("/conversations")
def start_conversation():
    """Start a new outbound conversation. Must use a template if no prior session."""
    body = request.get_json(silent=True) or {}
    # Strip +, spaces, dashes, parens — store as digits only (e.g. "18057332428")
    phone_raw = (body.get("phone") or "").strip().lstrip("+").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    text = (body.get("body") or "").strip()
    template_name = (body.get("template_name") or "").strip()

    if not phone_raw:
        return jsonify({"detail": "phone required"}), 400
    if not text and not template_name:
        return jsonify({"detail": "body or template_name required"}), 400

    with session_scope() as db:
        # Get or create contact
        contact = whatsapp_service._get_or_create_contact(db, phone_raw, None, None)
        conv = whatsapp_service._get_or_create_conversation(db, contact)
        db.commit()

        conv_uuid = conv.id
        try:
            if template_name:
                msg = whatsapp_service.send_template(db, conv_uuid, template_name)
            else:
                msg = whatsapp_service.send_message(db, conv_uuid, text)
        except WhatsAppSendError as exc:
            return jsonify({"detail": f"Send failed: {exc}"}), 502

        contact_fresh = db.query(MessagingContact).filter_by(id=contact.id).first()
        conv_fresh = db.query(MessagingConversation).filter_by(id=conv.id).first()
        return jsonify({
            "conversation": _conv_to_dict(conv_fresh, contact_fresh),
            "message": _msg_to_dict(msg),
        }), 201


# ── Contacts ──────────────────────────────────────────────────────────────────

@whatsapp_api_bp.get("/contacts/<contact_id>")
def get_contact(contact_id: str):
    try:
        contact_uuid = uuid.UUID(contact_id)
    except ValueError:
        return jsonify({"detail": "Invalid contact ID"}), 400
    with session_scope() as db:
        contact = db.query(MessagingContact).filter_by(id=contact_uuid).first()
        if not contact:
            return jsonify({"detail": "Not found"}), 404

        convs = db.query(MessagingConversation).filter_by(contact_id=contact.id).all()
        return jsonify({
            "id": str(contact.id),
            "phone": contact.phone,
            "displayName": contact.display_name,
            "waId": contact.wa_id,
            "labelsJson": contact.labels_json,
            "createdAt": _fmt_dt(contact.created_at),
            "conversations": [
                {
                    "id": str(c.id),
                    "channel": c.channel,
                    "status": c.status,
                    "lastMessagePreview": c.last_message_preview,
                    "lastActivityAt": _fmt_dt(c.last_activity_at),
                    "unreadCount": c.unread_count,
                }
                for c in convs
            ],
        })


@whatsapp_api_bp.patch("/contacts/<contact_id>")
def patch_contact(contact_id: str):
    body = request.get_json(silent=True) or {}
    try:
        contact_uuid = uuid.UUID(contact_id)
    except ValueError:
        return jsonify({"detail": "Invalid contact ID"}), 400
    with session_scope() as db:
        contact = db.query(MessagingContact).filter_by(id=contact_uuid).first()
        if not contact:
            return jsonify({"detail": "Not found"}), 404

        if "display_name" in body:
            contact.display_name = (body["display_name"] or "").strip() or contact.phone
        if "labels_json" in body:
            contact.labels_json = body["labels_json"]
        contact.updated_at = _now_utc()
        db.commit()
        return jsonify({
            "id": str(contact.id),
            "phone": contact.phone,
            "displayName": contact.display_name,
            "waId": contact.wa_id,
            "labelsJson": contact.labels_json,
        })


# ── Templates ─────────────────────────────────────────────────────────────────

@whatsapp_api_bp.get("/templates")
def list_templates():
    """Return the approved WhatsApp templates available for out-of-session sends."""
    return jsonify({"templates": APPROVED_TEMPLATES})


# ── SSE stream ────────────────────────────────────────────────────────────────

@whatsapp_api_bp.get("/stream")
def sse_stream():
    """Server-Sent Events endpoint. Pushes new_message and status_update events."""
    from app.services.sse_broker import whatsapp_sse
    q = whatsapp_sse.subscribe()
    return Response(
        stream_with_context(whatsapp_sse.stream(q)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
