# Infra and Tools Spec - Spot Bid Agent

## Recommended Core Stack
- Backend: `Python 3.12`, `FastAPI`, `Uvicorn`
- Orchestration: `LangGraph`
- Queue/Cache: `Redis` + worker framework (`RQ` or `Celery`)
- Database: `PostgreSQL` (AWS RDS/Aurora)
- Frontend: `React` + `TypeScript` + `Vite`
- Observability: `OpenTelemetry`, `Prometheus`, `Grafana`, `Sentry`

## AWS Recommendation
- API compute: `ECS Fargate` (or `Lambda` if traffic remains low/simple)
- DB: `RDS PostgreSQL`
- Object storage: `S3` (exports/log snapshots)
- Secrets: `AWS Secrets Manager`
- Queueing: `SQS` (optional if not using Redis-first queueing)
- Monitoring: `CloudWatch` + trace sink

## Communication Providers
- Email: `Resend`
- SMS + WhatsApp: `Twilio` (single provider simplifies callback model)

## Security and Compliance Baseline
- Signed webhook verification for Turvo/Twilio/Resend.
- PII minimization in logs.
- Encrypted secrets and at-rest database encryption.
- RBAC for dashboard/API.

## Dev Tooling
- Python deps: `uv` or `poetry`
- Linting: `ruff`
- Typing: `mypy`
- Tests: `pytest`
- API schema docs: OpenAPI from FastAPI
- Frontend quality: `eslint`, `prettier`, `vitest`

## CI/CD
- GitHub Actions:
- Lint + tests on PR
- Build artifact + deploy to staging on merge
- Manual approval to production

## Environment Strategy
- `local`
- `staging`
- `production`

Use environment-based config with strict separation of credentials and endpoints.
