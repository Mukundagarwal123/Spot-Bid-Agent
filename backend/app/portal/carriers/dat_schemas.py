from __future__ import annotations

from pydantic import BaseModel, model_validator


class DatImportRequest(BaseModel):
    truck_postings_text: str = ""
    lanemakers_text: str = ""

    @model_validator(mode="after")
    def at_least_one_required(self) -> "DatImportRequest":
        if not self.truck_postings_text.strip() and not self.lanemakers_text.strip():
            raise ValueError("At least one of truck_postings_text or lanemakers_text is required")
        return self


class DatImportResponse(BaseModel):
    lane_id: str
    source: str = "dat"
    parsed_count: int
    created_count: int
    status: str


class CarrierRecordItem(BaseModel):
    id: str
    carrier_name: str
    email: str
    phone: str
    mc_number: str
    source_notes: str
    source_type: str
    created_at: str


class CarrierRecordsResponse(BaseModel):
    lane_id: str
    sources: dict[str, list[CarrierRecordItem]]
