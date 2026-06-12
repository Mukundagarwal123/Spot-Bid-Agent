# Feature 004 - FreightX Carrier Relevancy Model Source

## Objective
Add the third carrier-ingestion source for lane search: the FreightX carrier relevancy model.

This source uses the model entry point in `FreightX-V1/src/api/models/combine_model.py` to return a ranked carrier DataFrame based on the lane origin zip, destination zip, and the equipment type selected by the user.

This feature is only for Source 3. It does not combine results with the internal Turvo source or the DAT source yet.

## Scope
- In scope:
  - Call the FreightX model with lane zips and equipment type.
  - Normalize the returned pandas DataFrame into carrier source records.
  - Preserve all columns returned by the model, without silently dropping metadata.
  - Normalize `DOCKET_NUMBER` as the carrier identifier.
  - Strip the `MC` prefix from `DOCKET_NUMBER` before saving or returning it.
  - Tag every row with source provenance for future multi-source merging.
- Out of scope:
  - Final merging of Source 1 + Source 2 + Source 3.
  - Cross-source ranking or deduplication.
  - Carrier outreach from this source.
  - Replacing the model with a live API or external service.

## User Flow
1. User creates or opens a lane.
2. User selects an equipment type for the lane.
3. The system calls the FreightX carrier relevancy model with the lane zips and equipment selection.
4. The model returns a ranked pandas DataFrame of candidate carriers.
5. The backend stores the model output as Source 3 carrier records.
6. The UI can display these results independently from the other sources.

## Frontend Inputs
This source relies on lane data that already exists in the portal:
- `origin_zip` (required)
- `destination_zip` (required)
- `equipment_type` (required)

Supported equipment values:
- `dryvan`
- `reefer`
- `flatbed`

## Input Validation Rules
- Trim zip values before sending them to the model.
- Treat empty strings as missing values.
- Reject the request if either zip is missing.
- Reject the request if the equipment type is missing or not one of the supported values.
- Normalize equipment labels from the UI to the model input format expected by FreightX.

## Proposed Source 3 API Contract
Endpoint:
- `POST /portal/carriers/recommendations/freightx-relevancy`

Request example:
```json
{
  "origin_zip": "75001",
  "destination_zip": "85001",
  "equipment_type": "dryvan"
}
```

Validation response example (`400`):
```json
{
  "request_id": "req_123",
  "error": "validation_error",
  "fields": {
    "origin_zip": "origin_zip is required",
    "destination_zip": "destination_zip is required",
    "equipment_type": "equipment_type must be dryvan, reefer, or flatbed"
  }
}
```

## FreightX Model Integration Contract
Use the combined model entry point:
- `FreightX-V1/src/api/models/combine_model.py`
- Function: `run_my_model(source_zip, dest_zip, equipment_list)`

Call pattern:
- `source_zip` = lane origin zip
- `dest_zip` = lane destination zip
- `equipment_list` = a list containing the selected equipment type, such as `["dryvan"]`

Notes:
- The model layer should stay behind a thin adapter/service boundary in the app.
- The adapter should not hardcode model paths in the portal layer.
- If the model output contract changes later, the adapter should be the only place that needs translation.
- If the model emits `MC` instead of `MC_NUMBER`, normalize it to the portal's carrier-contact field naming.

## Expected Model Output Handling
The FreightX model returns a pandas DataFrame of candidate carriers.

The portal must:
- Preserve all returned columns.
  - Do not expose `DOT_NUMBER` in the final Source 3 output.
  - Use `DOCKET_NUMBER` as the primary carrier identifier.
  - Remove the `MC` prefix from `DOCKET_NUMBER` values before saving.
  - Store model provenance for each row.
  - Persist both normalized fields and a raw payload snapshot so no model columns are lost.

Recommended normalized fields:
- `DOCKET_NUMBER`
- `LEGAL_NAME`
- `EMAIL_ADDRESS`
- `PHONE`
- `LABEL`
- `MODEL_USED`
- `SOURCE_MODEL`

If the model emits additional columns, store them in `raw_payload_json` or an equivalent payload field so they remain available for later schema changes.

## Data Model
Recommended storage shape for this source:

### `carrier_relevancy_runs`
- `id`
- `lane_id`
- `origin_zip`
- `destination_zip`
- `equipment_type`
- `model_version`
- `status`
- `row_count`
- `error_message`
- `created_at`

### `carrier_relevancy_records`
- `id`
- `run_id`
- `lane_id`
- `docket_number`
- `legal_name`
- `email_address`
- `phone`
- `label`
- `model_used`
- `source_model`
- `source_type`
- `rank`
- `raw_payload_json`
- `created_at`

This keeps Source 3 isolated while still making it easy to merge later into a shared carrier aggregation table.

## Processing Rules
- Validate the lane input before calling the model.
- Pass exactly one selected equipment type into the model call.
- Use the model's returned row order as the source ranking order.
- Deduplicate within Source 3 by `DOCKET_NUMBER` if the model returns repeated rows.
- Keep the first occurrence of a repeated docket number, unless the model later defines a better source-specific tie-breaker.
- Do not drop any returned columns silently.
- If the model returns no rows, store the run with a `NO_MATCHES` status.
- If the model raises an exception, store the run with an `ERROR` status and a safe message.

## Reliability and Observability
- Log `request_id`, `lane_id`, `origin_zip`, `destination_zip`, `equipment_type`, `row_count`, and `status`.
- Log model runtime and whether the call succeeded or failed.
- Do not log secrets, file paths containing credentials, or raw local environment values.
- Keep model execution isolated so a Source 3 failure does not block future source aggregation work.

## Acceptance Criteria
1. The portal can call the FreightX carrier relevancy model using lane zips and the selected equipment type.
2. The model output is stored as a separate Source 3 carrier dataset.
3. `DOCKET_NUMBER` is saved without the `MC` prefix.
4. All returned model columns are preserved, either as normalized columns or in a raw payload field.
5. `DOT_NUMBER` is not exposed in the final Source 3 output.
6. Missing or invalid zips and equipment values return clear validation errors.
7. A model failure is recorded safely and does not corrupt other source data.
8. Source 3 remains isolated and does not blend with the internal Turvo or DAT sources yet.

## Notes for the Future Multi-Source Merge
- Source 1 remains the internal Turvo carrier network.
- Source 2 remains the DAT pasted-text import.
- Source 3 is the FreightX carrier relevancy model.
- The future aggregator should merge these sources by a shared carrier identity strategy, with `DOCKET_NUMBER` as the primary key for Source 3.
- Keep the Source 3 adapter thin so the later merge step can reuse it without reworking the model integration.
