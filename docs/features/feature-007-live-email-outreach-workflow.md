# Feature 007 - Live Email Outreach Workflow

## Objective
Replace the current dummy lane experience with a live email outreach workflow.

This feature covers:
- lane creation with notes,
- source selection for outreach inputs,
- DAT parsing when DAT is selected,
- email template generation and user approval,
- live send progress,
- webhook-driven metric updates,
- carrier response surfacing,
- source-wise performance metrics,
- and campaign completion handling.

## Scope
- In scope:
  - Email outreach only.
  - Remove dummy lane metrics, dummy carrier CRM, and dummy outreach data from the live workflow.
  - Add a `Notes` field to lane creation.
  - Add source selection for:
    - Internal
    - DAT
    - CRR Model
    - Manual Emails
  - Auto-select the first three sources by default.
  - Allow manual emails to be added optionally.
  - If DAT is selected, prompt for DAT data and parse it before continuing.
  - Generate an email template using lane details and notes.
  - Let the user edit the email content before sending.
  - Show a live activity log during outreach build and send.
  - Show top-level metrics:
    - total sent
    - total delivered
    - total opened
    - total responded
  - Show carriers who opened or responded so the operator can follow up.
  - Show source-wise metrics at the bottom:
    - delivered
    - opened
    - replied
  - Provide a follow-up action for non-responders.
  - Provide a `Covered` or `End Campaign` action to close the lane.
- Out of scope:
  - SMS.
  - WhatsApp.
  - Multi-step automation beyond email follow-up.
  - Full autonomous negotiation.

## Problem Statement
The current experience is built around dummy data and a side drawer.
That makes it hard to run a real outreach workflow.

We need a live lane page that:
- accepts real lane inputs,
- builds outreach from selected sources,
- shows exactly what email will be sent,
- starts the send only after user approval,
- and updates in real time as Resend webhooks arrive.

## UX Direction
Use the attached references as guidance:
- the lane creation form should stay simple and structured,
- the lane detail experience should open as a full page,
- the page should show progress and metrics clearly,
- and the workflow should feel operational rather than simulated.

The frontend should also feel more distinctive and polished than a standard dashboard:
- use a strong visual hierarchy with a dark or high-contrast header and a lighter content surface,
- make the progress state feel alive with purposeful motion or staged reveal, not generic spinners,
- use source-specific color accents so Internal, DAT, CRR Model, and Manual Emails are easy to distinguish,
- give the email preview area the visual weight of a real drafting workspace,
- make the recipient/status table feel like a live operations console rather than a plain CRUD list,
- and avoid default SaaS sameness by using more deliberate spacing, typography, and section framing.

## Primary Users
- Operations users launching outreach.
- Internal testers validating the email flow.
- Admin users monitoring engagement and source quality.

## Functional Requirements
1. Remove dummy data from the live workflow.
2. Add `Notes` to lane creation.
3. Add source selection:
   - Internal
   - DAT
   - CRR Model
   - Manual Emails
4. Auto-select Internal, DAT, and CRR Model by default.
5. Allow the user to add or remove any source before outreach is built.
6. If DAT is selected, prompt for DAT data and parse it before moving to template review.
7. Allow manual email addresses to be entered when the user wants to test or supplement a lane.
8. Generate an email template that includes:
   - lane origin/destination
   - equipment type
   - pickup date if present
   - notes
   - selected source mix
9. Display the template to the user for confirmation.
10. Allow the user to edit the subject and body before send.
11. After approval, show an activity log for:
   - internal carrier lookup
   - DAT parsing
   - CRR model lookup
   - manual email validation
   - outreach send progress
12. Show total send counts and source-wise counts before the final send.
13. Open the lane as a full page when the user clicks it.
14. Show live outreach progress on that page.
15. Update metrics automatically from Resend webhooks.
16. Show carriers who opened or responded.
17. Provide a follow-up action for non-responders.
18. Provide a `Covered` or `End Campaign` action.
19. When a campaign is ended, move the lane to completed and stop updating metrics for it.

## Lane Creation Form
The `Add Lane` flow should include:
- origin city
- origin state
- origin zip
- destination city
- destination state
- destination zip
- equipment
- pickup date
- notes
- source selectors
- manual email input section

### Default Source Behavior
On form open:
- Internal = selected
- DAT = selected
- CRR Model = selected
- Manual Emails = not selected unless the user enters them

### Manual Email Behavior
If the user adds manual emails:
- validate basic email format,
- store them separately from source-derived carriers,
- and clearly label them as test/manual recipients.

## DAT Flow
If DAT is selected:
1. Prompt the user to paste DAT data.
2. Parse the data.
3. Show parsed record count.
4. Continue to template generation only after parsing succeeds.

## Email Template Requirements
The system should generate a preview email using:
- lane details
- notes
- selected source mix

The user should be able to:
- edit the subject,
- edit the body,
- and approve or cancel before sending.

The preview step should make it obvious:
- who will receive the email,
- how many emails will be sent,
- and which sources contributed to the recipient list.

## Outreach Workflow
Recommended flow:
1. Create lane.
2. Select sources.
3. Parse DAT if selected.
4. Build recipient set.
5. Generate email template.
6. Show preview to user.
7. Show activity log and counts.
8. User confirms send.
9. Send emails.
10. Open live progress page.
11. Update metrics from webhooks.
12. Surface opens and responses.
13. Allow follow-up to non-responders.
14. Allow campaign end / covered action.

## Progress Page Requirements
When outreach starts, the lane page should show:
- a live status header,
- top-level metrics,
- recipient table,
- source-wise metrics,
- activity log,
- and action buttons.

The page should feel like an execution workspace:
- a sticky summary header for the current lane,
- a prominent timeline or stage rail for build/send progress,
- a clear divide between draft review, send progress, and live results,
- and a lower section for source comparison and follow-up actions.

### Top-Level Metrics
Show:
- total email sent
- delivered
- opened
- responded

Response should supersede open counts for reporting purposes:
- if a carrier replies, they are counted as responded,
- and that carrier should also be considered opened.

### Recipient Table
Show only carriers relevant to outreach, especially those who:
- opened,
- clicked,
- or responded.

Recommended columns:
- carrier name
- email
- phone
- source
- status
- last activity
- attempts
- response snippet if available

## Follow-Up Action
Add a follow-up button that sends a follow-up email to carriers who have not replied.

Rules:
- do not resend to carriers who already responded unless the user explicitly chooses that behavior,
- keep follow-up tracked as a separate outreach attempt,
- update metrics separately for the follow-up batch.

## End Campaign / Covered Action
The lane detail page should have a final action:
- `Covered`
- or `End Campaign`

When this is used:
- mark the lane as completed,
- stop updating metrics for that lane,
- and keep historical data visible for review.

## Data Model
The existing outreach tables should be extended or used to support live data.

Suggested tables or logical entities:
- `lanes`
- `outreach_sets`
- `outreach_recipients`
- `outreach_messages`
- `outreach_events`
- `outreach_campaign_logs`

Suggested tracking fields:
- `lane_id`
- `outreach_set_id`
- `recipient_email`
- `carrier_name`
- `phone`
- `source`
- `source_type`
- `provider_message_id`
- `status`
- `sent_at`
- `delivered_at`
- `opened_at`
- `replied_at`
- `response_text`
- `attempt_number`
- `is_manual_email`
- `is_follow_up`

## Event Handling
The system must continuously update metrics from webhook or provider event updates.

Rules:
1. Each webhook event must map to a single outbound message or recipient.
2. Message state should update incrementally as events arrive.
3. If a reply arrives, the recipient should be counted as responded.
4. If a recipient has replied, they should also be treated as opened.
5. Campaign metrics must not double count repeated webhook deliveries.
6. Once a lane is marked completed, its metrics should be frozen.

## Source-Wise Metrics
At the bottom of the lane page, show metrics by source:
- Internal
- DAT
- CRR Model
- Manual Emails

For each source, show:
- delivered
- opened
- replied

This should help the operator compare which source performs best for outreach quality.

## API Contract
Suggested endpoints:
- `POST /portal/lanes`
- `GET /portal/lanes`
- `GET /portal/lanes/{lane_id}`
- `POST /portal/lanes/{lane_id}/source-selection`
- `POST /portal/lanes/{lane_id}/dat-imports`
- `POST /portal/lanes/{lane_id}/outreach/template`
- `POST /portal/lanes/{lane_id}/outreach/send`
- `POST /portal/lanes/{lane_id}/outreach/follow-up`
- `POST /portal/lanes/{lane_id}/outreach/end`
- `POST /webhooks/resend/events`

## Observability
Log structured fields for every important step:
- `request_id`
- `lane_id`
- `outreach_set_id`
- `recipient_email`
- `source`
- `provider_message_id`
- `event_type`
- `status`
- `attempt_number`
- `is_follow_up`
- `is_manual_email`

## Acceptance Criteria
1. Dummy live-workflow data is removed.
2. Lane creation supports notes.
3. Lane creation supports source selection with Internal, DAT, CRR Model, and Manual Emails.
4. Internal, DAT, and CRR Model are selected by default.
5. DAT selection triggers a paste/parse step.
6. The user sees a generated email template before sending.
7. The user can edit the email content before confirming send.
8. Clicking a lane opens a full page, not a side drawer.
9. The lane page shows live send progress and webhook-driven metrics.
10. Top metrics show sent, delivered, opened, and responded.
11. Carriers who opened or responded are visible for follow-up.
12. A follow-up action exists for non-responders.
13. A Covered/End Campaign action completes the lane and freezes metrics.
14. Source-wise delivered/opened/replied metrics appear at the bottom.
15. SMS and WhatsApp are disabled for this phase.

## Open Questions
- Should manual emails be treated as test-only addresses or as a real fourth source bucket?
- Should the template preview be a modal, a separate step, or an inline section on the lane page?
- Should the follow-up button reuse the same template with a different subject line, or open a second preview step?
- Should `Covered` and `End Campaign` be separate labels or the same action with different wording?

## Notes for Implementation
- Keep this feature email-only.
- Remove dummy content paths that can conflict with live outreach data.
- Keep the event model general enough to support future SMS and WhatsApp later.
- Use the screenshots as interaction references, but keep the final UI cleaner and more operational.
