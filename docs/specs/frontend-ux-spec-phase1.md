# Frontend UX Spec - Phase 1 Manual Lane Simulator

## Goal
Help ops users visualize spot-bid workflow behavior per lane using dummy data before live integrations are built.

## Main Screens
1. Lane Intake Form
2. Active Lanes Board
3. Lane Detail Activity View
4. Carrier CRM View

## Lane Intake Form
Fields:
1. Origin city/state/zip
2. Destination city/state/zip
3. Stops repeater (add/remove)
4. Equipment type
5. Pickup date (optional)

Validation:
1. Origin and destination are required.
2. Equipment type is required.
3. Stops are optional.

## Active Lanes Board
Each lane card/tab displays:
1. Origin -> Destination
2. Equipment
3. Status badge
4. Last updated time
5. Quick metrics preview (sent/responded)

## Lane Detail Activity View
Sections:
1. KPI strip (email/sms/whatsapp and responses)
2. Activity timeline
3. Channel performance table
4. Carrier response list

## Carrier CRM View
Table columns:
1. Carrier
2. Times contacted
3. Times responded
4. Response rate
5. Average response time
6. Preferred channel
7. Last contacted

## Empty and Loading States
1. Empty lanes:
- show CTA: "Create your first lane"
2. Loading:
- skeleton cards and tables
3. No CRM data:
- show friendly empty message

## Phase 1 UX Success Criteria
1. User can create lane in under 30 seconds.
2. User can open lane details in one click.
3. User can quickly understand channel performance and carrier responsiveness.
