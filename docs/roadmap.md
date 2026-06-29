# Roadmap - Spot Bid Agent

## Phase 0 - Foundation
- Finalize specs and data contracts.
- Set up repo standards, CI, and environments.
- Stand up Flask monolith skeleton (SSR + JSON API).

## Phase 1 - Manual Lane MVP (No Turvo Yet)
- Manual lane input form (origin/destination/stops/equipment/optional pickup date).
- Active and Completed lane views.
- Lane detail drawer with channel overview, responses, and activity log.
- Carrier CRM view with profile response history.
- Deterministic dummy data generation for metrics/timeline/carrier snapshots.

## Phase 2 - Trigger and Orchestration
- Implement Turvo webhook ingestion.
- Build LangGraph workflow skeleton.
- Add idempotency and run tracking.

## Phase 3 - Carrier Data Layer
- Build source adapters for DAT/CSV/internal DB.
- Normalize and deduplicate carrier records.
- Start with a CSV-backed contact cache for feature 002, then migrate the same interface to RDS/Postgres.
Feature spec reference:
- `docs/features/feature-002-internal-turvo-carrier-recommendation.md` (Source 1: internal Turvo carrier recommendation + email enrichment)
- `docs/features/feature-003-dat-carrier-data-import.md` (Source 2: DAT paste import + lane-scoped carrier storage)
- `docs/features/feature-004-freightx-carrier-relevancy-model.md` (Source 3: FreightX carrier relevancy model)
- `docs/features/feature-005-multi-source-carrier-aggregation.md` (combine Source 1 + 2 + 3 into one outreach-ready dataset)

## Phase 4 - Outreach Layer
- Integrate Resend for email blasts.
- Persist outbound message references.
- Add webhook-driven metric updates mapped back to each outbound email/message record.
- Add lane-level live outreach page with source selection, notes, template preview, and follow-up actions.
- Keep SMS and WhatsApp disabled until the email workflow is stable.

## Phase 4b - WhatsApp Inbox Foundation
- Build a WhatsApp inbox/dashboard with webhook-driven inbound message ingestion.
- Show full conversation history per contact in a dedicated route.
- Support manual reply/send from the dashboard UI.
- Persist message status updates and live thread state.
- Keep the architecture channel-aware so WhatsApp can later share the same messaging model as email and SMS.

## Phase 5 - Event Tracking
- Capture delivery/open/click/reply callbacks.
- Update per-carrier and per-load state.

## Phase 6 - Profiling and Outcomes
- Save negotiation history.
- Write carrier performance summaries.
- Record final winning carrier/rate.

## Phase 7 - Production Dashboard
- Live load activity metrics.
- Timeline and leaderboards.
- Filters and drill-down by lane/carrier.
