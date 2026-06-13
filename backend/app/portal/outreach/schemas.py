from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator


class OutreachRequest(BaseModel):
    include_internal: bool = True
    include_dat: bool = True
    include_freightx: bool = True
    test_mode: bool = False
    manual_emails: list[str] = []
    notes: str = ""

    @field_validator("manual_emails")
    @classmethod
    def cap_manual_emails(cls, v: list[str]) -> list[str]:
        cleaned = [e.strip() for e in v if e.strip()]
        if len(cleaned) > 20:
            raise ValueError("manual_emails may not exceed 20 addresses")
        return cleaned


class RecipientItem(BaseModel):
    carrier_name: str
    email: str


class PreviewResponse(BaseModel):
    subject: str
    body: str
    recipients: list[RecipientItem]
    recipient_count: int
    sources_included: list[str]
    test_mode: bool


class OutreachBatchResponse(BaseModel):
    batch_id: str
    lane_id: str
    status: str
    sent_count: int
    test_mode: bool


class CarrierResponseItem(BaseModel):
    carrier_name: str
    email: str
    phone: str
    source: str
    status: str
    last_event: str
    last_event_at: str | None
    reply_snippet: str | None


class LaneMetricsResponse(BaseModel):
    lane_id: str
    batch_id: str | None
    sent: int
    delivered: int
    opened: int
    clicked: int
    replied: int
    open_rate: float
    click_through_rate: float
    reply_rate: float
    test_mode: bool
    sent_at: str | None
    carrier_responses: list[CarrierResponseItem]
