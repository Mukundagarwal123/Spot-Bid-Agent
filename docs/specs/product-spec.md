# Product Spec - Spot Bid Agent

## Problem Statement
Manual spot bid outreach is slow, inconsistent, and hard to track across channels. Ops needs a reliable system to trigger outreach instantly, capture carrier responses, and close loads faster with measurable outcomes.

## Goal
Automate spot bidding with end-to-end visibility from lane intake to deal closure.

## Primary Users
- Operations team
- Carrier sales / procurement team
- Leadership (dashboard consumers)

## Initial Intake (Phase 1)
Manual lane entry from frontend form:
- origin (city/state/zip)
- destination (city/state/zip)
- multiple optional stops
- equipment type
- optional pickup date

Future trigger:
- Shipment in Turvo receives tag `#spotbid`.

## Functional Requirements
1. Create a lane workflow per manual lane entry (Phase 1), then per tagged Turvo load (later phase).
2. Ingest carrier candidates from:
- DAT feed/import
- Sid's carrier list (CSV/shared file)
- Internal carrier network DB
3. Execute outreach through:
- Email (Resend)
- SMS (Twilio)
- WhatsApp (Twilio WhatsApp API)
4. Track engagement by carrier and by load:
- Sent
- Opened/Clicked
- Replied
- Negotiating (v2)
- Deal closed
- Final rate agreed (v2)
- No response
5. Persist conversation/event history.
6. Update carrier profile using outcomes.
7. Display per-load live dashboard and timeline.

## Dashboard Requirements
- Total carriers contacted
- Open rate
- Click-through rate
- Reply rate
- Carriers in negotiation
- Closed carrier + final rate
- Event timeline
- Carrier response speed leaderboard

## Out of Scope for MVP
- Full autonomous negotiation
- Advanced dynamic pricing model
- Complex SLA routing by customer segment

## Success Metrics
- Time from tag to first outreach
- Reply rate uplift vs baseline
- Load coverage (percent of tagged loads processed)
- Deal close time reduction
- Data completeness for load events
