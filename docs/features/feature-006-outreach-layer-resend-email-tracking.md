# Feature 006 - Outreach Layer: Resend Email Sending, Engagement Tracking, and Test Sends

## Objective
Build the first live outreach layer for the Spot Bid Portal using email only.

The outreach layer should:
- send emails through Resend to the carriers in a lane's outreach-ready dataset,
- track delivery, open, click, and reply events,
- surface lane-level and carrier-level metrics,
- support manual test sends to a small list of hand-entered email addresses,
- and let the operator choose which carrier sources are included before outreach is built or sent.

## Scope
- In scope:
  - Email outreach only, using Resend.
  - Sending to carriers from the canonical outreach dataset.
  - Tracking delivery/open/click/reply metrics.
  - Persisting outbound messages, provider message IDs, and event history.
  - Showing carrier-level response detail for opened/clicked/replied carriers.
  - Supporting manual test recipients for validation with 3-4 emails or any small hand-entered list.
  - Frontend controls to include/exclude source 1, source 2, and source 3 when building outreach input.
  - A `Notes` field that lets the user add custom instructions or context for the email.
  - An email template preview/confirmation step before sending.
- Out of scope:
  - SMS outreach.
  - WhatsApp outreach.
  - Fully autonomous follow-up sequences.
  - Negotiation optimization or rate automation.
  - Multi-step campaign logic beyond the first outbound email.

## Problem Statement
We already have the carrier data layer that combines the three sources into a single outreach-ready dataset.
What is missing now is the actual sending and tracking layer.

Ops needs to know:
- how many emails were sent,
- how many were delivered,
- how many were opened,
- how many were clicked,
- how many carriers replied,
- and which carriers responded with their contact details and response text when available.

We also need a safe way to test the flow on a few manual addresses before running a larger lane.

## Primary Users
- Operations users who launch outreach for a lane.
- Admin users who verify provider and webhook behavior.
- Internal testers who want to send to 3-4 manual test emails first.

## Functional Requirements
1. Send email outreach through Resend only.
2. Save provider message IDs for every outbound email.
3. Track message lifecycle events:
   - sent
   - delivered
   - opened
   - clicked
   - replied
   - failed
4. Aggregate metrics for each lane and outreach set:
   - total sent
   - total delivered
   - total opened
   - total clicked
   - total replied
   - open rate
   - click-through rate
   - reply rate
5. Show carrier-level detail for any carrier that opened, clicked, or replied:
   - carrier name
   - email
   - phone
   - source
   - last event type
   - last event timestamp
   - reply text or reply summary when available
6. Support manual test sends:
   - allow entering a small list of email addresses manually
   - send a test outreach batch to those addresses instead of the full lane audience
   - clearly label the run as a test run
7. Add frontend source-selection controls:
   - source 1: internal
   - source 2: DAT
   - source 3: FreightX carrier relevancy model
   - optionally combine any subset of sources for outreach build
8. Keep source selection visible in the UI so an operator can see what was included in the run.
9. Add a `Notes` input so the operator can append free-form context to the email.
10. Generate an email draft/template from lane info plus notes and show it to the user for confirmation before send.

## Data Inputs
The outreach layer consumes the canonical outreach-ready carrier dataset built from:
- Source 1: internal Turvo carrier recommendation data
- Source 2: DAT carrier import data
- Source 3: FreightX carrier relevancy model data

For test runs, the outreach layer may also accept a manual recipient list that bypasses the source dataset.

## Suggested Data Model
The repository already contains the core outreach tables in `backend/app/db/models.py`.
This feature should wire them into live sending and event tracking rather than inventing a new schema.

Recommended usage:

### `carrier_outreach_sets`
- one row per outreach build/run
- tracks status, source count, row count, and dedupe count
- should also carry test-run metadata if needed

### `carrier_outreach_rows`
- one canonical carrier row to send to
- stores carrier name, phone, email, MC number, source, source row IDs, and dedupe key

### New or extended outreach tracking tables
If needed, add support for:
- `outreach_messages`
- `outreach_message_events`
- `outreach_replies`
- `outreach_batches`

Suggested fields:
- `lane_id`
- `outreach_set_id`
- `carrier_id` or canonical row reference
- `provider`
- `provider_message_id`
- `channel`
- `status`
- `sent_at`
- `delivered_at`
- `opened_at`
- `clicked_at`
- `replied_at`
- `raw_payload`
- `normalized_payload`
- `reply_body`
- `reply_subject`
- `reply_from_email`

## Event Model
The system should treat Resend callbacks and inbound reply handling as the source of truth for live state.

Normalized event types:
- `sent`
- `delivered`
- `opened`
- `clicked`
- `replied`
- `failed`

Rules:
1. Every outbound email should create a persistent message record.
2. Every provider callback should append a normalized event row.
3. Carrier-level lane metrics should be derived from those events.
4. A reply should update both the message record and the per-carrier summary state.
5. If a reply contains enough data, store the response text for review.

## UI Requirements
### Lane Detail View
Add an outreach section that shows:
- sent count
- delivered count
- opened count
- clicked count
- replied count
- open rate
- click-through rate
- reply rate

### Carrier Response Table
For carriers who opened, clicked, or replied, show:
- carrier name
- email
- phone
- source
- status
- last event
- last event time
- response text snippet when available

### Build Controls
Add controls to the frontend so the user can:
- choose which sources to include:
  - internal
  - DAT
  - FreightX
- choose test mode vs normal outreach mode
- enter manual test email addresses for validation
- enter optional notes that should be injected into the outbound email

### Test Workflow
Manual test sends should be a separate test workflow in the UI rather than only a toggle inside the send form.
That gives us a cleaner guardrail for production sends and makes it obvious when the user is validating the email template.

Recommended structure:
1. Lane outreach form for production sends.
2. Separate test send card or modal for manual test recipients.
3. Shared email template preview for both paths.

## Manual Test Mode
Manual testing should be supported as a first-class workflow.

Recommended behavior:
1. User selects test mode.
2. User enters 3-4 email addresses manually, or any short list needed for verification.
3. User enters optional notes for the message body.
4. The system generates a preview email using lane info plus notes.
5. The user reviews the preview and confirms or edits it.
6. The system sends the same email template and tracking logic to those addresses.
7. The run is flagged as `test` so it can be filtered out from production metrics if needed.
8. The UI clearly shows test runs separately from normal lane outreach.

## Email Template Requirements
The first version should generate a readable plain-text email draft using:
- lane origin and destination
- equipment type
- pickup date when available
- selected carrier source mix
- optional operator notes

The draft should be shown to the user before send so they can confirm:
- subject line
- body copy
- recipients
- source selection
- test mode vs production mode

The preview step should allow the user to:
- edit notes before sending
- regenerate the message
- cancel the send if the draft is not correct

## API Contract
Suggested endpoints:
- `POST /portal/lanes/{lane_id}/outreach-sets`
- `POST /portal/lanes/{lane_id}/outreach/send`
- `GET /portal/lanes/{lane_id}/outreach`
- `GET /portal/lanes/{lane_id}/outreach/{outreach_set_id}`
- `POST /webhooks/resend/events`
- `POST /webhooks/inbound/replies`

Suggested request shape for build/send:
```json
{
  "include_internal": true,
  "include_dat": true,
  "include_freightx": true,
  "test_mode": false,
  "manual_emails": [],
  "notes": ""
}
```

Suggested request shape for a test run:
```json
{
  "include_internal": false,
  "include_dat": false,
  "include_freightx": false,
  "test_mode": true,
  "manual_emails": [
    "test1@example.com",
    "test2@example.com",
    "test3@example.com"
  ],
  "notes": "Please verify the lane summary and formatting."
}
```

## Tracking Rules
1. Sent count increments when Resend accepts the send request.
2. Delivered count increments from provider delivery callbacks.
3. Opened count increments from open tracking callbacks.
4. Clicked count increments from click tracking callbacks.
5. Replied count increments when an inbound reply is matched back to the message or carrier.
6. Repeated webhook deliveries must be idempotent.
7. A carrier should be counted once per metric bucket even if multiple events arrive.

## Observability
Log structured fields for all outreach actions:
- `request_id`
- `lane_id`
- `outreach_set_id`
- `carrier_name`
- `provider`
- `provider_message_id`
- `channel`
- `status`
- `test_mode`
- `source_filter`

## Acceptance Criteria
1. The system can send carrier emails through Resend.
2. Every outbound email is tied to a persistent outreach record.
3. Delivery, open, click, and reply events are tracked and visible in the UI.
4. The lane view shows totals for sent, delivered, opened, clicked, and replied emails.
5. Carriers who interacted with the email show name, email, phone, and response detail when available.
6. The frontend lets the user include or exclude source 1, source 2, and source 3 when building outreach.
7. A manual test-recipient mode exists for sending to 3-4 hand-entered emails or another small test list.
8. Test runs are clearly separated from normal outreach runs.
9. The user can enter notes and preview the exact draft before sending.

## Open Questions
- Do we want one email template for all carriers initially, or a lane-specific subject/body editor from day one?
- Should click/open tracking be treated as metrics only, or should opens/clicks also advance carrier status in the UI?
- Do replies come only from inbound email parsing, or do we also need a provider webhook route for response events?

## Notes for Implementation
- Keep the first version narrow: one lane, one email channel, one tracking provider.
- Prefer deterministic event updates and idempotent webhook handling.
- Make the manual test path easy to use so developers can verify the flow without a large carrier batch.
- Treat Resend webhooks as the source of truth for live status updates and map them back to the correct outbound email row.
- Use a normal service-based workflow for the email-only version; do not introduce LangGraph just for webhook handling.
- Leave a clean boundary so a future multi-channel orchestrator can plug in later without changing the event model.
