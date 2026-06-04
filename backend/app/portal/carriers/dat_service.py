from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.models import PortalLane, PortalLaneCarrierRecord, PortalLaneCarrierSource
from app.portal.carriers.dat_schemas import CarrierRecordItem, CarrierRecordsResponse, DatImportResponse
from app.portal.carriers.source_2_dat.parser import DatParseError, parse_dat_text

# Avoid circular import — CarrierResult is imported lazily inside the function
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.portal.carriers.schemas import CarrierResult

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_dat_import(
    db: Session,
    lane_id: uuid.UUID,
    raw_text: str,
    request_id: str = "",
) -> DatImportResponse:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")

    logger.info("dat_import_received", lane_id=str(lane_id), request_id=request_id, source="dat")
    logger.info("dat_parse_started", lane_id=str(lane_id), request_id=request_id, source="dat")

    rows = parse_dat_text(raw_text, settings)

    logger.info(
        "dat_parse_completed",
        lane_id=str(lane_id),
        parsed_count=len(rows),
        request_id=request_id,
        source="dat",
    )

    now = _utcnow()
    source_id = uuid.uuid4()

    source = PortalLaneCarrierSource(
        id=source_id,
        lane_id=lane_id,
        source_type="dat",
        raw_payload=raw_text,
        parsed_count=len(rows),
        status="ok",
        created_at=now,
    )
    db.add(source)
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

    return CarrierRecordsResponse(lane_id=str(lane_id), sources=grouped)
