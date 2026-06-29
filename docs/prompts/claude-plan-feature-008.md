# Claude Plan Prompt - WhatsApp Inbox Dashboard

```text
Read these files first and confirm by listing them:
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/CLAUDE.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/specs/product-spec.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/specs/technical-spec.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/data-model.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/roadmap.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-006-outreach-layer-resend-email-tracking.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-007-live-email-outreach-workflow.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-008-whatsapp-inbox-dashboard.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/backend/app/db/models.py
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/backend/app/web/templates/portal.html
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/backend/app/web/static/portal.js

Task:
Create an implementation PLAN ONLY for the WhatsApp inbox dashboard and live conversation handling.

Context:
- We do NOT have Meta coexistence API.
- We DO have the normal WhatsApp Business API and test messages are already working.
- The main goal right now is to send and receive WhatsApp messages through our own dashboard UI.
- This is not the campaign automation layer yet.
- We need a real inbox-style surface where operators can see conversation history, reply, and monitor incoming messages.
- Think like a frontend developer as much as a backend engineer:
  - build the dashboard like a real messaging workspace,
  - not like a generic CRUD admin page,
  - with conversation list, active thread panel, contact details, and composer.

Requirements:
1. Plan the messaging data model for contacts, conversations, messages, and webhook events.
2. Plan how inbound WhatsApp webhooks create/update the thread history.
3. Plan how outbound sends from the dashboard are persisted and mapped to provider message IDs.
4. Plan how delivery/read/status updates are ingested and reflected in the UI.
5. Plan the inbox layout and thread layout like a real WhatsApp-style dashboard.
6. Plan the composer/reply flow for sending messages from the dashboard UI.
7. Plan search, unread indicators, live refresh, and contact detail behavior.
8. Plan how this same architecture can later support WhatsApp outreach campaigns without being rewritten.
9. Explicitly exclude email outreach implementation in this feature.
10. Explicitly exclude SMS outreach implementation in this feature.

Deliver:
1. Implementation phases
2. Backend/API plan
3. Frontend/UI plan
4. Data model and event-tracking plan
5. Testing and validation plan
6. Risks, assumptions, and open questions
```
