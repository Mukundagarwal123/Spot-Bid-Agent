# Roadmap - Spot Bid Agent

## Phase 0 - Foundation
- Finalize specs and data contracts.
- Set up repo standards, CI, and environments.
- Build dummy-data frontend dashboard.

## Phase 1 - Manual Lane MVP (No Turvo Yet) ✅ COMPLETE
- Manual lane input form (origin/destination/stops/equipment/optional PU date).
- Active lane tabs/cards UI.
- Dummy workflow activity simulation for each lane.
- Dummy carrier CRM history view.

**Delivered (Feature 001):**
- `backend/app/portal/` — FastAPI router, Pydantic schemas, service, dummy generator
- `backend/app/db/` — SQLAlchemy ORM for 5 `portal_*` tables
- `frontend/src/` — React + Vite + TS: LaneIntakeForm, ActiveLanesBoard, LaneDetailPanel, CarrierCRMView
- 46 backend tests (pytest), 21 frontend tests (vitest) — all green
- SQLite for local dev; swap `DATABASE_URL` to PostgreSQL for staging

**Transition to Feature 002:** Replace `portal_*` tables with live `loads`/`carriers`
schema; wire Turvo webhook to trigger real lane creation.

## Phase 2 - Trigger and Orchestration
- Implement Turvo webhook ingestion.
- Build LangGraph workflow skeleton.
- Add idempotency and run tracking.

## Phase 3 - Carrier Data Layer
- Build source adapters for DAT/CSV/internal DB.
- Normalize + deduplicate carrier records.

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
