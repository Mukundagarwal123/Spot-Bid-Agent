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

## Phase 4 - Outreach Layer
- Integrate Resend for email blasts.
- Integrate Twilio for SMS and WhatsApp.
- Persist outbound message references.

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
