from __future__ import annotations

from pydantic import BaseModel, field_validator


class DatImportRequest(BaseModel):
    raw_text: str

    @field_validator("raw_text")
    @classmethod
    def raw_text_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("DAT text is required")
        return v


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
