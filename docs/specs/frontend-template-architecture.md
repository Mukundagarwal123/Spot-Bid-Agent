# Frontend Template and Architecture - Feature 001A

## Existing Frontend Baseline
Current frontend already contains:
1. Lane intake form components
2. Active lanes board components
3. Lane detail metrics components
4. Carrier CRM component

## Target Template Structure
`PortalShell`
1. `LeftSidebar`
- `ActiveLanesTab`
- `CarrierCRMTab`
2. `MainContent`
- `LanesGridView` (default on Active Lanes)
3. `RightDetailPanel`
- `LaneHeader`
- `MetricsCards`
- `ChannelBreakdown`
- `CarrierResponses`
- `ActivityTimeline`

## Suggested Component Mapping
Reuse/refactor:
1. `ActiveLanesBoard.tsx` -> `LanesGridView.tsx`
2. `LaneCard.tsx` -> row/cell renderer
3. `LaneDetailPanel.tsx` -> right-side drawer panel
4. `CarrierCRMView.tsx` -> full tab page
5. `KPIStrip.tsx` and `ActivityTimeline.tsx` keep with visual redesign

## State Model
UI state:
1. `activeTab`: `active_lanes | carrier_crm`
2. `selectedLaneId`
3. `laneStatusFilter`: `active | covered | completed`
4. `panelOpen`

Data state:
1. `lanes[]`
2. `laneDetail`
3. `carrierCrmRows[]`

## Responsive Rules
Desktop:
1. 3-column shell: sidebar + main + detail panel.

Tablet:
1. Sidebar collapsible.
2. Detail panel overlays main content.

Mobile:
1. Stack views.
2. Detail panel as full-screen sheet.

## Visual System Tokens (Starter)
1. Primary: `#0B4A6F`
2. Accent: `#0E7490`
3. Success: `#15803D`
4. Warning: `#B45309`
5. Danger: `#B91C1C`
6. Surface: `#F8FAFC`
7. Border: `#CBD5E1`
8. Text strong: `#0F172A`
9. Text muted: `#475569`

## Interaction Standards
1. All key actions within two clicks.
2. Visible loading/empty/error states.
3. Keyboard focus states on rows/buttons.
4. Sticky header for list columns on long tables.
