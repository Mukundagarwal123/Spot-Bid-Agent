from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

import structlog
from sqlalchemy.orm import Session

from app.db.models import (
    OutreachBatch,
    OutreachMessage,
    PortalCarrierCRMSnapshot,
    PortalLane,
    PortalLaneActivityEvent,
    PortalLaneMetricsSnapshot,
    PortalLaneStop,
)
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
        notes=req.notes or None,
        campaign_config_json=json.dumps({
            "sources": {
                "internal": req.include_internal,
                "dat": req.include_dat,
                "crr_model": req.include_crr_model,
                "manual": bool(req.manual_recipients),
            },
            "channels": {
                "email": "email" in req.channels,
                "whatsapp": "whatsapp" in req.channels,
            },
            "manual_recipients": req.manual_recipients,
            "whatsapp_source_types": req.whatsapp_source_types,
        }),
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

    db.commit()
    db.refresh(lane)
    logger.info("lane_created", lane_id=str(lane_id), label=make_label(lane))
    return lane


def list_lanes(db: Session) -> list[LaneListItem]:
    lanes = db.query(PortalLane).order_by(PortalLane.created_at.desc()).all()
    result: list[LaneListItem] = []
    for lane in lanes:
        metrics = db.query(PortalLaneMetricsSnapshot).filter_by(lane_id=lane.id).first()

        # For new lanes (no dummy snapshot), derive preview counts from live outreach data.
        if metrics is None:
            metrics = _live_metrics_snapshot(db, lane.id, now=lane.created_at)

        last_event = (
            db.query(PortalLaneActivityEvent)
            .filter_by(lane_id=lane.id)
            .order_by(PortalLaneActivityEvent.event_at.desc())
            .first()
        )
        last_at = last_event.event_at if last_event else lane.updated_at
        result.append(LaneListItem(lane=lane, metrics=metrics, last_activity_at=last_at))
    return result


def _live_metrics_snapshot(
    db: Session, lane_id: uuid.UUID, now: datetime
) -> PortalLaneMetricsSnapshot | None:
    """Build a transient metrics snapshot from live outreach data (not persisted)."""
    batch = (
        db.query(OutreachBatch)
        .filter(OutreachBatch.lane_id == lane_id, OutreachBatch.test_mode.is_(False))
        .order_by(OutreachBatch.created_at.desc())
        .first()
    )
    if batch is None:
        return None
    messages = db.query(OutreachMessage).filter(OutreachMessage.batch_id == batch.id).all()
    sent = len(messages)
    replied = sum(1 for m in messages if m.replied_at)
    return SimpleNamespace(
        carriers_contacted=sent,
        carriers_responded=replied,
        emails_sent=sent,
        emails_clicked=sum(1 for m in messages if m.clicked_at),
        email_replies=replied,
        sms_sent=0,
        sms_replies=0,
        whatsapp_sent=0,
        whatsapp_replies=0,
        generated_at=now,
    )


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
