# Feature 001 - Manual Lane Input and Portal Activity Simulator

## Objective
Start without Turvo/webhooks. User manually enters lane details in frontend, creates an active lane card/tab, and sees simulated spot-bid workflow activity with dummy data.

## Scope
1. Manual lane creation form in frontend.
2. Supports origin, destination, optional multiple stops.
3. Supports equipment type and optional pickup date.
4. Newly created lane appears in "Active Lanes" view.
5. Lane detail panel shows simulated workflow timeline and metrics.
6. Carrier CRM panel shows historical dummy stats per carrier.

## Out of Scope
1. Turvo webhook ingestion.
2. Real email/SMS/WhatsApp sending.
3. Live provider callbacks.
4. Real agent orchestration.

## Input Form Requirements
1. Origin:
- city
- state
- zip (optional but recommended)
2. Destination:
- city
- state
- zip (optional but recommended)
3. Stops:
- add/remove multiple intermediate stops
- each stop has city/state/zip
4. Equipment type:
- dropdown (Dry Van, Reefer, Flatbed, Power Only, Other)
5. Pickup date:
- optional

## UI Requirements

### Active Lanes
1. Lane tabs/cards list at top or left rail.
2. Each lane shows:
- lane label (Origin -> Destination)
- equipment
- status badge (`new`, `in_progress`, `closed`)
- last activity timestamp

### Lane Activity View (Dummy)
1. KPI tiles:
- emails_sent
- emails_clicked
- email_replies
- sms_sent
- sms_replies
- whatsapp_sent
- whatsapp_replies
- carriers_contacted
- carriers_responded
2. Timeline:
- "lane created"
- "outreach simulated"
- "engagement simulated"
- "responses simulated"
3. Channel breakdown chart/table:
- email
- sms
- whatsapp

### Carrier CRM View (Dummy)
For each carrier:
1. carrier_name
2. times_contacted
3. times_responded
4. avg_response_time
5. preferred_channel
6. response_rate
7. last_contacted_at

## API Contracts (Feature 001)
1. `POST /portal/lanes`
- creates manual lane
2. `GET /portal/lanes`
- returns active lanes list
3. `GET /portal/lanes/{lane_id}`
- returns lane details + simulated metrics + timeline
4. `GET /portal/lanes/{lane_id}/carrier-crm`
- returns simulated carrier history

## Data Model (Feature 001)
1. `lanes`
2. `lane_stops`
3. `lane_metrics_snapshot` (dummy)
4. `lane_activity_events` (dummy timeline)
5. `carrier_crm_snapshot` (dummy)

## Dummy Data Rules
1. Generate deterministic dummy metrics per lane (seed by `lane_id`) so UI stays stable on refresh.
2. Keep values realistic.
3. Include 10-30 carriers in CRM snapshot.

## Acceptance Criteria
1. User can create a lane with required fields.
2. User can add multiple stops.
3. Lane appears in active lanes immediately.
4. Opening lane detail shows dummy metrics + timeline.
5. Carrier CRM table renders for selected lane.
6. Refreshing page preserves lane and deterministic dummy activity.

## Claude Code Plan Prompt (Copy/Paste)
```text
Create an implementation plan only (no code) for Feature 001:
"Manual lane input -> active lane tabs -> dummy activity metrics -> dummy carrier CRM view".

Constraints:
- No Turvo, no webhooks, no live provider integrations yet.
- Backend: FastAPI
- Frontend: React
- Data can be persisted locally in DB with deterministic dummy simulation.

Deliver:
1) Step-by-step tasks (frontend + backend)
2) API schema plan
3) Data model plan
4) Dummy data generation approach
5) State management plan for active lanes UI
6) Testing plan (form validation, list view, detail metrics, CRM table)
7) Milestones for 2-3 day execution
```

## Definition of Done
1. Manual lane can be created and listed.
2. Lane detail screen shows realistic simulated agent activity.
3. Carrier CRM screen shows simulated historical engagement stats.
4. Docs are updated for next feature transition to real integrations.
