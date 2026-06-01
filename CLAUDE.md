    # Spot Bid Agent - Claude Code Context

## Project Intent
Build an AI-powered Spot Bid Agent for US freight lanes. When a shipment is tagged `#spotbid` in Turvo TMS, the system should trigger an agent that:
- identifies candidate carriers from multiple sources,
- sends outreach via email/SMS/WhatsApp,
- tracks engagement and negotiations,
- stores conversation + carrier performance history,
- updates a per-load activity dashboard.

## Current Product Phase
MVP with dummy data in frontend first, then replace data source components incrementally with live integrations.

## Core Business Flow
1. Turvo webhook/tag event arrives.
2. Spot Bid workflow instance starts for shipment/lane.
3. Carrier candidates fetched + ranked.
4. Outreach campaign launched (email + SMS + WhatsApp).
5. Events ingested (open/click/reply/status).
6. Negotiation state updated.
7. Winning carrier and rate recorded.
8. Dashboard and analytics refreshed.

## Target Stack (Current)
- `Python` backend
- `FastAPI` APIs and webhooks
- `LangGraph` for workflow orchestration
- `React` frontend
- `AWS` infrastructure + database services
- `Resend` for email
- `Twilio` for SMS + WhatsApp

## Non-Functional Priorities
- Idempotent trigger handling
- Horizontal scalability for concurrent loads
- Strong observability (logs, metrics, traces)
- Data lineage for every communication event
- Clear audit trail per load

## Constraints and Assumptions
- Initial UI may use dummy data from all 3 carrier sources.
- Multiple tags/events for one shipment may happen quickly.
- Each load must support independent concurrent workflow execution.

## Documentation Map
- `docs/specs/product-spec.md`
- `docs/specs/technical-spec.md`
- `docs/specs/infra-tools-spec.md`
- `docs/specs/api-spec.md`
- `docs/roadmap.md`

## Build Rules for Contributors
- Keep modules small and testable.
- Add tests for orchestration transitions and idempotency edge cases.
- Prefer typed interfaces (Pydantic/TypeScript types) across boundaries.
- Never hardcode secrets; use environment variables and a secret manager.
