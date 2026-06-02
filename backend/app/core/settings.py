from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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


settings = Settings()
