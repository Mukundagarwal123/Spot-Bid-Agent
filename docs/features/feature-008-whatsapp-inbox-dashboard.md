# Feature 008 - WhatsApp Inbox Dashboard and Live Conversation Handling

## Objective
Build an internal WhatsApp dashboard that can receive, display, and send WhatsApp messages through the WhatsApp Business API.

This feature is the operational inbox for WhatsApp, not the campaign layer.
Operators should be able to:
- see inbound messages arrive through webhooks,
- browse full conversation history by contact,
- send replies and outbound messages from the dashboard UI,
- and review delivery/read state for each message.

## Scope
- In scope:
  - WhatsApp only.
  - Webhook-driven inbound message ingestion.
  - Message status ingestion for sent, delivered, and read updates.
  - Conversation list and thread view.
  - Contact profile panel with WhatsApp history.
  - Manual send/reply composer from the dashboard.
  - Search, filters, unread state, and live refresh behavior.
  - A frontend that feels like a real inbox, not a generic admin table.
- Out of scope:
  - Email outreach.
  - SMS outreach.
  - Automated campaign sequencing.
  - Meta coexistence API.
  - Full multi-agent negotiation automation.

## Problem Statement
We can already test WhatsApp Business API messages, but we do not have a proper operational surface for day-to-day work.

The team needs a dashboard that acts like our own WhatsApp-style inbox so we can:
- monitor incoming carrier messages,
- reply from one place,
- view the full thread per contact,
- and later connect the inbox to outreach campaigns.

## Primary Users
- Operations users managing carrier communication.
- Internal testers validating WhatsApp webhooks and message sends.
- Future campaign operators who will eventually launch outbound WhatsApp outreach.

## Product Direction
Think like a frontend developer building a production messaging workspace:
- the left side should behave like a conversation list with avatars, names, unread badges, last message preview, and timestamps,
- the center should be a chat thread with clear inbound/outbound bubbles and status ticks,
- the right side should show contact details, identifiers, tags, and history,
- the composer should feel instant and safe for manual sending,
- and the whole page should work smoothly on desktop first, then collapse cleanly on smaller screens.

The UI should feel more like an operations console than a CRUD dashboard:
- strong hierarchy,
- clear active conversation focus,
- sticky header with channel and contact state,
- live activity indicators,
- graceful empty states,
- and subtle motion for new messages and thread changes.

## Functional Requirements
1. Show a WhatsApp inbox page in its own route.
2. Display a list of conversations with:
   - contact name
   - phone number
   - last message preview
   - unread badge
   - last activity timestamp
   - status
3. Show a full message thread for the selected contact.
4. Distinguish inbound and outbound messages visually.
5. Show message delivery/read state for outbound messages.
6. Persist all webhook events and tie them back to the correct message when possible.
7. Allow the operator to send a manual reply from the dashboard.
8. Allow the operator to start a new outbound conversation from the dashboard when needed.
9. Keep the conversation history visible after refresh.
10. Provide contact details and conversation metadata in a side panel.
11. Support live updates without requiring a full page reload.
12. Support search and filtering by contact, unread state, and status.

## Data Model
The implementation should be channel-aware and future-proof.

Suggested entities:

### `messaging_contacts`
- one row per WhatsApp contact
- phone number, display name, labels/tags, metadata, timestamps

### `messaging_conversations`
- one row per contact thread
- channel, status, unread count, last message preview, last activity time

### `messaging_messages`
- one row per inbound or outbound message
- conversation ID, contact ID, direction, body, provider message ID, template flag, timestamps, status

### `messaging_message_events`
- append-only webhook/event log
- message ID, event type, event time, raw payload, idempotency key

### `messaging_webhook_deliveries`
- optional audit log for provider webhook payloads and retry handling

## Event Model
The dashboard should treat webhook events as the source of truth.

Normalized event types:
- `received`
- `sent`
- `delivered`
- `read`
- `failed`
- `template_sent`

Rules:
1. Every inbound WhatsApp message should create or update a conversation thread.
2. Every outbound WhatsApp message should persist a message record before or immediately after send.
3. Each provider callback should append an event row.
4. Status updates should update the visible message state in the thread.
5. Duplicate webhooks must be idempotent.
6. The newest activity should surface the conversation to the top of the inbox.

## UI Requirements
### Inbox Page
The inbox page should include:
- conversation list
- thread view
- contact details panel
- composer
- search and filters
- live status indicators

### Thread View
Show:
- sender name or phone
- message body
- sent/delivered/read timestamps when available
- inbound/outbound distinction
- grouping by conversation date
- loading state while a thread is fetched

### Composer
The composer should support:
- manual text replies
- sending to an existing contact
- starting a new thread when permitted
- clear send confirmation and error states

## API Contract
Suggested endpoints:
- `GET /whatsapp`
- `GET /api/whatsapp/conversations`
- `GET /api/whatsapp/conversations/{conversation_id}`
- `POST /api/whatsapp/conversations/{conversation_id}/messages`
- `POST /api/webhooks/whatsapp`
- `GET /api/whatsapp/contacts/{contact_id}`

## Acceptance Criteria
1. The app has a WhatsApp inbox route that shows conversations.
2. Operators can open a thread and see full message history.
3. Inbound WhatsApp messages arrive through webhooks and appear in the UI.
4. Outbound replies can be sent from the dashboard.
5. Message delivery and read state are visible when available.
6. Conversation history survives refresh.
7. The dashboard feels like a real messaging workspace, not a generic table.

## Notes for Implementation
- Keep the first version focused on operational inbox behavior.
- Do not build campaign automation yet.
- Leave a clean boundary so WhatsApp outreach campaigns can reuse the same conversation and message model later.
