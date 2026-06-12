from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.models import CarrierRelevancyRecord, CarrierRelevancyRun, PortalLane
from app.portal.carriers.freightx_schemas import FreightXCarrierRecord, FreightXRelevancyResponse
from app.portal.carriers.source_3_freightx.adapter import FreightXModelError, run_freightx_model
from app.portal.carriers.source_3_freightx.normalizer import deduplicate, normalize_row

logger = structlog.get_logger(__name__)

_MODEL_VERSION = "carrier-relevancy-model"
_SOURCE = "freightx_relevancy"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run_freightx_relevancy(
    db: Session,
    lane_id: uuid.UUID,
    origin_zip: str,
    dest_zip: str,
    equipment_type: str,
    request_id: str = "",
) -> FreightXRelevancyResponse:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")

    logger.info(
        "freightx.run.started",
        request_id=request_id,
        lane_id=str(lane_id),
        origin_zip=origin_zip,
        dest_zip=dest_zip,
        equipment_type=equipment_type,
        source=_SOURCE,
    )

    now = _utcnow()
    run_id = uuid.uuid4()
    t0 = time.monotonic()

    try:
        df = run_freightx_model(
            origin_zip=origin_zip,
            dest_zip=dest_zip,
            equipment_type=equipment_type,
            freightx_src_api_path=settings.freightx_src_api_path,
        )
        elapsed = time.monotonic() - t0
    except FreightXModelError as exc:
        elapsed = time.monotonic() - t0
        logger.error(
            "freightx.run.model_failed",
            request_id=request_id,
            lane_id=str(lane_id),
            error=str(exc),
            elapsed_seconds=round(elapsed, 2),
            source=_SOURCE,
        )
        db.add(CarrierRelevancyRun(
            id=run_id,
            lane_id=lane_id,
            origin_zip=origin_zip,
            destination_zip=dest_zip,
            equipment_type=equipment_type,
            model_version=_MODEL_VERSION,
            status="ERROR",
            row_count=0,
            error_message="freightx_model_failure",
            created_at=now,
        ))
        db.commit()
        return FreightXRelevancyResponse(
            request_id=request_id,
            lane_id=str(lane_id),
            run_id=str(run_id),
            status="freightx_model_failure",
            row_count=0,
            error_message="freightx_model_failure",
            carriers=[],
        )

    if df is None or df.empty:
        logger.info(
            "freightx.run.no_matches",
            request_id=request_id,
            lane_id=str(lane_id),
            elapsed_seconds=round(time.monotonic() - t0, 2),
            source=_SOURCE,
        )
        db.add(CarrierRelevancyRun(
            id=run_id,
            lane_id=lane_id,
            origin_zip=origin_zip,
            destination_zip=dest_zip,
            equipment_type=equipment_type,
            model_version=_MODEL_VERSION,
            status="NO_MATCHES",
            row_count=0,
            error_message=None,
            created_at=now,
        ))
        db.commit()
        return FreightXRelevancyResponse(
            request_id=request_id,
            lane_id=str(lane_id),
            run_id=str(run_id),
            status="NO_MATCHES",
            row_count=0,
            error_message=None,
            carriers=[],
        )

    raw_rows = [
        normalize_row(row, rank=i + 1, run_id=run_id, lane_id=lane_id, now=now)
        for i, row in enumerate(df.to_dict(orient="records"))
    ]
    normalized = deduplicate(raw_rows)

    empty_docket_count = sum(1 for r in normalized if r["docket_number"] == "")
    if empty_docket_count:
        logger.warning(
            "freightx.run.empty_docket_numbers",
            request_id=request_id,
            lane_id=str(lane_id),
            run_id=str(run_id),
            count=empty_docket_count,
            source=_SOURCE,
        )

    db.add(CarrierRelevancyRun(
        id=run_id,
        lane_id=lane_id,
        origin_zip=origin_zip,
        destination_zip=dest_zip,
        equipment_type=equipment_type,
        model_version=_MODEL_VERSION,
        status="OK",
        row_count=len(normalized),
        error_message=None,
        created_at=now,
    ))
    db.flush()

    for row_data in normalized:
        db.add(CarrierRelevancyRecord(**row_data))

    db.commit()

    logger.info(
        "freightx.run.completed",
        request_id=request_id,
        lane_id=str(lane_id),
        run_id=str(run_id),
        row_count=len(normalized),
        elapsed_seconds=round(elapsed, 2),
        source=_SOURCE,
    )

    return FreightXRelevancyResponse(
        request_id=request_id,
        lane_id=str(lane_id),
        run_id=str(run_id),
        status="OK",
        row_count=len(normalized),
        error_message=None,
        carriers=[
            FreightXCarrierRecord(
                rank=r["rank"],
                docket_number=r["docket_number"],
                legal_name=r["legal_name"],
                email_address=r["email_address"],
                phone=r["phone"],
                label=r["label"],
                source_type=r["source_type"],
            )
            for r in normalized
        ],
    )


def get_freightx_records(
    db: Session,
    lane_id: uuid.UUID,
) -> FreightXRelevancyResponse | None:
    """Return the most recent run and its records for a lane. None if lane not found."""
    if db.query(PortalLane).filter_by(id=lane_id).first() is None:
        return None

    run = (
        db.query(CarrierRelevancyRun)
        .filter_by(lane_id=lane_id)
        .order_by(CarrierRelevancyRun.created_at.desc())
        .first()
    )

    if run is None:
        return FreightXRelevancyResponse(
            request_id="",
            lane_id=str(lane_id),
            run_id="",
            status="NO_RUNS",
            row_count=0,
            error_message=None,
            carriers=[],
        )

    records = (
        db.query(CarrierRelevancyRecord)
        .filter_by(run_id=run.id)
        .order_by(CarrierRelevancyRecord.rank)
        .all()
    )

    return FreightXRelevancyResponse(
        request_id="",
        lane_id=str(lane_id),
        run_id=str(run.id),
        status=run.status,
        row_count=run.row_count,
        error_message=run.error_message,
        carriers=[
            FreightXCarrierRecord(
                rank=r.rank,
                docket_number=r.docket_number,
                legal_name=r.legal_name,
                email_address=r.email_address,
                phone=r.phone,
                label=r.label,
                source_type=r.source_type,
            )
            for r in records
        ],
    )
