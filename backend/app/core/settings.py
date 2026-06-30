from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from the project root regardless of where the server is started from.
# settings.py lives at backend/app/core/settings.py → parents[3] = project root.
_ENV_FILE = str(Path(__file__).resolve().parents[3] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    app_env: str = "local"
    app_name: str = "spot-bid-agent"
    log_level: str = "INFO"

    # Database — defaults to local SQLite; override with PostgreSQL URL in staging/prod
    database_url: str = "sqlite:///./spot_bid_agent.db"

    # CORS origins allowed to call the API
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    grafana_cloud_loki_url: str | None = None
    grafana_cloud_loki_username: str | None = None
    grafana_cloud_loki_api_key: str | None = None

    otel_service_name: str = "spot-bid-agent"
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None

    # Turvo internal DB (for covered_loads carrier recommendation)
    turvo_db_url: str | None = None

    # Local carrier contact cache used before falling back to Turvo
    carrier_data_csv_path: str = str(Path(__file__).resolve().parents[3] / "Carrire Data.csv")

    # Turvo API (for carrier contact enrichment)
    turvo_api_base_url: str = "https://app.turvo.com"
    turvo_api_client_id: str | None = None
    turvo_api_client_secret: str | None = None
    turvo_api_key: str | None = None
    turvo_api_username: str | None = None
    turvo_api_password: str | None = None

    # Set to true in local dev to return mock carrier + email data without real Turvo credentials
    turvo_mock_carriers: bool = False

    # DAT Parser LLM (OpenAI-compatible API)
    llm_base_url: str = "https://api.theagentic.ai/v1"
    llm_model: str = "agentic-large"
    llm_api_key: str = ""

    # FreightX carrier relevancy model — path to FreightX-V1/src/api/
    freightx_src_api_path: str = str(Path(__file__).resolve().parents[3] / "FreightX-V1" / "src" / "api")

    # Resend email provider
    # Accepts RESEND_API_KEY or RESEND_FROM / RESEND_FROM_EMAIL (both spellings in the wild)
    resend_api_key: str = ""
    resend_from: str = Field(default="", alias="RESEND_FROM", validation_alias="RESEND_FROM")
    resend_from_email: str = Field(default="", alias="RESEND_FROM_EMAIL", validation_alias="RESEND_FROM_EMAIL")
    resend_webhook_secret: str = ""

    # Meta WhatsApp Business Cloud API (Feature 008)
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_templates_json: str = "[]"

    @property
    def resend_sender(self) -> str:
        """Return whichever from-address env var is set."""
        return self.resend_from or self.resend_from_email


settings = Settings()
