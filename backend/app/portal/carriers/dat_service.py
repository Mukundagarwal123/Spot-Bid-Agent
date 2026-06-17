from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.models import CarrierRelevancyRecord, CarrierRelevancyRun, PortalLane, PortalLaneCarrierRecord, PortalLaneCarrierSource
import json as _json

from app.portal.carriers.dat_schemas import CarrierRecordItem, CarrierRecordsResponse, DatImportResponse
from app.portal.carriers.source_2_dat.parser import DatParseError, parse_lanemakers, parse_truck_postings

# Avoid circular import — CarrierResult is imported lazily inside the function
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.portal.carriers.schemas import CarrierResult

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_pending_dat_source(
    db: Session,
    lane_id: uuid.UUID,
    truck_postings_text: str,
    lanemakers_text: str,
) -> uuid.UUID:
    """Write a 'pending' source record immediately so the UI knows DAT is processing."""
    source_id = uuid.uuid4()
    raw_payload = _json.dumps({
        "truck_postings": truck_postings_text,
        "lanemakers": lanemakers_text,
    })
    db.add(
        PortalLaneCarrierSource(
            id=source_id,
            lane_id=lane_id,
            source_type="dat",
            raw_payload=raw_payload,
            parsed_count=0,
            status="pending",
            created_at=_utcnow(),
        )
    )
    db.commit()
    return source_id


def create_dat_import(
    db: Session,
    lane_id: uuid.UUID,
    truck_postings_text: str,
    lanemakers_text: str,
    request_id: str = "",
    source_id: uuid.UUID | None = None,
) -> DatImportResponse:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")

    logger.info("dat_import_received", lane_id=str(lane_id), request_id=request_id, source="dat")
    logger.info("dat_parse_started", lane_id=str(lane_id), request_id=request_id, source="dat")

    try:
        rows = []
        if truck_postings_text.strip():
            rows.extend(parse_truck_postings(truck_postings_text, settings))
        if lanemakers_text.strip():
            rows.extend(parse_lanemakers(lanemakers_text, settings))
    except Exception as exc:
        if source_id:
            src = db.query(PortalLaneCarrierSource).filter_by(id=source_id).first()
            if src:
                src.status = "error"
                db.commit()
        raise

    logger.info(
        "dat_parse_completed",
        lane_id=str(lane_id),
        parsed_count=len(rows),
        request_id=request_id,
        source="dat",
    )

    now = _utcnow()
    if source_id is None:
        source_id = uuid.uuid4()

    # If we pre-created a pending source, update it; otherwise insert fresh
    existing_source = db.query(PortalLaneCarrierSource).filter_by(id=source_id).first()
    if existing_source:
        existing_source.parsed_count = len(rows)
        existing_source.status = "ok"
        db.flush()
    else:
        source_id = uuid.uuid4()
        raw_payload = _json.dumps({
            "truck_postings": truck_postings_text,
            "lanemakers": lanemakers_text,
        })
        db.add(
            PortalLaneCarrierSource(
                id=source_id,
                lane_id=lane_id,
                source_type="dat",
                raw_payload=raw_payload,
                parsed_count=len(rows),
                status="ok",
                created_at=now,
            )
        )
        db.flush()

    for row in rows:
        db.add(
            PortalLaneCarrierRecord(
                id=uuid.uuid4(),
                lane_id=lane_id,
                source_id=source_id,
                source_type="dat",
                carrier_name=row.carrier_name,
                email=row.email,
                phone=row.phone,
                mc_number=row.mc_number,
                source_notes=row.source_notes,
                created_at=now,
            )
        )

    db.commit()
    logger.info(
        "dat_import_stored",
        lane_id=str(lane_id),
        created_count=len(rows),
        request_id=request_id,
        source="dat",
    )

    return DatImportResponse(
        lane_id=str(lane_id),
        source="dat",
        parsed_count=len(rows),
        created_count=len(rows),
        status="ok",
    )


def save_internal_carriers(
    db: Session,
    lane_id: uuid.UUID,
    carriers: list,
) -> None:
    """Persist internal Turvo carrier results into portal_lane_carrier_records."""
    if not carriers:
        return

    now = _utcnow()
    source_id = uuid.uuid4()

    db.add(
        PortalLaneCarrierSource(
            id=source_id,
            lane_id=lane_id,
            source_type="internal",
            raw_payload=None,
            parsed_count=len(carriers),
            status="ok",
            created_at=now,
        )
    )
    db.flush()

    for c in carriers:
        db.add(
            PortalLaneCarrierRecord(
                id=uuid.uuid4(),
                lane_id=lane_id,
                source_id=source_id,
                source_type="internal",
                carrier_name=c.carrier_name,
                email=c.email or "",
                phone=c.phone or "",
                mc_number=c.mc_number or "",
                source_notes=f"rank:{c.match_rank} | {c.status}",
                created_at=now,
            )
        )

    db.commit()
    logger.info("internal_carriers_stored", lane_id=str(lane_id), count=len(carriers), source="internal")


def get_carrier_records(
    db: Session,
    lane_id: uuid.UUID,
    source_type: str | None = None,
) -> CarrierRecordsResponse | None:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        return None

    q = db.query(PortalLaneCarrierRecord).filter(
        PortalLaneCarrierRecord.lane_id == lane_id
    )
    if source_type:
        q = q.filter(PortalLaneCarrierRecord.source_type == source_type)

    records = q.order_by(PortalLaneCarrierRecord.created_at).all()

    grouped: dict[str, list[CarrierRecordItem]] = {"internal": [], "dat": []}
    for r in records:
        item = CarrierRecordItem(
            id=str(r.id),
            carrier_name=r.carrier_name,
            email=r.email,
            phone=r.phone,
            mc_number=r.mc_number,
            source_notes=r.source_notes,
            source_type=r.source_type,
            created_at=r.created_at.isoformat(),
        )
        if r.source_type not in grouped:
            grouped[r.source_type] = []
        grouped[r.source_type].append(item)

    # Source 3: FreightX records from carrier_relevancy_records
    latest_run = (
        db.query(CarrierRelevancyRun)
        .filter_by(lane_id=lane_id)
        .order_by(CarrierRelevancyRun.created_at.desc())
        .first()
    )
    if latest_run:
        fx_records = (
            db.query(CarrierRelevancyRecord)
            .filter_by(run_id=latest_run.id)
            .order_by(CarrierRelevancyRecord.rank)
            .all()
        )
        grouped["freightx"] = [
            CarrierRecordItem(
                id=str(r.id),
                carrier_name=r.legal_name or "",
                email=r.email_address or "",
                phone=r.phone or "",
                mc_number=r.docket_number or "",
                source_notes=f"Rank {r.rank} | Label: {r.label}" if r.label else f"Rank {r.rank}",
                source_type="freightx",
                created_at=r.created_at.isoformat(),
            )
            for r in fx_records
        ]

    return CarrierRecordsResponse(lane_id=str(lane_id), sources=grouped)
