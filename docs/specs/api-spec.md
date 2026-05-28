# API Spec (Initial) - Spot Bid Agent

## External Webhook Endpoints
1. `POST /webhooks/turvo/spotbid-tag`
- Receives shipment tag events.
- Validates signature.
- Enqueues workflow.

2. `POST /webhooks/resend/events`
- Email delivery/open/click/reply events.

3. `POST /webhooks/twilio/status`
- SMS/WhatsApp delivery and engagement events.

4. `POST /webhooks/twilio/inbound`
- Inbound replies from SMS/WhatsApp.

## Internal API Endpoints
1. `GET /loads/{load_id}/activity`
- Returns dashboard summary + timeline.

2. `GET /loads/{load_id}/carriers`
- Returns contacted carriers and statuses.

3. `POST /loads/{load_id}/outreach/retry`
- Retries outreach to failed targets.

4. `GET /runs/{run_id}`
- Workflow execution status.

## Response Principles
- All responses include `request_id`.
- All event payloads stored with raw + normalized representation.
- Pagination for list endpoints.
