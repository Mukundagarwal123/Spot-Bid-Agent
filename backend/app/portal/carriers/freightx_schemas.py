from __future__ import annotations

from pydantic import BaseModel, field_validator, model_validator

_EQUIPMENT_MAP = {"dry_van": "dryvan"}
_VALID_EQUIPMENT = {"dryvan", "reefer", "flatbed"}


class FreightXRelevancyRequest(BaseModel):
    origin_zip: str
    destination_zip: str
    equipment_type: str

    @model_validator(mode="before")
    @classmethod
    def trim_fields(cls, values):
        if not isinstance(values, dict):
            return values
        return {k: v.strip() if isinstance(v, str) else v for k, v in values.items()}

    @field_validator("equipment_type", mode="after")
    @classmethod
    def normalize_equipment(cls, v: str) -> str:
        normalized = _EQUIPMENT_MAP.get(v, v)
        if normalized not in _VALID_EQUIPMENT:
            raise ValueError("equipment_type must be dryvan, reefer, or flatbed")
        return normalized


class FreightXCarrierRecord(BaseModel):
    rank: int
    docket_number: str
    legal_name: str
    email_address: str
    phone: str
    label: str
    source_type: str = "freightx_relevancy"


class FreightXRelevancyResponse(BaseModel):
    request_id: str
    lane_id: str
    run_id: str
    status: str
    row_count: int
    error_message: str | None
    carriers: list[FreightXCarrierRecord]
