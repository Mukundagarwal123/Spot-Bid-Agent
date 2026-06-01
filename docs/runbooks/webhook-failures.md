# Runbook - Webhook Failures

## Symptoms
- Turvo/Resend/Twilio webhooks returning 4xx/5xx.
- Missing load events in dashboard.

## Checks
1. Confirm endpoint health (`/health`).
2. Inspect logs by `correlation_id` and provider event ID.
3. Validate webhook secret configuration.
4. Check clock skew for signature verification logic.
5. Confirm queue backlog and worker status.

## Immediate Actions
1. If 5xx spike: scale API/worker or reduce downstream pressure.
2. If signature failures spike: rotate secret and re-validate signing code.
3. If queue backlog grows: increase worker concurrency.

## Recovery
1. Replay failed webhook payloads from provider console.
2. Reconcile missing events from provider APIs.
3. Mark impacted runs and re-run outreach only where needed.

## Postmortem Data
- Incident timeline.
- Number of impacted loads.
- Lost/late events count.
- Permanent fix and owner.
