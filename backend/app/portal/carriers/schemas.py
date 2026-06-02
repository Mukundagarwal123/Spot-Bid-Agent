from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator


class CarrierRecommendationRequest(BaseModel):
    origin_city: str
    origin_state: str
    origin_zip: str
    destination_city: str
    destination_state: str
    destination_zip: str

    @model_validator(mode="before")
    @classmethod
    def trim_and_reject_blank(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        trimmed = {}
        for k, v in values.items():
            if isinstance(v, str):
                stripped = v.strip()
                trimmed[k] = stripped if stripped else None
            else:
                trimmed[k] = v
        return trimmed


class CarrierResult(BaseModel):
    carrier_name: str
    email: str | None
    phone: str | None = None
    mc_number: str | None = None
    source: Literal["turvo_internal"] = "turvo_internal"
    match_rank: int
    status: Literal["OK", "NOT_FOUND", "ERROR"]
    error: str | None = None


class CarrierRecommendationResponse(BaseModel):
    request_id: str
    query: dict
    carriers: list[CarrierResult]
