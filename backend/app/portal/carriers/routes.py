from __future__ import annotations

import structlog
from flask import Blueprint, g, jsonify, request
from pydantic import ValidationError

from app.portal.carriers.schemas import CarrierRecommendationRequest
from app.portal.carriers.service import get_internal_turvo_recommendations

carriers_api_bp = Blueprint("carriers_api", __name__)
log = structlog.get_logger(__name__)


@carriers_api_bp.post("/portal/carriers/recommendations/internal-turvo")
def recommend_internal_turvo():
    request_id: str = getattr(g, "correlation_id", "")
    body = request.get_json(silent=True) or {}
    log.info(
        "carrier.request.received",
        request_id=request_id,
        origin_city=body.get("origin_city"),
        origin_state=body.get("origin_state"),
        origin_zip=body.get("origin_zip"),
        destination_city=body.get("destination_city"),
        destination_state=body.get("destination_state"),
        destination_zip=body.get("destination_zip"),
        source="turvo_internal",
    )

    field_errors: dict[str, str] = {}
    if not str(body.get("origin_zip", "")).strip():
        field_errors["origin_zip"] = "origin_zip is required"
    if not str(body.get("destination_zip", "")).strip():
        field_errors["destination_zip"] = "destination_zip is required"
    if field_errors:
        log.warning(
            "carrier.request.validation_failed",
            request_id=request_id,
            error_fields=sorted(field_errors),
            source="turvo_internal",
        )
        return (
            jsonify({"request_id": request_id, "error": "validation_error", "fields": field_errors}),
            400,
        )

    try:
        req = CarrierRecommendationRequest.model_validate(body)
    except ValidationError as exc:
        fields = {e["loc"][0]: e["msg"] for e in exc.errors() if e.get("loc")}
        log.warning(
            "carrier.request.validation_failed",
            request_id=request_id,
            error_fields=sorted(fields),
            source="turvo_internal",
        )
        return (
            jsonify({"request_id": request_id, "error": "validation_error", "fields": fields}),
            400,
        )

    response = get_internal_turvo_recommendations(req, request_id=request_id)
    log.info(
        "carrier.request.completed",
        request_id=request_id,
        carrier_count=len(response.carriers),
        source="turvo_internal",
    )
    return jsonify(response.model_dump()), 200
