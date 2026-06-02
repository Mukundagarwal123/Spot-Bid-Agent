from __future__ import annotations

import uuid

import structlog
from flask import Blueprint, g, jsonify, request
from pydantic import ValidationError

from app.db.base import session_scope
from app.portal import service
from app.portal.carriers.schemas import CarrierRecommendationRequest
from app.portal.carriers.service import get_internal_turvo_recommendations
from app.portal.schemas import (
    CarrierCRMItem,
    CarrierCRMResponse,
    LaneCreateRequest,
    LaneCreatedResponse,
    LaneDetailResponse,
    LaneInfo,
    LanesListResponse,
    LaneSummary,
    MetricsPreview,
    MetricsSnapshot,
    StopInfo,
    TimelineEvent,
)

portal_api_bp = Blueprint("portal_api", __name__, url_prefix="/portal")
logger = structlog.get_logger(__name__)

_ZERO_METRICS = MetricsSnapshot(
    emails_sent=0,
    emails_clicked=0,
    email_replies=0,
    sms_sent=0,
    sms_replies=0,
    whatsapp_sent=0,
    whatsapp_replies=0,
    carriers_contacted=0,
    carriers_responded=0,
)


def _validation_error(exc: ValidationError):
    return jsonify({"detail": exc.errors()}), 422


@portal_api_bp.post("/lanes")
def create_lane():
    payload = request.get_json(silent=True) or {}
    logger.info(
        "lane.create.request_received",
        origin_city=payload.get("origin_city"),
        origin_state=payload.get("origin_state"),
        origin_zip=payload.get("origin_zip"),
        destination_city=payload.get("destination_city"),
        destination_state=payload.get("destination_state"),
        destination_zip=payload.get("destination_zip"),
        source="source_1_internal_turvo",
    )
    try:
        req = LaneCreateRequest.model_validate(payload)
    except ValidationError as exc:
        return _validation_error(exc)

    missing_fields: list[str] = []
    if not req.origin_zip:
        missing_fields.append("origin_zip")
    if not req.destination_zip:
        missing_fields.append("destination_zip")
    if missing_fields:
        logger.warning(
            "lane.create.validation_failed",
            missing_fields=missing_fields,
            source="source_1_internal_turvo",
        )
        return (
            jsonify(
                {
                    "detail": [
                        {
                            "loc": ["body", field],
                            "msg": f"{field} is required",
                            "type": "value_error",
                        }
                        for field in missing_fields
                    ]
                }
            ),
            422,
        )

    logger.info(
        "lane.create.validated",
        origin_city=req.origin_city,
        origin_state=req.origin_state,
        origin_zip=req.origin_zip,
        destination_city=req.destination_city,
        destination_state=req.destination_state,
        destination_zip=req.destination_zip,
        source="source_1_internal_turvo",
    )

    with session_scope() as db:
        lane = service.create_lane(db, req)
        response = LaneCreatedResponse(
            lane_id=lane.id,
            label=service.make_label(lane),
            status=lane.status,
            created_at=lane.created_at,
        )

    if lane.origin_zip and lane.destination_zip:
        request_id = getattr(g, "correlation_id", "")
        carrier_request = CarrierRecommendationRequest(
            origin_city=lane.origin_city,
            origin_state=lane.origin_state,
            origin_zip=lane.origin_zip,
            destination_city=lane.destination_city,
            destination_state=lane.destination_state,
            destination_zip=lane.destination_zip,
        )
        try:
            carrier_response = get_internal_turvo_recommendations(carrier_request, request_id=request_id)
            logger.info(
                "lane.source_1_carriers_loaded",
                lane_id=str(lane.id),
                request_id=request_id,
                carrier_count=len(carrier_response.carriers),
                source="turvo_internal",
            )
        except Exception as exc:
            logger.warning(
                "lane.source_1_carriers_failed",
                lane_id=str(lane.id),
                request_id=request_id,
                error=str(exc),
                source="turvo_internal",
            )
    else:
        logger.info(
            "lane.source_1_skipped_missing_zip",
            lane_id=str(lane.id),
            origin_zip=lane.origin_zip,
            destination_zip=lane.destination_zip,
            source="turvo_internal",
        )
    return jsonify(response.model_dump(mode="json")), 201


@portal_api_bp.get("/lanes")
def list_lanes():
    with session_scope() as db:
        items = service.list_lanes(db)
        summaries = [
            LaneSummary(
                lane_id=item.lane.id,
                label=service.make_label(item.lane),
                equipment_type=item.lane.equipment_type,
                status=item.lane.status,
                last_activity_at=item.last_activity_at,
                pickup_date=item.lane.pickup_date,
                metrics_preview=MetricsPreview(
                    carriers_contacted=item.metrics.carriers_contacted if item.metrics else 0,
                    carriers_responded=item.metrics.carriers_responded if item.metrics else 0,
                ),
            )
            for item in items
        ]
        logger.debug("lanes_listed", count=len(summaries))
        response = LanesListResponse(lanes=summaries)
    return jsonify(response.model_dump(mode="json"))


@portal_api_bp.get("/lanes/<uuid:lane_id>")
def get_lane(lane_id: uuid.UUID):
    with session_scope() as db:
        detail = service.get_lane_detail(db, lane_id)
        if detail is None:
            return jsonify({"detail": "Lane not found"}), 404

        m = detail.metrics
        metrics = (
            MetricsSnapshot(
                emails_sent=m.emails_sent,
                emails_clicked=m.emails_clicked,
                email_replies=m.email_replies,
                sms_sent=m.sms_sent,
                sms_replies=m.sms_replies,
                whatsapp_sent=m.whatsapp_sent,
                whatsapp_replies=m.whatsapp_replies,
                carriers_contacted=m.carriers_contacted,
                carriers_responded=m.carriers_responded,
            )
            if m
            else _ZERO_METRICS
        )

        response = LaneDetailResponse(
            lane=LaneInfo(
                lane_id=detail.lane.id,
                label=service.make_label(detail.lane),
                origin_city=detail.lane.origin_city,
                origin_state=detail.lane.origin_state,
                origin_zip=detail.lane.origin_zip,
                destination_city=detail.lane.destination_city,
                destination_state=detail.lane.destination_state,
                destination_zip=detail.lane.destination_zip,
                equipment_type=detail.lane.equipment_type,
                pickup_date=detail.lane.pickup_date,
                status=detail.lane.status,
                created_at=detail.lane.created_at,
            ),
            stops=[
                StopInfo(stop_order=s.stop_order, city=s.city, state=s.state, zip=s.zip)
                for s in detail.stops
            ],
            metrics=metrics,
            timeline=[
                TimelineEvent(
                    event_type=e.event_type,
                    label=e.label,
                    timestamp=e.event_at,
                    channel=e.channel,
                )
                for e in detail.timeline
            ],
        )
    return jsonify(response.model_dump(mode="json"))


@portal_api_bp.get("/lanes/<uuid:lane_id>/carrier-crm")
def get_carrier_crm(lane_id: uuid.UUID):
    with session_scope() as db:
        carriers = service.get_carrier_crm(db, lane_id)
        if carriers is None:
            return jsonify({"detail": "Lane not found"}), 404
        response = CarrierCRMResponse(
            carriers=[CarrierCRMItem.model_validate(c) for c in carriers]
        )
    return jsonify(response.model_dump(mode="json"))
