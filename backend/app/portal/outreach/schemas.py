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


class ManualPhoneEntry(BaseModel):
    carrier_name: str = ""
    phone: str

    @field_validator("phone")
    @classmethod
    def phone_is_dialable(cls, v: str) -> str:
        raw = v.strip()
        if not raw.startswith("+"):
            raise ValueError("must start with + and include the country calling code")
        digits = "".join(ch for ch in v if ch.isdigit())
        if not 8 <= len(digits) <= 15:
            raise ValueError("must contain 8 to 15 digits including country code")
        return digits

    @field_validator("carrier_name")
    @classmethod
    def name_strip(cls, v: str) -> str:
        return v.strip()


class OutreachRequest(BaseModel):
    include_internal: bool = True
    include_dat: bool = True
    include_crr_model: bool = True
    send_email: bool = True
    send_whatsapp: bool = False
    whatsapp_template_name: str = ""
    whatsapp_language: str = "en_US"
    whatsapp_source_types: list[str] = ["internal", "dat", "manual"]
    test_mode: bool = False
    manual_emails: list[ManualEmailEntry] = []
    manual_phones: list[ManualPhoneEntry] = []
    notes: str = ""
    source_limits: dict[str, int] | None = None  # e.g. {"CRR Model": 500}

    @field_validator("manual_emails")
    @classmethod
    def cap_manual_emails(cls, v: list[ManualEmailEntry]) -> list[ManualEmailEntry]:
        if len(v) > 50:
            raise ValueError("manual_emails may not exceed 50 entries")
        return v

    @field_validator("manual_phones")
    @classmethod
    def cap_manual_phones(cls, v: list[ManualPhoneEntry]) -> list[ManualPhoneEntry]:
        if len(v) > 50:
            raise ValueError("manual_phones may not exceed 50 entries")
        return v

    @field_validator("whatsapp_source_types")
    @classmethod
    def valid_whatsapp_sources(cls, v: list[str]) -> list[str]:
        allowed = {"internal", "dat", "crr_model", "manual"}
        return list(dict.fromkeys(item for item in v if item in allowed))


class FollowUpRequest(BaseModel):
    notes: str = ""
    subject_override: str = ""


class EndCampaignRequest(BaseModel):
    reason: str = "covered"


class RecipientItem(BaseModel):
    carrier_name: str
    email: str = ""
    phone: str = ""
    source: str = ""


class PreviewResponse(BaseModel):
    subject: str
    body: str
    html_body: str
    recipients: list[RecipientItem]
    recipient_count: int
    unique_contact_count: int = 0
    email_recipient_count: int = 0
    whatsapp_recipient_count: int = 0
    email_recipients: list[RecipientItem] = []
    whatsapp_recipients: list[RecipientItem] = []
    recipient_count_by_source: dict[str, int]
    recipient_count_by_channel: dict[str, int] = {}
    sources_included: list[str]
    channels_included: list[str] = []
    whatsapp_template_name: str = ""
    whatsapp_template_preview: str = ""
    test_mode: bool
    bounced_count: int = 0


class OutreachBatchResponse(BaseModel):
    batch_id: str
    lane_id: str
    status: str
    sent_count: int
    email_sent_count: int = 0
    whatsapp_sent_count: int = 0
    test_mode: bool


class CarrierResponseItem(BaseModel):
    carrier_name: str
    email: str
    phone: str
    channel: str = "email"
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


class ChannelMetrics(BaseModel):
    sent: int = 0
    delivered: int = 0
    opened: int = 0
    clicked: int = 0
    replied: int = 0
    failed: int = 0
    bounced: int = 0


class LaneMetricsResponse(BaseModel):
    lane_id: str
    batch_id: str | None
    sent: int
    delivered: int
    opened: int
    clicked: int
    replied: int
    failed: int = 0
    bounced: int = 0
    open_rate: float
    click_through_rate: float
    reply_rate: float
    test_mode: bool
    sent_at: str | None
    carrier_responses: list[CarrierResponseItem]
    source_metrics: dict[str, SourceMetrics]
    channel_metrics: dict[str, ChannelMetrics] = {}
    unique_contacts: int = 0
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
    channel: str = "email"


class CarrierThreadResponse(BaseModel):
    carrier_name: str
    email: str = ""
    phone: str = ""
    channel: str = "email"
    conversation_id: str | None = None
    messages: list[ThreadMessage]


class CarrierReplyRequest(BaseModel):
    email: str
    carrier_name: str = ""
    subject: str
    body: str


class WhatsAppReplyRequest(BaseModel):
    phone: str
    body: str = ""
    template_name: str = ""
