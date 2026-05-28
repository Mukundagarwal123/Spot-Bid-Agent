# Data Model

## Feature 001 — Portal Tables (live, SQLite local / PostgreSQL staging)

> All five tables use a `portal_` prefix to remain isolated from the future
> Turvo-triggered workflow tables below. Column names were intentionally aligned
> with the future `loads` / `carriers` schema to make migration straightforward.

### `portal_lanes`
- `id` UUID PK
- `origin_city`, `origin_state`, `origin_zip`
- `destination_city`, `destination_state`, `destination_zip`
- `equipment_type` TEXT (dry_van | reefer | flatbed | power_only | other)
- `pickup_date` DATE nullable
- `status` TEXT (new | in_progress | closed)
- `created_at`, `updated_at` TIMESTAMP (UTC, timezone-naive)

### `portal_lane_stops`
- `id` UUID PK
- `lane_id` FK → portal_lanes.id CASCADE DELETE
- `stop_order` INT (0-based insertion order)
- `city`, `state`, `zip`

### `portal_lane_metrics_snapshot`
- `id` UUID PK
- `lane_id` UUID FK UNIQUE (one row per lane)
- `emails_sent`, `emails_clicked`, `email_replies`
- `sms_sent`, `sms_replies`
- `whatsapp_sent`, `whatsapp_replies`
- `carriers_contacted`, `carriers_responded`
- `generated_at` TIMESTAMP
- **Generated once on lane creation; never recalculated.**

### `portal_lane_activity_events`
- `id` UUID PK
- `lane_id` UUID FK
- `event_type` TEXT (lane_created | outreach_simulated | engagement_simulated | response_simulated)
- `label` TEXT
- `channel` TEXT nullable
- `event_at` TIMESTAMP
- `sort_order` INT
- **4 rows per lane, deterministically generated.**

### `portal_carrier_crm_snapshot`
- `id` UUID PK
- `lane_id` UUID FK
- `carrier_name` TEXT
- `times_contacted`, `times_responded` INT
- `avg_response_time_minutes` INT
- `preferred_channel` TEXT (email | sms | whatsapp)
- `response_rate` FLOAT (0–100)
- `last_contacted_at` TIMESTAMP
- **10–30 rows per lane, seeded by `int(lane_id_hex[:8], 16)` for determinism.**

### Migration path to live data (Feature 002+)
| portal_lanes column | Future loads column |
|---------------------|---------------------|
| id | loads.id |
| origin_city/state | loads.lane_origin (denormalized or FK to stops) |
| equipment_type | loads.equipment_type |
| status | spotbid_runs.status |

---

## Future Tables (Phase 2+)

## Core Tables (Phases 2–7)

### `loads`
- `id` (pk)
- `external_shipment_id` (unique)
- `lane_origin`
- `lane_destination`
- `equipment_type`
- `created_at`
- `updated_at`

### `spotbid_runs`
- `id` (pk)
- `load_id` (fk -> loads.id)
- `trigger_event_id` (unique)
- `status` (`queued|running|completed|failed`)
- `started_at`
- `ended_at`

### `carriers`
- `id` (pk)
- `mc_number` (nullable unique)
- `dot_number` (nullable)
- `name`
- `source` (`dat|sid_list|internal`)
- `score` (numeric)
- `created_at`

### `carrier_contacts`
- `id` (pk)
- `carrier_id` (fk)
- `email`
- `phone`
- `whatsapp_number`
- `is_primary`

### `outreach_messages`
- `id` (pk)
- `run_id` (fk)
- `carrier_id` (fk)
- `channel` (`email|sms|whatsapp`)
- `provider` (`resend|twilio`)
- `provider_message_id`
- `status` (`sent|delivered|opened|clicked|replied|failed`)
- `sent_at`

### `message_events`
- `id` (pk)
- `outreach_message_id` (fk)
- `event_type`
- `event_at`
- `raw_payload` (jsonb)
- `normalized_payload` (jsonb)

### `negotiation_threads`
- `id` (pk)
- `run_id` (fk)
- `carrier_id` (fk)
- `state` (`contacted|engaged|negotiating|won|lost|no_response`)
- `last_event_at`
- `final_rate` (nullable)

### `load_outcomes`
- `id` (pk)
- `run_id` (fk unique)
- `winning_carrier_id` (fk nullable)
- `agreed_rate` (nullable)
- `closed_at` (nullable)
