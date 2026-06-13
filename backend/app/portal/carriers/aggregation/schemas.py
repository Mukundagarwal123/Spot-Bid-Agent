from __future__ import annotations

import uuid
from typing import List

from pydantic import BaseModel, Field


class AggregatedCarrier(BaseModel):
    """Normalized intermediate row before deduplication."""

    carrier_name: str
    phone: str
    email: str
    mc_number: str
    source: str
    source_row_id: str  # UUID of the originating DB row, as a string


class OutreachSetRequest(BaseModel):
    include_internal: bool = True
    include_dat: bool = True
    include_freightx: bool = True


class OutreachSetResponse(BaseModel):
    lane_id: str
    outreach_set_id: str
    status: str
    source_count: int
    row_count: int
    dedupe_count: int


class OutreachRowResponse(BaseModel):
    id: str
    carrier_name: str
    phone: str
    email: str
    mc_number: str
    source: str
    dedupe_key: str
    source_row_ids: List[str]
