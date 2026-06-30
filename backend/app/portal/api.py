from __future__ import annotations

import json
import threading
import uuid

import structlog
from flask import Blueprint, current_app, g, jsonify, request
from pydantic import ValidationError

from sqlalchemy import func

from app.db.base import session_scope
from app.db.models import CarrierRelevancyRun, PortalLane, PortalLaneCarrierRecord, PortalLaneCarrierSource
from app.portal import service
from app.portal.carriers import dat_service
from app.portal.carriers.dat_schemas import DatImportRequest
from app.portal.carriers.freightx_schemas import FreightXRelevancyRequest
from app.portal.carriers.schemas import CarrierRecommendationRequest
from app.portal.carriers.service import get_internal_turvo_recommendations
from app.portal.carriers.aggregation import service as aggregation_service
from app.portal.carriers.aggregation.schemas import OutreachRowResponse, OutreachSetRequest, OutreachSetResponse
from app.portal.carriers.source_3_freightx import service as freightx_service
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


def _run_background(fn, *args, **kwargs) -> None:
    """Run fn(*args, **kwargs) in a daemon thread with the Flask app context."""
    app = current_app._get_current_object()

    def _wrapper():
        with app.app_context():
            try:
                fn(*args, **kwargs)
            except Exception as exc:
                logger.error("background_task_error", task=fn.__name__, error=str(exc))

    threading.Thread(target=_wrapper, daemon=True).start()


def _bg_fetch_internal_carriers(
    lane_id_str: str,
    carrier_request: CarrierRecommendationRequest,
    request_id: str,
) -> None:
    carrier_response = get_internal_turvo_recommendations(carrier_request, request_id=request_id)
    logger.info(
        "lane.source_1_carriers_loaded",
        lane_id=lane_id_str,
        request_id=request_id,
        carrier_count=len(carrier_response.carriers),
        source="turvo_internal",
    )
    if carrier_response.carriers:
        with session_scope() as db:
            dat_service.save_internal_carriers(
                db, uuid.UUID(lane_id_str), carrier_response.carriers
            )


def _bg_process_dat_import(
    lane_id: uuid.UUID,
    truck_postings_text: str,
    lanemakers_text: str,
    request_id: str,
    source_id: uuid.UUID | None = None,
) -> None:
    with session_scope() as db:
        dat_service.create_dat_import(db, lane_id, truck_postings_text, lanemakers_text, request_id, source_id)


_PORTAL_TO_FREIGHTX_EQUIP = {"dry_van": "dryvan"}
_FREIGHTX_SUPPORTED_EQUIP = {"dryvan", "reefer", "flatbed"}


def _bg_fetch_internal_carriers_rerun(
    lane_id_str: str,
    carrier_request: CarrierRecommendationRequest,
    filter_mode: str,
    request_id: str,
) -> None:
    carrier_response = get_internal_turvo_recommendations(
        carrier_request, request_id=request_id, filter_mode=filter_mode
    )
    logger.info(
        "lane.source_1_carriers_reloaded",
        lane_id=lane_id_str,
        request_id=request_id,
        carrier_count=len(carrier_response.carriers),
        filter_mode=filter_mode,
        source="turvo_internal",
    )
    if carrier_response.carriers:
        with session_scope() as db:
            dat_service.save_internal_carriers(
                db, uuid.UUID(lane_id_str), carrier_response.carriers
            )


def _bg_run_freightx_relevancy(
    lane_id_str: str,
    origin_zip: str,
    destination_zip: str,
    equipment_type: str,
    request_id: str,
) -> None:
    normalized_equip = _PORTAL_TO_FREIGHTX_EQUIP.get(equipment_type, equipment_type)
    if normalized_equip not in _FREIGHTX_SUPPORTED_EQUIP:
        logger.info(
            "lane.source_3_skipped_unsupported_equipment",
            lane_id=lane_id_str,
            equipment_type=equipment_type,
            source="freightx_relevancy",
        )
        return

    with session_scope() as db:
        result = freightx_service.run_freightx_relevancy(
            db=db,
            lane_id=uuid.UUID(lane_id_str),
            origin_zip=origin_zip,
            dest_zip=destination_zip,
            equipment_type=normalized_equip,
            request_id=request_id,
        )
    logger.info(
        "lane.source_3_carriers_loaded",
        lane_id=lane_id_str,
        request_id=request_id,
        row_count=result.row_count,
        status=result.status,
        source="freightx_relevancy",
    )

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
    return jsonify({"detail": json.loads(exc.json())}), 422


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

    request_id = getattr(g, "correlation_id", "")

    with session_scope() as db:
        lane = service.create_lane(db, req)
        response = LaneCreatedResponse(
            lane_id=lane.id,
            label=service.make_label(lane),
            status=lane.status,
            notes=lane.notes,
            created_at=lane.created_at,
        )

    if lane.origin_zip and lane.destination_zip:
        carrier_request = CarrierRecommendationRequest(
            origin_city=lane.origin_city,
            origin_state=lane.origin_state,
            origin_zip=lane.origin_zip,
            destination_city=lane.destination_city,
            destination_state=lane.destination_state,
            destination_zip=lane.destination_zip,
        )
        if req.include_internal:
            _run_background(_bg_fetch_internal_carriers, str(lane.id), carrier_request, request_id)
            logger.info("lane.source_1_carriers_queued", lane_id=str(lane.id), source="turvo_internal")
        else:
            logger.info("lane.source_1_skipped_user_deselected", lane_id=str(lane.id), source="turvo_internal")

        if req.include_crr_model:
            _run_background(
                _bg_run_freightx_relevancy,
                str(lane.id),
                lane.origin_zip,
                lane.destination_zip,
                lane.equipment_type,
                request_id,
            )
            logger.info("lane.source_3_carriers_queued", lane_id=str(lane.id), source="freightx_relevancy")
        else:
            logger.info("lane.source_3_skipped_user_deselected", lane_id=str(lane.id), source="freightx_relevancy")
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
                created_at=item.lane.created_at,
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


@portal_api_bp.get("/lanes/<uuid:lane_id>/carriers/counts")
def get_carrier_counts(lane_id: uuid.UUID):
    """Return stored carrier counts per source — instant DB query, no model re-run."""
    with session_scope() as db:
        rows = (
            db.query(
                PortalLaneCarrierRecord.source_type,
                func.count().label("total"),
            )
            .filter(PortalLaneCarrierRecord.lane_id == lane_id)
            .group_by(PortalLaneCarrierRecord.source_type)
            .all()
        )
        counts: dict[str, int] = {r.source_type: r.total for r in rows}

        # Check for a DAT import that is still processing (pending status)
        dat_pending = db.query(PortalLaneCarrierSource).filter_by(
            lane_id=lane_id, source_type="dat", status="pending"
        ).first() is not None

        # CRR model: use row_count from the latest run (pre-computed)
        latest_run = (
            db.query(CarrierRelevancyRun)
            .filter_by(lane_id=lane_id)
            .order_by(CarrierRelevancyRun.created_at.desc())
            .first()
        )
        if latest_run and latest_run.row_count > 0:
            counts["crr_model"] = latest_run.row_count

    return jsonify({**counts, "dat_pending": dat_pending})


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
                notes=detail.lane.notes,
                campaign_config=json.loads(detail.lane.campaign_config_json or "{}"),
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


@portal_api_bp.post("/lanes/<uuid:lane_id>/dat-imports")
def create_dat_import(lane_id: uuid.UUID):
    payload = request.get_json(silent=True) or {}
    request_id = getattr(g, "correlation_id", "")

    try:
        req = DatImportRequest.model_validate(payload)
    except ValidationError as exc:
        return _validation_error(exc)

    # Pre-create a 'pending' source record so UI can see DAT is processing
    with session_scope() as db:
        if db.query(PortalLane).filter_by(id=lane_id).first() is None:
            return jsonify({"detail": "Lane not found"}), 404
        source_id = dat_service.create_pending_dat_source(
            db, lane_id, req.truck_postings_text, req.lanemakers_text
        )

    # Fire LLM parsing in background and return immediately
    _run_background(
        _bg_process_dat_import,
        lane_id,
        req.truck_postings_text,
        req.lanemakers_text,
        request_id,
        source_id,
    )
    logger.info("dat_import_queued", lane_id=str(lane_id), request_id=request_id, source="dat")

    return jsonify({"lane_id": str(lane_id), "source": "dat", "status": "processing"}), 202


@portal_api_bp.get("/lanes/<uuid:lane_id>/carrier-records")
def get_carrier_records(lane_id: uuid.UUID):
    source_type = request.args.get("source")
    with session_scope() as db:
        response = dat_service.get_carrier_records(db, lane_id, source_type)
        if response is None:
            return jsonify({"detail": "Lane not found"}), 404
    return jsonify(response.model_dump(mode="json"))


@portal_api_bp.post("/lanes/<uuid:lane_id>/carriers/internal-rerun")
def rerun_internal_carriers(lane_id: uuid.UUID):
    """Re-fetch internal carriers with a chosen filter mode (city_state or state_only)."""
    payload = request.get_json(silent=True) or {}
    request_id = getattr(g, "correlation_id", "")
    filter_mode = str(payload.get("filter_mode", "city_state")).strip()
    if filter_mode not in ("city_state", "state_only"):
        filter_mode = "city_state"

    with session_scope() as db:
        lane = db.query(PortalLane).filter_by(id=lane_id).first()
        if lane is None:
            return jsonify({"detail": "Lane not found"}), 404
        carrier_request = CarrierRecommendationRequest(
            origin_city=lane.origin_city or "",
            origin_state=lane.origin_state or "",
            origin_zip=lane.origin_zip or "",
            destination_city=lane.destination_city or "",
            destination_state=lane.destination_state or "",
            destination_zip=lane.destination_zip or "",
        )

    _run_background(
        _bg_fetch_internal_carriers_rerun,
        str(lane_id),
        carrier_request,
        filter_mode,
        request_id,
    )
    logger.info(
        "lane.source_1_rerun_queued",
        lane_id=str(lane_id),
        filter_mode=filter_mode,
        source="turvo_internal",
    )
    return jsonify({"lane_id": str(lane_id), "filter_mode": filter_mode, "status": "processing"}), 202


@portal_api_bp.post("/lanes/<uuid:lane_id>/freightx-relevancy")
def run_freightx_relevancy(lane_id: uuid.UUID):
    payload = request.get_json(silent=True) or {}
    request_id = getattr(g, "correlation_id", "")

    field_errors: dict[str, str] = {}
    if not str(payload.get("origin_zip", "")).strip():
        field_errors["origin_zip"] = "origin_zip is required"
    if not str(payload.get("destination_zip", "")).strip():
        field_errors["destination_zip"] = "destination_zip is required"
    equip_raw = str(payload.get("equipment_type", "")).strip()
    if not equip_raw:
        field_errors["equipment_type"] = "equipment_type is required"

    if field_errors:
        logger.warning(
            "freightx.request.validation_failed",
            request_id=request_id,
            lane_id=str(lane_id),
            error_fields=sorted(field_errors),
            source="freightx_relevancy",
        )
        return jsonify({"request_id": request_id, "error": "validation_error", "fields": field_errors}), 400

    try:
        req = FreightXRelevancyRequest.model_validate(payload)
    except ValidationError as exc:
        fields = {e["loc"][0]: e["msg"] for e in exc.errors() if e.get("loc")}
        logger.warning(
            "freightx.request.validation_failed",
            request_id=request_id,
            lane_id=str(lane_id),
            error_fields=sorted(fields),
            source="freightx_relevancy",
        )
        return jsonify({"request_id": request_id, "error": "validation_error", "fields": fields}), 400

    logger.info(
        "freightx.request.received",
        request_id=request_id,
        lane_id=str(lane_id),
        origin_zip=req.origin_zip,
        destination_zip=req.destination_zip,
        equipment_type=req.equipment_type,
        source="freightx_relevancy",
    )

    try:
        with session_scope() as db:
            response = freightx_service.run_freightx_relevancy(
                db=db,
                lane_id=lane_id,
                origin_zip=req.origin_zip,
                dest_zip=req.destination_zip,
                equipment_type=req.equipment_type,
                request_id=request_id,
            )
    except ValueError as exc:
        if str(exc) == "lane_not_found":
            return jsonify({"detail": "Lane not found"}), 404
        raise

    status_code = 500 if response.status == "freightx_model_failure" else 200
    return jsonify(response.model_dump(mode="json")), status_code


@portal_api_bp.get("/lanes/<uuid:lane_id>/freightx-relevancy")
def get_freightx_relevancy(lane_id: uuid.UUID):
    with session_scope() as db:
        response = freightx_service.get_freightx_records(db, lane_id)
    if response is None:
        return jsonify({"detail": "Lane not found"}), 404
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


@portal_api_bp.post("/lanes/<uuid:lane_id>/carrier-outreach-sets")
def create_carrier_outreach_set(lane_id: uuid.UUID):
    payload = request.get_json(silent=True) or {}
    request_id = getattr(g, "correlation_id", "")

    try:
        req = OutreachSetRequest.model_validate(payload)
    except ValidationError as exc:
        return _validation_error(exc)

    try:
        with session_scope() as db:
            outreach_set = aggregation_service.build_outreach_set(
                db=db,
                lane_id=lane_id,
                include_internal=req.include_internal,
                include_dat=req.include_dat,
                include_freightx=req.include_freightx,
                request_id=request_id,
            )
    except ValueError as exc:
        if str(exc) == "lane_not_found":
            return jsonify({"detail": "Lane not found"}), 404
        raise

    response = OutreachSetResponse(
        lane_id=str(lane_id),
        outreach_set_id=str(outreach_set.id),
        status=outreach_set.status,
        source_count=outreach_set.source_count,
        row_count=outreach_set.row_count,
        dedupe_count=outreach_set.dedupe_count,
    )
    return jsonify(response.model_dump(mode="json")), 201


@portal_api_bp.get("/lanes/<uuid:lane_id>/carrier-outreach-sets/latest")
def get_latest_carrier_outreach_set(lane_id: uuid.UUID):
    with session_scope() as db:
        if db.query(PortalLane).filter_by(id=lane_id).first() is None:
            return jsonify({"detail": "Lane not found"}), 404
        outreach_set = aggregation_service.get_latest_outreach_set(db, lane_id)
        if outreach_set is None:
            return jsonify({"detail": "No outreach set found for this lane"}), 404
        response = OutreachSetResponse(
            lane_id=str(lane_id),
            outreach_set_id=str(outreach_set.id),
            status=outreach_set.status,
            source_count=outreach_set.source_count,
            row_count=outreach_set.row_count,
            dedupe_count=outreach_set.dedupe_count,
        )
    return jsonify(response.model_dump(mode="json"))


@portal_api_bp.get("/lanes/<uuid:lane_id>/carrier-outreach-sets/<uuid:set_id>/rows")
def get_carrier_outreach_rows(lane_id: uuid.UUID, set_id: uuid.UUID):
    with session_scope() as db:
        if db.query(PortalLane).filter_by(id=lane_id).first() is None:
            return jsonify({"detail": "Lane not found"}), 404
        rows = aggregation_service.get_outreach_rows(db, set_id)
        response = [
            OutreachRowResponse(
                id=str(r.id),
                carrier_name=r.carrier_name,
                phone=r.phone,
                email=r.email,
                mc_number=r.mc_number,
                source=r.source,
                dedupe_key=r.dedupe_key,
                source_row_ids=json.loads(r.source_row_ids or "[]"),
            ).model_dump(mode="json")
            for r in rows
        ]
    return jsonify({"lane_id": str(lane_id), "outreach_set_id": str(set_id), "rows": response})
