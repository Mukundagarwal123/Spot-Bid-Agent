# Claude Plan Prompt - Outreach Layer: Resend Email + Tracking

```text
Read these files first and confirm by listing them:
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/CLAUDE.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/specs/product-spec.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/specs/technical-spec.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/data-model.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/roadmap.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-005-multi-source-carrier-aggregation.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-006-outreach-layer-resend-email-tracking.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/backend/app/db/models.py
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/backend/app/web/templates/portal.html
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/backend/app/web/static/portal.js

Task:
Create an implementation PLAN ONLY for the live outreach layer.

Context:
- The carrier data layer already exists and produces an outreach-ready merged dataset from the three carrier sources.
- This new work is email only for now.
- Email sending will use Resend.
- We need to track sent, delivered, opened, clicked, and replied metrics.
- We also need a manual test mode that can send to a small list of hand-entered emails.
- The frontend should let the user choose which sources to include:
  - source 1 internal
  - source 2 DAT
  - source 3 FreightX carrier relevancy model
- The UI should include a Notes field and an email preview/confirmation step before send.

Requirements:
1. Plan the backend model changes needed for live outreach and event tracking.
2. Plan the Resend send flow and webhook/event ingestion flow.
3. Plan how per-lane and per-carrier metrics are derived.
4. Plan how reply text and responder details should be stored and surfaced.
5. Plan the frontend changes for source selection and manual test-recipient entry.
6. Plan the email template generation flow using lane details plus user notes.
7. Plan the preview/confirmation UX before any send is finalized.
8. Plan the test strategy, including a small 3-4 email validation run.
9. Do not write code yet.

Deliver:
1. Implementation phases
2. Backend/API plan
3. Frontend/UI plan
4. Data model and event-tracking plan
5. Testing and validation plan
6. Risks, assumptions, and open questions
```
