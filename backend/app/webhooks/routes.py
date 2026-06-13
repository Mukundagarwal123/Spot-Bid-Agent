from __future__ import annotations

import structlog
from flask import Blueprint, jsonify, request

from app.db.base import session_scope
from app.webhooks import reply_handler, resend_handler

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")
logger = structlog.get_logger(__name__)


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
