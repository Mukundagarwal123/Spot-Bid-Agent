# Frontend Template and Architecture - Flask/Jinja

## Runtime
- Flask server-rendered template for page shell (`/` and `/portal`).
- Vanilla JS module for interactions (lane selection, drawer, tabs, filters, details toggle).
- Internal JSON APIs under `/portal/*` for data hydration.

## Template Structure
1. Left Sidebar
- Active Lanes
- Completed
- Carrier CRM

2. Main Workspace
- Lane table for active/completed tabs
- Carrier CRM table for CRM tab

3. Right Drawer
- Hidden by default
- Opened when a lane is selected
- Contains overview/responses/activity tabs

## Client-Side State (vanilla JS)
- selected tab (`active|completed|crm`)
- selected lane id
- lane status overrides (`active|completed`)
- drawer tab (`overview|responses|activity`)
- response channel filter (`all|email|sms|whatsapp`)
- selected carrier + details toggle

## Notes
- Keep JSON contracts compatible with existing portal endpoint shapes.
- Keep UI behavior deterministic with dummy backend data.
