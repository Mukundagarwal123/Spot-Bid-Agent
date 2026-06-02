from __future__ import annotations

import time

import structlog

from app.portal.carriers.schemas import (
    CarrierRecommendationRequest,
    CarrierRecommendationResponse,
    CarrierResult,
)
from app.portal.carriers.source_1_internal_turvo.carrier_contact_store import (
    CarrierContactRecord,
    get_carrier_contact_store,
)
from app.portal.carriers.source_1_internal_turvo.db import query_covered_loads
from app.portal.carriers.source_1_internal_turvo.turvo_client import turvo_client

log = structlog.get_logger(__name__)

_SOURCE = "turvo_internal"


def get_internal_turvo_recommendations(
    req: CarrierRecommendationRequest,
    request_id: str,
) -> CarrierRecommendationResponse:
    t0 = time.monotonic()
    log.info(
        "carrier.recommendation.started",
        request_id=request_id,
        origin_city=req.origin_city,
        origin_state=req.origin_state,
        origin_zip=req.origin_zip,
        destination_city=req.destination_city,
        destination_state=req.destination_state,
        destination_zip=req.destination_zip,
        source=_SOURCE,
    )

    carrier_names = query_covered_loads(
        origin_city=req.origin_city,
        origin_state=req.origin_state,
        destination_state=req.destination_state,
    )
    log.info(
        "carrier.source_1.loaded",
        request_id=request_id,
        carrier_count=len(carrier_names),
        origin_city=req.origin_city,
        origin_state=req.origin_state,
        destination_state=req.destination_state,
        source=_SOURCE,
    )

    results: list[CarrierResult] = []
    cache_hits = 0
    cache_misses = 0
    turvo_calls = 0
    turvo_matches = 0
    turvo_not_found = 0
    turvo_errors = 0
    turvo_unavailable = 0
    persisted_rows = 0
    for rank, name in enumerate(carrier_names, start=1):
        result, outcome = _enrich(name, rank, request_id=request_id)
        if outcome == "cache_hit":
            cache_hits += 1
        elif outcome == "cache_miss":
            cache_misses += 1
        elif outcome == "turvo_ok":
            turvo_calls += 1
            turvo_matches += 1
            persisted_rows += 1
        elif outcome == "turvo_not_found":
            turvo_calls += 1
            turvo_not_found += 1
        elif outcome == "turvo_error":
            turvo_calls += 1
            turvo_errors += 1
        elif outcome == "turvo_unavailable":
            turvo_unavailable += 1
        results.append(result)

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "carrier.source_1.summary",
        request_id=request_id,
        carrier_count=len(results),
        carrier_names_from_internal=len(carrier_names),
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        turvo_calls=turvo_calls,
        turvo_matches=turvo_matches,
        turvo_not_found=turvo_not_found,
        turvo_errors=turvo_errors,
        turvo_unavailable=turvo_unavailable,
        persisted_rows=persisted_rows,
        duration_ms=duration_ms,
        source=_SOURCE,
    )

    return CarrierRecommendationResponse(request_id=request_id, query=req.model_dump(), carriers=results)


def _enrich(carrier_name: str, rank: int, request_id: str) -> tuple[CarrierResult, str]:
    contact_store = get_carrier_contact_store()
    cached = contact_store.get(carrier_name)
    if cached is not None:
        return (
            CarrierResult(
                carrier_name=carrier_name,
                email=cached.email,
                phone=cached.phone,
                mc_number=cached.mc_number,
                match_rank=rank,
                status="OK",
            ),
            "cache_hit",
        )

    if turvo_client is None:
        return (
            CarrierResult(
                carrier_name=carrier_name,
                email=None,
                match_rank=rank,
                status="NOT_FOUND",
            ),
            "turvo_unavailable",
        )

    try:
        contact = turvo_client.get_carrier_contact(carrier_name)
        has_data = bool(contact.email or contact.phone or contact.mc_number)
        if has_data:
            contact_store.upsert(
                CarrierContactRecord(
                    carrier_name=carrier_name,
                    email=contact.email,
                    phone=contact.phone,
                    mc_number=contact.mc_number,
                )
            )
            return (
                CarrierResult(
                    carrier_name=carrier_name,
                    email=contact.email,
                    phone=contact.phone,
                    mc_number=contact.mc_number,
                    match_rank=rank,
                    status="OK",
                ),
                "turvo_ok",
            )
        return (
            CarrierResult(
                carrier_name=carrier_name,
                email=None,
                phone=None,
                mc_number=None,
                match_rank=rank,
                status="NOT_FOUND",
                ),
                "turvo_not_found",
            )
    except Exception as exc:
        return (
            CarrierResult(
                carrier_name=carrier_name,
                email=None,
                phone=None,
                mc_number=None,
                match_rank=rank,
                status="ERROR",
                error=str(exc),
            ),
            "turvo_error",
        )
