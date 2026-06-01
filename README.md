# Spot Bid Agent

AI-assisted spot bid automation for freight loads tagged `#spotbid` in Turvo.

## What This Project Does
- Triggers a workflow when Turvo tag events arrive.
- Pulls and normalizes carrier candidates from multiple sources.
- Sends outreach via email, SMS, and WhatsApp.
- Tracks engagement and negotiation status.
- Exposes load activity metrics for dashboarding.

## Current Repo Layout
- `CLAUDE.md`: Claude Code project context and contribution rules.
- `docs/specs/`: Product, technical, infra/tooling, and API specs.
- `docs/roadmap.md`: Build phases.
- `docs/data-model.md`: Initial schema design.
- `docs/runbooks/`: Operational runbooks.
- `docs/adr/`: Architecture decision records.
- `backend/`: Flask monolith (SSR + internal JSON APIs), DB models, services, and tests.

## Recommended Stack
- Backend/UI: `Python`, `Flask`, `Jinja`, minimal vanilla JS, `LangGraph`
- Queue/cache: `Redis` + worker
- DB: `PostgreSQL (AWS RDS/Aurora)`
- Comms: `Resend` + `Twilio (SMS + WhatsApp)`
- Logs/observability: `Grafana Cloud Free` + OpenTelemetry

## Local Setup (Planned)
1. Copy `.env.example` to `.env`.
2. Install backend dependencies.
3. Start Flask app.
4. Configure webhooks in Turvo, Resend, Twilio.

## Logging Recommendation
Use `docs/logging-observability.md` as the implementation guide.
