from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class EquipmentType(str, Enum):
    dry_van = "dry_van"
    reefer = "reefer"
    flatbed = "flatbed"
    power_only = "power_only"
    other = "other"


EQUIPMENT_LABELS: dict[EquipmentType, str] = {
    EquipmentType.dry_van: "Dry Van",
    EquipmentType.reefer: "Reefer",
    EquipmentType.flatbed: "Flatbed",
    EquipmentType.power_only: "Power Only",
    EquipmentType.other: "Other",
}

# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class StopInput(BaseModel):
    city: str
    state: str
    zip: str | None = None

    @field_validator("city")
    @classmethod
    def city_min_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("city must be at least 2 characters")
        return v

    @field_validator("state")
    @classmethod
    def state_format(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 2:
            raise ValueError("state must be a 2-letter code")
        return v

    @field_validator("zip")
    @classmethod
    def zip_format(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not v.isdigit() or len(v) != 5:
            raise ValueError("zip must be 5 digits")
        return v


class LaneCreateRequest(BaseModel):
    origin_city: str
    origin_state: str
    origin_zip: str | None = None
    destination_city: str
    destination_state: str
    destination_zip: str | None = None
    stops: list[StopInput] = []
    equipment_type: EquipmentType
    pickup_date: date | None = None

    @field_validator("origin_city", "destination_city")
    @classmethod
    def city_min_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("must be at least 2 characters")
        return v

    @field_validator("origin_state", "destination_state")
    @classmethod
    def state_format(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 2:
            raise ValueError("must be a 2-letter state code")
        return v

    @field_validator("origin_zip", "destination_zip")
    @classmethod
    def zip_format(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not v.isdigit() or len(v) != 5:
            raise ValueError("zip must be 5 digits")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class LaneCreatedResponse(BaseModel):
    lane_id: UUID
    label: str
    status: str
    created_at: datetime


class MetricsPreview(BaseModel):
    carriers_contacted: int
    carriers_responded: int


class LaneSummary(BaseModel):
    lane_id: UUID
    label: str
    equipment_type: str
    status: str
    last_activity_at: datetime
    pickup_date: date | None
    metrics_preview: MetricsPreview


class LanesListResponse(BaseModel):
    lanes: list[LaneSummary]


class StopInfo(BaseModel):
    stop_order: int
    city: str
    state: str
    zip: str | None


class LaneInfo(BaseModel):
    lane_id: UUID
    label: str
    origin_city: str
    origin_state: str
    origin_zip: str | None
    destination_city: str
    destination_state: str
    destination_zip: str | None
    equipment_type: str
    pickup_date: date | None
    status: str
    created_at: datetime


class MetricsSnapshot(BaseModel):
    emails_sent: int
    emails_clicked: int
    email_replies: int
    sms_sent: int
    sms_replies: int
    whatsapp_sent: int
    whatsapp_replies: int
    carriers_contacted: int
    carriers_responded: int


class TimelineEvent(BaseModel):
    event_type: str
    label: str
    timestamp: datetime
    channel: str | None


class LaneDetailResponse(BaseModel):
    lane: LaneInfo
    stops: list[StopInfo]
    metrics: MetricsSnapshot
    timeline: list[TimelineEvent]


class CarrierCRMItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    carrier_name: str
    times_contacted: int
    times_responded: int
    avg_response_time_minutes: int
    preferred_channel: str
    response_rate: float
    last_contacted_at: datetime


class CarrierCRMResponse(BaseModel):
    carriers: list[CarrierCRMItem]
