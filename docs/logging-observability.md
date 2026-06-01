# Logging and Observability

## Recommendation
Use `Grafana Cloud Free` as the primary third-party logs platform.

Why:
- Fast to set up.
- Easy query UI for debugging.
- Supports logs, traces, and dashboards in one place.
- Free tier includes meaningful monthly log volume.

## Verified Free Tier Notes (as of 2026-05-27)
- Grafana Cloud docs describe free access that includes logs and traces.
- Pricing pages show included monthly log ingestion in free tier.

## Logging Standard
- Structured JSON logs only.
- Include `correlation_id`, `load_id`, `run_id`, `carrier_id`, `channel`, `provider`.
- UTC timestamps.
- No secrets or sensitive payloads in clear text.

## Minimum Required Fields Per Log Event
- `event`
- `level`
- `timestamp`
- `correlation_id`
- `service`
- `env`
- `message`

## Ingestion Path
1. App logs to stdout (JSON).
2. App pushes to Loki endpoint in Grafana Cloud (configured in `.env`).
3. Dashboard + queries in Grafana UI.

## Suggested Debug Queries
- `service="spot-bid-agent" and event="turvo_webhook_received"`
- `service="spot-bid-agent" and run_id="..."`
- `service="spot-bid-agent" and level="error"`
- `service="spot-bid-agent" and channel="whatsapp"`

## Alerting Starter Rules
- Error rate > threshold for 5m.
- Webhook signature validation failures spike.
- Message send failure ratio by provider.
- No successful run completion in last N minutes.

## Integration Checklist
1. Create Grafana Cloud account.
2. Create API key for logs write.
3. Set `.env` vars:
- `GRAFANA_CLOUD_LOKI_URL`
- `GRAFANA_CLOUD_LOKI_USERNAME`
- `GRAFANA_CLOUD_LOKI_API_KEY`
4. Verify `/health` log appears in Grafana.
5. Add dashboards and alerts.
