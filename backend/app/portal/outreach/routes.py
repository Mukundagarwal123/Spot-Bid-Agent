from __future__ import annotations

import uuid

import structlog
from flask import Blueprint, g, jsonify, request
from pydantic import ValidationError

from app.db.base import session_scope
from app.portal.outreach import metrics as outreach_metrics
from app.portal.outreach import service as outreach_service
from app.portal.outreach.schemas import OutreachRequest

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
            return jsonify({"detail": "No ready outreach set found for this lane. Build one first."}), 409
        if msg == "no_valid_recipients":
            return jsonify({"detail": "No valid email addresses found for the selected sources."}), 422
        raise

    return jsonify(result.model_dump(mode="json")), 201


@outreach_bp.get("/lanes/<uuid:lane_id>/outreach")
def get_outreach_metrics(lane_id: uuid.UUID):
    exclude_test = request.args.get("include_test", "false").lower() != "true"
    with session_scope() as db:
        result = outreach_metrics.lane_metrics(db, lane_id, exclude_test=exclude_test)
    return jsonify(result.model_dump(mode="json")), 200
