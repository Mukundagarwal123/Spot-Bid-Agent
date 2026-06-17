from __future__ import annotations

from pydantic import BaseModel, field_validator


class ManualEmailEntry(BaseModel):
    carrier_name: str = ""
    email: str

    @field_validator("email")
    @classmethod
    def email_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or "@" not in v:
            raise ValueError("must be a valid email address")
        return v

    @field_validator("carrier_name")
    @classmethod
    def name_strip(cls, v: str) -> str:
        return v.strip()


class OutreachRequest(BaseModel):
    include_internal: bool = True
    include_dat: bool = True
    include_crr_model: bool = True
    test_mode: bool = False
    manual_emails: list[ManualEmailEntry] = []
    notes: str = ""
    source_limits: dict[str, int] | None = None  # e.g. {"CRR Model": 500}

    @field_validator("manual_emails")
    @classmethod
    def cap_manual_emails(cls, v: list[ManualEmailEntry]) -> list[ManualEmailEntry]:
        if len(v) > 50:
            raise ValueError("manual_emails may not exceed 50 entries")
        return v


class FollowUpRequest(BaseModel):
    notes: str = ""
    subject_override: str = ""


class EndCampaignRequest(BaseModel):
    reason: str = "covered"


class RecipientItem(BaseModel):
    carrier_name: str
    email: str


class PreviewResponse(BaseModel):
    subject: str
    body: str
    html_body: str
    recipients: list[RecipientItem]
    recipient_count: int
    recipient_count_by_source: dict[str, int]
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
    source_type: str
    status: str
    last_event: str
    last_event_at: str | None
    reply_snippet: str | None
    attempt_number: int
    is_follow_up: bool


class SourceMetrics(BaseModel):
    total: int
    delivered: int
    opened: int
    replied: int


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
    source_metrics: dict[str, SourceMetrics]
    campaign_ended: bool
    follow_up_eligible_count: int
    batch_status: str


class ThreadMessage(BaseModel):
    direction: str  # "outbound" | "inbound"
    subject: str | None = None
    body: str | None = None
    timestamp: str
    status: str | None = None
    from_name: str | None = None
    attempt_number: int | None = None


class CarrierThreadResponse(BaseModel):
    carrier_name: str
    email: str
    messages: list[ThreadMessage]


class CarrierReplyRequest(BaseModel):
    email: str
    carrier_name: str = ""
    subject: str
    body: str
