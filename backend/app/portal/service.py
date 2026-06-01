from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.db.models import (
    PortalCarrierCRMSnapshot,
    PortalLane,
    PortalLaneActivityEvent,
    PortalLaneMetricsSnapshot,
    PortalLaneStop,
)
from app.portal import dummy_generator
from app.portal.schemas import LaneCreateRequest

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_label(lane: PortalLane) -> str:
    return f"{lane.origin_city}, {lane.origin_state} → {lane.destination_city}, {lane.destination_state}"


# ---------------------------------------------------------------------------
# Compound return types
# ---------------------------------------------------------------------------


@dataclass
class LaneListItem:
    lane: PortalLane
    metrics: PortalLaneMetricsSnapshot | None
    last_activity_at: datetime


@dataclass
class LaneDetail:
    lane: PortalLane
    stops: list[PortalLaneStop]
    metrics: PortalLaneMetricsSnapshot | None
    timeline: list[PortalLaneActivityEvent]


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


def create_lane(db: Session, req: LaneCreateRequest) -> PortalLane:
    now = _utcnow()
    lane_id = uuid.uuid4()

    lane = PortalLane(
        id=lane_id,
        origin_city=req.origin_city,
        origin_state=req.origin_state,
        origin_zip=req.origin_zip,
        destination_city=req.destination_city,
        destination_state=req.destination_state,
        destination_zip=req.destination_zip,
        equipment_type=req.equipment_type.value,
        pickup_date=req.pickup_date,
        status="new",
        created_at=now,
        updated_at=now,
    )
    db.add(lane)
    db.flush()

    for i, stop in enumerate(req.stops):
        db.add(
            PortalLaneStop(
                id=uuid.uuid4(),
                lane_id=lane_id,
                stop_order=i,
                city=stop.city,
                state=stop.state,
                zip=stop.zip,
            )
        )

    metrics_data = dummy_generator.generate_metrics(lane_id)
    db.add(
        PortalLaneMetricsSnapshot(
            id=uuid.uuid4(),
            lane_id=lane_id,
            generated_at=now,
            **metrics_data,
        )
    )

    for event in dummy_generator.generate_timeline(lane_id, now):
        db.add(
            PortalLaneActivityEvent(
                id=uuid.uuid4(),
                lane_id=lane_id,
                **event,
            )
        )

    for carrier in dummy_generator.generate_carrier_crm(lane_id, now):
        db.add(
            PortalCarrierCRMSnapshot(
                id=uuid.uuid4(),
                lane_id=lane_id,
                **carrier,
            )
        )

    db.commit()
    db.refresh(lane)
    logger.info("lane_created", lane_id=str(lane_id), label=make_label(lane))
    return lane


def list_lanes(db: Session) -> list[LaneListItem]:
    lanes = db.query(PortalLane).order_by(PortalLane.created_at.desc()).all()
    result: list[LaneListItem] = []
    for lane in lanes:
        metrics = (
            db.query(PortalLaneMetricsSnapshot).filter_by(lane_id=lane.id).first()
        )
        last_event = (
            db.query(PortalLaneActivityEvent)
            .filter_by(lane_id=lane.id)
            .order_by(PortalLaneActivityEvent.event_at.desc())
            .first()
        )
        last_at = last_event.event_at if last_event else lane.created_at
        result.append(LaneListItem(lane=lane, metrics=metrics, last_activity_at=last_at))
    return result


def get_lane_detail(db: Session, lane_id: uuid.UUID) -> LaneDetail | None:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        return None
    stops = (
        db.query(PortalLaneStop)
        .filter_by(lane_id=lane_id)
        .order_by(PortalLaneStop.stop_order)
        .all()
    )
    metrics = db.query(PortalLaneMetricsSnapshot).filter_by(lane_id=lane_id).first()
    timeline = (
        db.query(PortalLaneActivityEvent)
        .filter_by(lane_id=lane_id)
        .order_by(PortalLaneActivityEvent.sort_order)
        .all()
    )
    return LaneDetail(lane=lane, stops=stops, metrics=metrics, timeline=timeline)


def get_carrier_crm(
    db: Session, lane_id: uuid.UUID
) -> list[PortalCarrierCRMSnapshot] | None:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        return None
    return (
        db.query(PortalCarrierCRMSnapshot)
        .filter_by(lane_id=lane_id)
        .order_by(PortalCarrierCRMSnapshot.response_rate.desc())
        .all()
    )
