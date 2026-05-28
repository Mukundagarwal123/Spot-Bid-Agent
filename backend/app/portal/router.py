from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.portal import service
from app.portal.schemas import (
    CarrierCRMItem,
    CarrierCRMResponse,
    LaneCreatedResponse,
    LaneDetailResponse,
    LaneInfo,
    LanesListResponse,
    LaneSummary,
    LaneCreateRequest,
    MetricsPreview,
    MetricsSnapshot,
    StopInfo,
    TimelineEvent,
)

router = APIRouter(prefix="/portal", tags=["portal"])
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


@router.post("/lanes", status_code=201, response_model=LaneCreatedResponse)
def create_lane(
    req: LaneCreateRequest, db: Session = Depends(get_db)
) -> LaneCreatedResponse:
    lane = service.create_lane(db, req)
    return LaneCreatedResponse(
        lane_id=lane.id,
        label=service.make_label(lane),
        status=lane.status,
        created_at=lane.created_at,
    )


@router.get("/lanes", response_model=LanesListResponse)
def list_lanes(db: Session = Depends(get_db)) -> LanesListResponse:
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
    return LanesListResponse(lanes=summaries)


@router.get("/lanes/{lane_id}", response_model=LaneDetailResponse)
def get_lane(lane_id: uuid.UUID, db: Session = Depends(get_db)) -> LaneDetailResponse:
    detail = service.get_lane_detail(db, lane_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Lane not found")

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

    return LaneDetailResponse(
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


@router.get("/lanes/{lane_id}/carrier-crm", response_model=CarrierCRMResponse)
def get_carrier_crm(
    lane_id: uuid.UUID, db: Session = Depends(get_db)
) -> CarrierCRMResponse:
    carriers = service.get_carrier_crm(db, lane_id)
    if carriers is None:
        raise HTTPException(status_code=404, detail="Lane not found")
    return CarrierCRMResponse(
        carriers=[CarrierCRMItem.model_validate(c) for c in carriers]
    )
