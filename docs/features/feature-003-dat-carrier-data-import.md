# Feature 003 - DAT Carrier Data Import and Lane-Level Source Storage

## Objective
Add a second carrier-data source for a lane: DAT pasted text.

After a user creates a lane in the frontend, the app should optionally prompt them to paste DAT text. The system should extract carrier contact details from that pasted text and store them alongside the existing internal carrier data for the same lane.

This feature does not replace the internal carrier source from Feature 002. It adds a second, lane-scoped source: DAT.

## Scope
- In scope:
  - Prompt for DAT paste immediately after lane creation.
  - Parse copied DAT text into structured carrier records.
  - Store DAT results separately from internal carrier results.
  - Show both source types for the same lane in the UI.
  - Keep source provenance visible per record.
- Out of scope:
  - Live DAT API integration.
  - Automatic browser scraping.
  - Re-ranking internal carriers against DAT carriers in this phase.
  - Outreach from DAT data in this phase.

## User Flow
1. User adds a lane from the frontend.
2. After lane save, the UI asks whether the user wants to upload DAT data.
3. If the user selects yes, a paste area opens.
4. User pastes raw DAT text copied from DAT.
5. User submits the pasted content.
6. Backend parses the text into carrier rows.
7. Parsed DAT rows are saved as a separate source for that lane.
8. Lane detail shows both:
   - internal carrier data
   - DAT carrier data

## Frontend Requirements
### Post-lane-create prompt
- Show a modal, drawer step, or inline follow-up after lane creation.
- Prompt text should ask if the user wants to upload DAT data for this lane.
- If the user chooses no, continue normally and keep the lane active.
- If the user chooses yes, show:
  - a large multiline paste input
  - a short helper note telling the user to paste copied DAT text
  - a submit action to parse and save the data

### DAT paste UX
- Support plain copied text only.
- Do not require file upload in this phase.
- Show parsing success/failure clearly.
- Display the number of extracted carrier rows after submit.
- Surface row-level errors only when parsing cannot safely infer required fields.

### Lane detail UX
- Add a source section for the lane with at least:
  - `Internal`
  - `DAT`
- Each source should be independently viewable.
- DAT results should not overwrite internal carrier data.
- If one source is missing, the other source still renders normally.

## DAT Extraction Contract
The parser should follow these rules when converting pasted DAT text into structured data:

### Output shape
Each DAT post should produce one JSON object with:
- `carrier_name`
- `email`
- `phone`
- `mc_number`
- `source_notes`

### Extraction rules
1. One DAT post equals one result.
2. `Post Details Contact` has highest priority.
3. If `Post Details Contact` contains a phone, use it as `phone`.
4. If `Post Details Contact` contains an email, use it as `email`.
5. If email is missing from `Post Details`, fall back to the carrier/company profile email.
6. If phone is missing from `Post Details`, fall back to the carrier/company profile phone.
7. If `Post Details Contact` is empty or missing, use both email and phone from the carrier/company profile.
8. `mc_number` always comes from the carrier/company profile MC number.
9. Ignore driver phone in comments unless no carrier contact phone exists anywhere.
10. Do not guess missing values. Use empty strings when data cannot be found safely.
11. Preserve the posted carrier name exactly as shown in the DAT row.

### Name preservation examples
- `Go To Logistics Inc/Non Stop Logistics Inc` must remain exactly that string.
- Do not normalize away slashes, punctuation, or suffixes.

## Backend API Contract
### Create DAT import for a lane
`POST /portal/lanes/{lane_id}/dat-imports`

Request example:
```json
{
  "raw_text": "pasted DAT content here"
}
```

Success response example:
```json
{
  "lane_id": "bca6b2b2-0b3a-4d3b-8e1f-73c2e2d7a9f0",
  "source": "dat",
  "parsed_count": 12,
  "created_count": 12,
  "status": "ok"
}
```

Validation response example:
```json
{
  "error": "validation_error",
  "fields": {
    "raw_text": "DAT text is required"
  }
}
```

## Data Model
Add a lane-scoped source model so the app can store multiple carrier datasets for one lane.

Recommended storage shape:
- `portal_lane_carrier_sources`
  - `id`
  - `lane_id`
  - `source_type` (`internal | dat`)
  - `raw_text` or `raw_payload`
  - `parsed_count`
  - `status`
  - `created_at`
- `portal_lane_carrier_records`
  - `id`
  - `lane_id`
  - `source_id`
  - `carrier_name`
  - `email`
  - `phone`
  - `mc_number`
  - `source_notes`
  - `source_type`

This keeps internal and DAT records separate while still making them queryable per lane.

## Processing Rules
- Validate lane exists before accepting DAT text.
- Trim pasted input before parsing.
- Reject empty paste submissions.
- Normalize output to a consistent carrier record schema.
- Deduplicate rows within the DAT paste when the same carrier appears multiple times with the same MC number.
- Store raw text for audit/debugging.
- Keep parsing deterministic for the same input.

## Security And Reliability
- Do not hardcode any parser API key or model key in the source file.
- Use environment variables for parser credentials and model configuration.
- Log lane ID, source type, and parsed count, but never log secrets.
- If the parser fails, return a safe error without losing the created lane.

## Acceptance Criteria
1. After lane creation, the frontend asks whether the user wants to upload DAT data.
2. Users can paste DAT text instead of uploading a file.
3. DAT text is parsed into structured carrier rows.
4. Each DAT row preserves carrier name exactly as shown in DAT.
5. Internal carrier data and DAT data both remain available for the same lane.
6. A lane can have internal data only, DAT data only, or both.
7. Missing values are returned as empty strings rather than guessed values.
8. DAT storage does not overwrite the existing internal carrier source.

## Definition Of Done
- Lane creation flow includes the DAT follow-up prompt.
- Backend accepts pasted DAT text and stores parsed results per lane.
- Lane detail UI can show both internal and DAT carrier sources.
- The DAT source remains isolated and additive to the existing carrier workflow.
