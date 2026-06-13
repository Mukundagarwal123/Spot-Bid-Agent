# Feature 005 - Multi-Source Carrier Aggregation and Outreach Dataset

## Objective
Combine the three carrier sources into one canonical outreach-ready dataset after each source has been collected.

This feature is the merge layer above:
- Source 1: internal Turvo carrier recommendation
- Source 2: DAT pasted-text import
- Source 3: FreightX carrier relevancy model

The output is a single deduplicated dataset that can be used later for outreach.

## Scope
- In scope:
  - Read carrier rows from all three source pipelines.
  - Normalize each source into one shared carrier schema.
  - Deduplicate carriers by MC number and carrier name.
  - Preserve source provenance in the canonical `source` field.
  - Produce an outreach-ready dataset without actually sending outreach.
- Out of scope:
  - Sending email, SMS, or WhatsApp outreach.
  - Reply tracking or negotiation state.
  - Re-ranking the merged rows with a new scoring model.
  - Replacing source-specific datasets.

## Problem Statement
Today, each source stores its own carrier records separately.
That is useful for ingestion, but outreach needs one clean list of unique carriers.

We need a consolidation step that:
- merges the three sources,
- keeps the important contact fields,
- makes the origin of each row visible,
- and removes duplicates before outreach starts.

## Target Output Schema
Each canonical outreach row should include:
- `carrier_name`
- `phone`
- `email`
- `mc_number`
- `source`

Recommended supporting fields:
- `lane_id`
- `source_row_ids`
- `source_count`
- `dedupe_key`
- `created_at`
- `updated_at`

## Field Rules
### `carrier_name`
- Use the normalized carrier name from the source row.
- Trim leading and trailing whitespace.
- Preserve the original carrier name casing unless a source already normalizes it.

### `phone`
- Keep the best available phone number for the canonical row.
- If multiple sources have phone values, keep the first non-empty value based on source precedence.

### `email`
- Keep the best available email address for the canonical row.
- If multiple sources have email values, keep the first non-empty value based on source precedence.

### `mc_number`
- Keep the MC number when it is available.
- If one source has an MC number and others do not, use the populated value.

### `source`
- Store the provenance or model label for the surviving canonical row.
- Allowed examples:
  - `DAT`
  - `internal`
  - `1_2`
  - `1_4`
- If a row is merged from multiple sources, choose the best surviving provenance label for that row.
- If full lineage needs to be preserved later, store it in a separate audit table or payload field, not in the canonical outreach row.

## Deduplication Rules
Use both MC number and carrier name to remove duplicate carriers.

Recommended dedupe logic:
1. Normalize carrier names by trimming and case-folding.
2. Normalize MC numbers by trimming and stripping any `MC` prefix.
3. If two rows share the same MC number, treat them as the same carrier.
4. If MC number is missing, treat exact normalized carrier-name matches as the same carrier.
5. If a row has both a carrier name match and an MC match, collapse it into the same canonical row.
6. Keep the first surviving row based on source precedence and ingestion order.

## Suggested Source Precedence
When two sources provide the same carrier, use this precedence to choose the canonical contact details:
1. `internal`
2. `freightx`
3. `dat`

Reasoning:
- Internal Turvo data is usually the most directly usable for outreach.
- FreightX can add breadth and ranking context.
- DAT is useful as a fallback and enrichment source.

Recommended canonical `source` values:
- Use `internal` for internal Turvo rows.
- Use `DAT` for DAT rows.
- Use the FreightX model label output, such as `1_2` or `1_4`, for model-derived rows when available.

## Aggregation Flow
1. Source 1, Source 2, and Source 3 each finish their own ingestion run.
2. The aggregator loads the latest carrier rows from each source for the lane.
3. Each row is normalized into the shared outreach schema.
4. Rows are grouped by MC number first, then carrier name.
5. Duplicate groups are collapsed into one canonical row.
6. Source provenance is preserved in `source`.
7. The final merged dataset is saved as the outreach-ready carrier list for that lane.

## Data Model
Recommended storage shape:

### `carrier_outreach_sets`
- `id`
- `lane_id`
- `status` (`building | ready | failed`)
- `source_count`
- `row_count`
- `dedupe_count`
- `created_at`
- `updated_at`

### `carrier_outreach_rows`
- `id`
- `outreach_set_id`
- `lane_id`
- `carrier_name`
- `phone`
- `email`
- `mc_number`
- `source`
- `source_row_ids`
- `dedupe_key`
- `created_at`

Optional audit tables if needed later:
- `carrier_outreach_row_sources`
- `carrier_outreach_build_events`

## API Contract
Recommended endpoint:
- `POST /portal/lanes/{lane_id}/carrier-outreach-sets`

Request example:
```json
{
  "include_internal": true,
  "include_dat": true,
  "include_freightx": true
}
```

Response example:
```json
{
  "lane_id": "bca6b2b2-0b3a-4d3b-8e1f-73c2e2d7a9f0",
  "status": "ready",
  "source_count": 3,
  "row_count": 42,
  "dedupe_count": 18
}
```

## Processing Rules
- Reject aggregation if the lane does not exist.
- Skip a source cleanly if that source has no rows for the lane.
- Do not mutate the source-specific tables while aggregating.
- Preserve raw source row IDs so the canonical row can be traced back.
- Make the merge deterministic for the same input set.
- If the merge fails, leave source data intact and return a safe failure state.

## Observability
- Log `request_id`, `lane_id`, `source_count`, `row_count`, `dedupe_count`, and `status`.
- Log source coverage counts separately for internal, DAT, and FreightX.
- Include enough lineage to answer which source mix generated a given outreach row.

## Acceptance Criteria
1. The system can combine Source 1, Source 2, and Source 3 into one outreach-ready dataset.
2. Each canonical row includes `carrier_name`, `phone`, `email`, `mc_number`, and `source`.
3. Duplicate carriers are removed by MC number and carrier name.
4. Source-specific datasets remain unchanged after aggregation.
5. The canonical row keeps a visible source or model label in `source` for later analysis.
6. The dataset can be built before outreach starts, without sending any messages.
7. The merge is deterministic and safe to rerun.

## Notes for Future Work
- This feature is the bridge between carrier ingestion and outreach execution.
- Later work can add scoring, channel selection, and campaign batching on top of the merged dataset.
- Keep the aggregator thin so it can evolve without changing the source adapters.
