# Spec: Carrier Recommendation from Internal Carrier Network (Turvo)

## Goal
Build the first carrier-ingestion source for lane search.

When a user enters lane details in the frontend, return relevant carriers using internal Turvo-based data logic, then enrich those carriers with contact email data from Turvo.

This spec is only for Source 1 (internal Turvo carrier network). Other sources will be added later.

## Scope
- In scope:
  - Lane-based carrier recommendation.
  - Carrier dedup/ranking.
  - Carrier email enrichment from Turvo.
  - Source-tagged output compatible with future multi-source aggregator.
- Out of scope:
  - Blending with external/secondary carrier sources.
  - Final multi-source scoring.

## Frontend Inputs
- `origin_city` (string, required)
- `origin_state` (string, required)
- `origin_zip` (string, required)
- `destination_city` (string, required)
- `destination_state` (string, required)
- `destination_zip` (string, required)

## Input Validation Rules

- If either zip is missing, return validation error (`400`) with field-level message.
- City/state should be trimmed before matching.
- Empty strings should be treated as missing.

## Proposed Internal API Contract (Phase-Compatible)
Endpoint:
- `POST /portal/carriers/recommendations/internal-turvo`

Request:
```json
{
  "origin_city": "Dallas",
  "origin_state": "TX",
  "origin_zip": "75001",
  "destination_city": "Phoenix",
  "destination_state": "AZ",
  "destination_zip": "85001"
}
```

Validation response example (`400`):
```json
{
  "request_id": "req_123",
  "error": "validation_error",
  "fields": {
    "origin_zip": "origin_zip is required",
    "destination_zip": "destination_zip is required"
  }
}
```

## Data Source for Carrier Recommendation
Use internal covered-loads dataset logic (same pattern as existing covered-load recommendation spec):
- Table: `public.covered_loads`
- Required matching dimensions:
  - origin city
  - origin state
  - destination state
- Matching behavior:
  - Case-insensitive
  - Trim spaces
  - Keep destination state strict
  - Optional fuzzy tolerance for city spelling mistakes (`pg_trgm`) as fallback

## Baseline SQL (Primary Match)
```sql
SELECT carrier
FROM public.covered_loads
WHERE lower(coalesce(origin_city, '')) = lower(%(origin_city)s)
  AND lower(coalesce(origin_state, '')) = lower(%(origin_state)s)
  AND lower(coalesce(destination_state, '')) = lower(%(destination_state)s)
  AND carrier IS NOT NULL
  AND btrim(carrier) <> ''
GROUP BY carrier
ORDER BY count(*) DESC, max(covered_date) DESC;
```

## Carrier Output from Source 1
- Return unique carrier names.
- Rank by:
  1. Higher lane frequency first.
  2. More recent `covered_date` as tie-breaker.

## Turvo Email Enrichment
For each recommended carrier, fetch contact data from Turvo and extract email.

Use the existing Turvo auth/search flow:
1. Token API (`POST /lobby/oauth/token`) to get `access_token`.
2. Carrier search API (`GET /api/search`) with:
   - `q=<carrier name>`
   - `qField=name`
   - `filters={"contextType":{"$in":["carrier"]}}`
3. Parse carrier match and extract:
   - Primary: `primaryEmail`
   - Fallback: `email[]` + `emailPrimary[]` (primary flagged first, else first non-empty)

## Reliability Rules for Turvo Calls
- Handle `429` with retry + exponential backoff.
- Respect `Retry-After` when present.
- On `401`, refresh token and retry once.
- Add short inter-request delay to reduce throttling.

## API Response Shape (Feature Output)
Each carrier entry should include:
- `carrier_name`
- `email`
- `source` = `turvo_internal`
- `match_rank` (1-based rank from lane query)
- `status` (`OK` | `NOT_FOUND` | `ERROR`)
- `error` (nullable)

Example:
```json
{
  "query": {
    "origin_city": "Dallas",
    "origin_state": "TX",
    "origin_zip": "75001",
    "destination_city": "Phoenix",
    "destination_state": "AZ",
    "destination_zip": "85001"
  },
  "carriers": [
    {
      "carrier_name": "ABC Logistics",
      "email": "dispatch@abclogistics.com",
      "source": "turvo_internal",
      "match_rank": 1,
      "status": "OK",
      "error": null
    }
  ]
}
```

## Processing Flow
1. Validate lane input (zips required).
2. Run lane-match query against internal covered-load data.
3. Build ordered unique carrier list.
4. For each carrier, call Turvo search and extract email.
5. Return enriched Source 1 carriers.

## Observability + Safety Requirements
- Include `request_id` in response and logs.
- Log with structured fields: `event`, `correlation_id/request_id`, `service`, `carrier_name`, `source`.
- Do not log Turvo credentials or raw secrets.
- Use env/secrets manager values for Turvo credentials.
- Log the source-1 flow clearly: request received, CSV lookup hits/misses, Turvo fallback, cache write-back, and final matched vs unmatched counts.

## Acceptance Criteria
1. API rejects missing origin/destination zip with clear `400` field errors.
2. For a valid lane request, carriers are returned unique and ranked by frequency/recency from covered loads.
3. Each returned carrier attempts Turvo email enrichment using `primaryEmail` + fallback arrays.
4. Turvo `429` and `401` scenarios are handled per retry rules.
5. Response includes source tag `turvo_internal` for every carrier row.
6. Feature remains isolated as Source 1 and does not mix with other source pipelines.

## Notes for Future Multi-Source Phase
- Keep this feature modular as `source_1_internal_turvo`.
- Future sources can append carriers into a shared aggregation layer.
- Do not mix source-ranking logic in this phase.
- For the current implementation, treat `Carrire Data.csv` as a local carrier-contact cache.
- When a carrier is missing from the cache, enrich from Turvo once and write the new contact back to the cache.
- The CSV-backed store should stay behind a thin abstraction so it can be swapped to RDS/Postgres later without changing the API contract.
