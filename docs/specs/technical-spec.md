# Technical Spec - Spot Bid Agent

## Architecture Overview
- `Flask` monolith receives Turvo/manual events, renders portal pages, and exposes internal JSON APIs.
- `LangGraph` orchestrates per-load workflow state transitions.
- Async workers process outreach and callback events.
- Event store captures every communication event.
- Jinja + vanilla JS UI reads aggregated load activity from JSON API endpoints.

## Why LangGraph
LangGraph is a strong choice because you expect concurrent workflows and stateful transitions. It gives explicit state graphs, recoverability, and easier branching for retries/escalations.

## Key Components
1. `trigger-service`
- Receives Turvo webhook/tag events.
- Performs idempotency checks.
- Starts workflow execution.

2. `carrier-ingestion-service`
- Normalizes carriers from DAT, CSV, internal DB into one schema.
- Deduplicates by MC/DOT/email/phone.
- Adds source confidence score.

3. `outreach-service`
- Sends email via Resend.
- Sends SMS/WhatsApp via Twilio.
- Stores provider message IDs.

4. `event-ingestion-service`
- Receives open/click/reply/status webhooks.
- Maps callbacks to load + carrier + channel.

5. `negotiation-state-service`
- Updates per-carrier status: contacted -> engaged -> negotiating -> won/lost.

6. `dashboard-service`
- Aggregates per-load stats and timelines.

## Data Model (High Level)
- `loads`
- `spotbid_runs`
- `carriers`
- `carrier_contacts`
- `outreach_messages`
- `message_events`
- `negotiation_threads`
- `load_outcomes`

## Critical Engineering Requirements
- Idempotency key: `shipment_id + tag_event_id`.
- Retry policy with dead-letter handling.
- Exactly-once semantics at business layer (even if transport retries).
- Correlation ID in all logs/events.
- UTC timestamps everywhere.

## Concurrency Strategy
- One workflow instance per load tag event.
- Guard duplicate triggers with unique constraints + Redis lock (optional).
- Use queue-based processing for high throughput.

## Testing Strategy
- Unit tests for each graph node.
- Integration tests for webhook -> workflow start.
- Contract tests for provider callbacks.
- Load test for burst tags (N loads in parallel).
