from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import List

import structlog

from app.db.models import (
    CarrierOutreachRow,
    CarrierOutreachSet,
    CarrierRelevancyRecord,
    CarrierRelevancyRun,
    PortalLane,
    PortalLaneCarrierRecord,
)
from app.portal.carriers.aggregation.deduplicator import deduplicate
from app.portal.carriers.aggregation.normalizer import (
    normalize_dat_records,
    normalize_freightx_records,
    normalize_internal_turvo_records,
)
from app.portal.carriers.aggregation.schemas import AggregatedCarrier

logger = structlog.get_logger(__name__)


def build_outreach_set(
    db,
    lane_id: uuid.UUID,
    include_internal: bool = True,
    include_dat: bool = True,
    include_freightx: bool = True,
    request_id: str = "",
) -> CarrierOutreachSet:
    """
    Aggregate carrier rows from all enabled sources, deduplicate, and persist
    a new CarrierOutreachSet with its CarrierOutreachRows.

    Source tables are never mutated.  Raises ValueError('lane_not_found') if
    the lane does not exist.
    """
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")

    now = datetime.utcnow()
    outreach_set = CarrierOutreachSet(
        id=uuid.uuid4(),
        lane_id=lane_id,
        status="building",
        source_count=0,
        row_count=0,
        dedupe_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(outreach_set)
    db.flush()

    try:
        all_rows: List[AggregatedCarrier] = []
        sources_with_data = 0

        if include_internal:
            internal_records = (
                db.query(PortalLaneCarrierRecord)
                .filter_by(lane_id=lane_id, source_type="internal")
                .all()
            )
            if internal_records:
                sources_with_data += 1
                all_rows.extend(normalize_internal_turvo_records(internal_records))
                logger.info(
                    "aggregation.source_loaded",
                    request_id=request_id,
                    lane_id=str(lane_id),
                    source="internal",
                    count=len(internal_records),
                )

        if include_dat:
            dat_records = (
                db.query(PortalLaneCarrierRecord)
                .filter_by(lane_id=lane_id, source_type="dat")
                .all()
            )
            if dat_records:
                sources_with_data += 1
                all_rows.extend(normalize_dat_records(dat_records))
                logger.info(
                    "aggregation.source_loaded",
                    request_id=request_id,
                    lane_id=str(lane_id),
                    source="dat",
                    count=len(dat_records),
                )

        if include_freightx:
            latest_run = (
                db.query(CarrierRelevancyRun)
                .filter_by(lane_id=lane_id)
                .order_by(CarrierRelevancyRun.created_at.desc())
                .first()
            )
            if latest_run:
                freightx_records = (
                    db.query(CarrierRelevancyRecord)
                    .filter_by(run_id=latest_run.id)
                    .order_by(CarrierRelevancyRecord.rank)
                    .all()
                )
                if freightx_records:
                    sources_with_data += 1
                    all_rows.extend(normalize_freightx_records(freightx_records))
                    logger.info(
                        "aggregation.source_loaded",
                        request_id=request_id,
                        lane_id=str(lane_id),
                        source="freightx",
                        count=len(freightx_records),
                    )

        total_before_dedup = len(all_rows)
        canonical_rows = deduplicate(all_rows)
        dedupe_count = total_before_dedup - len(canonical_rows)

        now_rows = datetime.utcnow()
        for canonical in canonical_rows:
            db.add(
                CarrierOutreachRow(
                    id=uuid.uuid4(),
                    outreach_set_id=outreach_set.id,
                    lane_id=lane_id,
                    carrier_name=canonical.carrier_name,
                    phone=canonical.phone,
                    email=canonical.email,
                    mc_number=canonical.mc_number,
                    source=canonical.source,
                    source_row_ids=json.dumps(canonical.source_row_ids),
                    dedupe_key=canonical.dedupe_key,
                    created_at=now_rows,
                )
            )

        outreach_set.status = "ready"
        outreach_set.source_count = sources_with_data
        outreach_set.row_count = len(canonical_rows)
        outreach_set.dedupe_count = dedupe_count
        outreach_set.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            "aggregation.build_complete",
            request_id=request_id,
            lane_id=str(lane_id),
            outreach_set_id=str(outreach_set.id),
            source_count=sources_with_data,
            row_count=len(canonical_rows),
            dedupe_count=dedupe_count,
        )

    except Exception as exc:
        outreach_set.status = "failed"
        outreach_set.updated_at = datetime.utcnow()
        db.commit()
        logger.error(
            "aggregation.build_failed",
            request_id=request_id,
            lane_id=str(lane_id),
            error=str(exc),
        )
        raise

    return outreach_set


def get_latest_outreach_set(db, lane_id: uuid.UUID) -> CarrierOutreachSet | None:
    return (
        db.query(CarrierOutreachSet)
        .filter_by(lane_id=lane_id)
        .order_by(CarrierOutreachSet.created_at.desc())
        .first()
    )


def get_outreach_rows(db, outreach_set_id: uuid.UUID) -> list[CarrierOutreachRow]:
    return (
        db.query(CarrierOutreachRow)
        .filter_by(outreach_set_id=outreach_set_id)
        .order_by(CarrierOutreachRow.created_at)
        .all()
    )
