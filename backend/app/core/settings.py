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


settings = Settings()
