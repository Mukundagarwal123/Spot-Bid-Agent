# Claude Plan Prompt - Live Email Outreach Workflow

```text
Read these files first and confirm by listing them:
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/CLAUDE.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/specs/product-spec.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/specs/technical-spec.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/data-model.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/roadmap.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-005-multi-source-carrier-aggregation.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-006-outreach-layer-resend-email-tracking.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-007-live-email-outreach-workflow.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/backend/app/db/models.py
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/backend/app/web/templates/portal.html
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/backend/app/web/static/portal.js

Task:
Create an implementation PLAN ONLY for the live email outreach workflow.

Context:
- Remove dummy data from the live outreach path.
- The workflow is email only for now.
- SMS and WhatsApp must be disabled in this phase.
- Lane creation now needs a Notes field.
- The user should choose data sources:
  - Internal
  - DAT
  - CRR Model
  - Manual Emails
- Internal, DAT, and CRR Model should be selected by default.
- If DAT is selected, the user must paste DAT data for parsing.
- The system should generate an email template using lane info and notes.
- The user should preview and modify the template before sending.
- Clicking a lane should open a full page, not a side drawer.
- The page should show live send progress and webhook-driven metrics.
- We need top-level metrics, source-wise metrics, carrier follow-up visibility, and a campaign end action.
- The frontend should be creative and polished, not a generic admin dashboard.

Requirements:
1. Plan how to remove dummy data from the live workflow without breaking the rest of the portal.
2. Plan the backend changes for lane notes, source selection, DAT parsing, template generation, and send orchestration.
3. Plan the frontend redesign so lane clicks open a dedicated page instead of a drawer.
4. Plan the live progress/log area and the top/bottom metrics sections.
5. Plan webhook-driven metric updates that map back to the correct outbound email rows.
6. Plan how to show carriers who opened or responded.
7. Plan the follow-up action for non-responders.
8. Plan the `Covered` / `End Campaign` action and metric freezing.
9. Plan a more creative frontend treatment with stronger hierarchy, source-specific accents, and a premium execution-workspace feel.
10. Keep the plan email-only and explicitly exclude SMS/WhatsApp for now.

Deliver:
1. Implementation phases
2. Backend/API plan
3. Frontend/UI plan
4. Data model and event-tracking plan
5. Testing and validation plan
6. Risks, assumptions, and open questions
```
