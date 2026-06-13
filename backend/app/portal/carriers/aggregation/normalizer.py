from __future__ import annotations

import re
import uuid
from typing import List

from app.db.models import CarrierRelevancyRecord, PortalLaneCarrierRecord
from app.portal.carriers.aggregation.schemas import AggregatedCarrier


def _strip_mc_prefix(value: str) -> str:
    """Remove a leading 'MC' prefix (case-insensitive) and trim whitespace."""
    return re.sub(r"^mc\s*", "", value.strip(), flags=re.IGNORECASE).strip()


def normalize_internal_turvo_records(
    records: List[PortalLaneCarrierRecord],
) -> List[AggregatedCarrier]:
    return [
        AggregatedCarrier(
            carrier_name=r.carrier_name.strip(),
            phone=r.phone or "",
            email=r.email or "",
            mc_number=_strip_mc_prefix(r.mc_number or ""),
            source="internal",
            source_row_id=str(r.id),
        )
        for r in records
    ]


def normalize_dat_records(
    records: List[PortalLaneCarrierRecord],
) -> List[AggregatedCarrier]:
    return [
        AggregatedCarrier(
            carrier_name=r.carrier_name.strip(),
            phone=r.phone or "",
            email=r.email or "",
            mc_number=_strip_mc_prefix(r.mc_number or ""),
            source="DAT",
            source_row_id=str(r.id),
        )
        for r in records
    ]


def normalize_freightx_records(
    records: List[CarrierRelevancyRecord],
) -> List[AggregatedCarrier]:
    return [
        AggregatedCarrier(
            carrier_name=(r.legal_name or "").strip(),
            phone=r.phone or "",
            email=r.email_address or "",
            # docket_number is already stored without the MC prefix (Feature 004)
            mc_number=(r.docket_number or "").strip(),
            source=r.label.strip() if r.label and r.label.strip() else "freightx",
            source_row_id=str(r.id),
        )
        for r in records
        if (r.legal_name or "").strip()
    ]
