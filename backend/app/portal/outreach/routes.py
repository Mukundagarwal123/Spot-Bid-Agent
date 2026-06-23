from __future__ import annotations

import uuid

import structlog
from flask import Blueprint, g, jsonify, request
from pydantic import ValidationError

from app.db.base import session_scope
from app.portal.outreach import metrics as outreach_metrics
from app.portal.outreach import service as outreach_service
from app.portal.outreach.schemas import CarrierReplyRequest, EndCampaignRequest, FollowUpRequest, OutreachRequest

outreach_bp = Blueprint("outreach_api", __name__, url_prefix="/portal")
logger = structlog.get_logger(__name__)


def _err(exc: ValidationError):
    import json
    return jsonify({"detail": json.loads(exc.json())}), 422


@outreach_bp.post("/lanes/<uuid:lane_id>/outreach/preview")
def outreach_preview(lane_id: uuid.UUID):
    payload = request.get_json(silent=True) or {}
    request_id = getattr(g, "correlation_id", "")

    try:
        req = OutreachRequest.model_validate(payload)
    except ValidationError as exc:
        return _err(exc)

    try:
        with session_scope() as db:
            result = outreach_service.preview(db, lane_id, req, request_id)
    except ValueError as exc:
        msg = str(exc)
        if msg == "lane_not_found":
            return jsonify({"detail": "Lane not found"}), 404
        if msg == "no_outreach_set":
            return jsonify({"detail": "No ready outreach set found for this lane. Build one first."}), 409
        raise

    return jsonify(result.model_dump(mode="json")), 200


@outreach_bp.post("/lanes/<uuid:lane_id>/outreach/send")
def outreach_send(lane_id: uuid.UUID):
    payload = request.get_json(silent=True) or {}
    request_id = getattr(g, "correlation_id", "")

    try:
        req = OutreachRequest.model_validate(payload)
    except ValidationError as exc:
        return _err(exc)

    try:
        with session_scope() as db:
            result = outreach_service.send(db, lane_id, req, request_id)
    except ValueError as exc:
        msg = str(exc)
        if msg == "lane_not_found":
            return jsonify({"detail": "Lane not found"}), 404
        if msg == "no_outreach_set":
            return jsonify({"detail": "No carrier data available. Try again once sources have loaded."}), 409
        if msg == "no_valid_recipients":
            return jsonify({"detail": "No valid email addresses found for the selected sources."}), 422
        raise

    return jsonify(result.model_dump(mode="json")), 201


@outreach_bp.post("/lanes/<uuid:lane_id>/outreach/follow-up")
def outreach_follow_up(lane_id: uuid.UUID):
    payload = request.get_json(silent=True) or {}
    request_id = getattr(g, "correlation_id", "")
    try:
        req = FollowUpRequest.model_validate(payload)
    except ValidationError as exc:
        return _err(exc)
    try:
        with session_scope() as db:
            result = outreach_service.send_follow_up(db, lane_id, req, request_id)
    except ValueError as exc:
        msg = str(exc)
        if msg == "lane_not_found":
            return jsonify({"detail": "Lane not found"}), 404
        if msg == "campaign_ended":
            return jsonify({"detail": "Campaign has ended. Cannot send follow-up."}), 409
        if msg == "no_batch":
            return jsonify({"detail": "No outreach has been sent for this lane yet."}), 409
        if msg == "no_eligible_recipients":
            return jsonify({"detail": "All carriers have already replied."}), 409
        raise
    return jsonify(result.model_dump(mode="json")), 201


@outreach_bp.post("/lanes/<uuid:lane_id>/outreach/end")
def outreach_end(lane_id: uuid.UUID):
    payload = request.get_json(silent=True) or {}
    request_id = getattr(g, "correlation_id", "")
    try:
        req = EndCampaignRequest.model_validate(payload)
    except ValidationError as exc:
        return _err(exc)
    try:
        with session_scope() as db:
            result = outreach_service.end_campaign(db, lane_id, req, request_id)
    except ValueError as exc:
        if str(exc) == "lane_not_found":
            return jsonify({"detail": "Lane not found"}), 404
        raise
    return jsonify(result), 200


@outreach_bp.get("/lanes/<uuid:lane_id>/outreach")
def get_outreach_metrics(lane_id: uuid.UUID):
    exclude_test = request.args.get("include_test", "false").lower() != "true"
    with session_scope() as db:
        result = outreach_metrics.lane_metrics(db, lane_id, exclude_test=exclude_test)
    return jsonify(result.model_dump(mode="json")), 200


@outreach_bp.get("/lanes/<uuid:lane_id>/outreach/export")
def export_outreach_rows(lane_id: uuid.UUID):
    import json as _json
    include_internal = request.args.get("include_internal", "true").lower() != "false"
    include_dat = request.args.get("include_dat", "true").lower() != "false"
    include_crr_model = request.args.get("include_crr_model", "true").lower() != "false"
    raw_limits = request.args.get("source_limits", "")
    source_limits: dict[str, int] | None = None
    if raw_limits:
        try:
            source_limits = {k: int(v) for k, v in _json.loads(raw_limits).items()}
        except Exception:
            pass

    with session_scope() as db:
        result = outreach_service.export_outreach_rows(
            db, lane_id,
            include_internal=include_internal,
            include_dat=include_dat,
            include_crr_model=include_crr_model,
            source_limits=source_limits,
        )
    return jsonify(result), 200


@outreach_bp.get("/lanes/<uuid:lane_id>/outreach/thread")
def get_carrier_thread(lane_id: uuid.UUID):
    email = request.args.get("email", "").strip()
    if not email:
        return jsonify({"detail": "email parameter required"}), 400
    try:
        with session_scope() as db:
            result = outreach_service.get_carrier_thread(db, lane_id, email)
    except Exception as exc:
        logger.exception("outreach.thread.error", email=email, error=str(exc))
        return jsonify({"detail": "Failed to load thread"}), 500
    return jsonify(result.model_dump(mode="json")), 200


@outreach_bp.post("/lanes/<uuid:lane_id>/outreach/carrier-reply")
def send_carrier_reply(lane_id: uuid.UUID):
    payload = request.get_json(silent=True) or {}
    request_id = getattr(g, "correlation_id", "")
    try:
        req = CarrierReplyRequest.model_validate(payload)
    except ValidationError as exc:
        return _err(exc)
    try:
        with session_scope() as db:
            result = outreach_service.send_carrier_reply(db, lane_id, req, request_id)
    except ValueError as exc:
        msg = str(exc)
        if msg == "lane_not_found":
            return jsonify({"detail": "Lane not found"}), 404
        if msg == "send_failed":
            return jsonify({"detail": "Failed to send reply email."}), 500
        raise
    return jsonify(result), 200
