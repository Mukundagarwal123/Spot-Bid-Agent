# Feature 001A - Professional Frontend Redesign (Manual Lane Simulator)

## Goal
Redesign the portal UI to a professional brokerage-style experience using the current manual-lane dummy-data workflow.

## Reference Inputs
Use these reference images:
1. `images/Screenshot 2026-05-27 130754.png`
2. `images/Screenshot 2026-05-27 131038.png`

## Navigation Structure
Left sidebar tabs:
1. `Active Lanes`
2. `Carrier CRM`

## Active Lanes UX
Main list should resemble a shipment grid/table:
1. Lane identifier
2. Equipment
3. Pickup details
4. Delivery details
5. Assigned status
6. Action (`View`)

Clicking a lane opens right-side detail panel/drawer.

## Lane Detail Panel UX
Top section:
1. Lane id / route summary
2. Status (`active`, `covered`, `completed`)
3. Assignee and quick actions

Tabs/sections:
1. `Overview`
2. `Outreach`
3. `Carrier Responses`
4. `Activity Log`

Required content:
1. Contact metrics:
- carriers contacted
- channels used
- email sent/opened/clicked/replied
- sms sent/replied
- whatsapp sent/replied
2. Carrier response list:
- carrier name
- channel
- response status
- response time
- chat/message history snippet
3. Timeline with latest events first.

## Covered/Completed Flow
1. Human can set lane status to `covered`.
2. Covered/completed lanes should appear in a separate section/tab in Active Lanes.
3. Status changes must be reflected in list and detail panel.

## Carrier CRM Tab UX
Show full carrier profile directory with:
1. Carrier name
2. Times contacted
3. Times responded
4. Response rate
5. Preferred channel
6. Last contact time
7. Short interaction history

## Design Requirements
1. Professional look, clean brokerage SaaS style.
2. Responsive desktop-first layout with tablet support.
3. Accessible color contrast and typography hierarchy.
4. Consistent spacing system and component states.
5. No placeholder "toy UI" visuals.

## Reuse Strategy
Keep existing backend/dummy logic where possible.
Focus this feature on:
1. Information architecture
2. Layout system
3. Component styling
4. Interaction polish

## Definition of Done
1. Two-tab left navigation implemented.
2. Active lane list + right detail panel implemented.
3. Covered/completed lane grouping implemented.
4. Carrier CRM tab production-looking and responsive.
5. Existing dummy metrics and timeline still functional.
