# Frontend UX Spec - Phase 1 Manual Lane Simulator (Flask/Jinja)

## Goal
Provide a professional brokerage-style portal using server-rendered Flask templates with minimal vanilla JS interactions.

## Main Screens
1. Portal shell with left nav tabs: Active Lanes, Completed, Carrier CRM
2. Lane table workspace
3. Right-side lane detail drawer

## Active/Completed Lane UX
1. Shipment-style lane table with lane/equipment/pickup/contacted/responded/status columns.
2. Clicking a row opens the right detail drawer.
3. Drawer hidden until lane is selected.

## Detail Drawer UX
1. Header with lane summary and status selector.
2. Tabs:
- Overview
- Carrier Responses
- Activity Log
3. Overview shows channel overview cards and response summary.
4. Carrier Responses shows channel filters + responded carriers list + communication history.
5. Carrier Details toggle shows MC number, email, and contact number.

## Carrier CRM Tab
1. Full carrier profile table.
2. Uses lane-selected context to render snapshot history.

## UX Success Criteria
1. Full-width responsive layout (no fixed root-width constraints).
2. No clipped/overlapping content in drawer/cards.
3. Drawer interactions and filters remain stable on desktop/tablet/mobile.
