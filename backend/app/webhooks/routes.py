from __future__ import annotations

import hashlib
import hmac
import structlog
from flask import Blueprint, jsonify, request

from app.core.settings import settings
from app.db.base import session_scope
from app.webhooks import reply_handler, resend_handler

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")
# Alias blueprint at root — catches /webhook (no 's') that Meta may call if dashboard URL was set wrong
webhook_alias_bp = Blueprint("webhook_alias", __name__)
logger = structlog.get_logger(__name__)


@webhooks_bp.post("/resend")
@webhooks_bp.post("/resend/events")
def resend_events():
    raw_body = request.get_data()
    svix_id = request.headers.get("svix-id", "")
    svix_ts = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")

    try:
        with session_scope() as db:
            resend_handler.handle_event(db, raw_body, svix_id, svix_ts, svix_signature)
    except ValueError as exc:
        if str(exc) == "invalid_signature":
            return jsonify({"detail": "Invalid webhook signature"}), 401
        raise
    except Exception as exc:
        logger.error("webhook.resend.unhandled_error", error=str(exc))

    # Always return 200 to prevent Resend retry storms
    return jsonify({"ok": True}), 200


@webhooks_bp.post("/inbound/replies")
def inbound_replies():
    payload = request.get_json(silent=True) or {}

    try:
        with session_scope() as db:
            reply_handler.handle_reply(db, payload)
    except Exception as exc:
        logger.error("webhook.reply.unhandled_error", error=str(exc))

    return jsonify({"ok": True}), 200


# ── Meta WhatsApp Business Cloud API webhooks ─────────────────────────────────

@webhooks_bp.get("/whatsapp")
def whatsapp_verify():
    """One-time webhook subscription verification from Meta."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        logger.info("webhook.whatsapp.verified")
        return challenge or "", 200

    logger.warning("webhook.whatsapp.verify_failed", mode=mode)
    return jsonify({"detail": "Forbidden"}), 403


@webhooks_bp.post("/whatsapp")
def whatsapp_event():
    """Inbound WhatsApp messages and message status updates from Meta."""
    from app.services import whatsapp_service

    # Validate X-Hub-Signature-256
    raw_body = request.get_data()
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if settings.whatsapp_app_secret:
        expected = "sha256=" + hmac.new(
            settings.whatsapp_app_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            logger.warning("webhook.whatsapp.invalid_signature")
            return jsonify({"detail": "Forbidden"}), 403

    try:
        payload = request.get_json(force=True) or {}
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if not value:
                    continue
                with session_scope() as db:
                    if "messages" in value:
                        whatsapp_service.ingest_inbound_message(db, value)
                    elif "statuses" in value:
                        whatsapp_service.ingest_status_update(db, value)
    except Exception as exc:
        logger.error("webhook.whatsapp.unhandled_error", error=str(exc))

    # Always return 200 — Meta retries on non-2xx
    return "", 200


# Root-level aliases: handles /webhook (no 's') if Meta dashboard was set to wrong URL
@webhook_alias_bp.get("/webhook")
def whatsapp_verify_alias():
    return whatsapp_verify()


@webhook_alias_bp.post("/webhook")
def whatsapp_event_alias():
    return whatsapp_event()
