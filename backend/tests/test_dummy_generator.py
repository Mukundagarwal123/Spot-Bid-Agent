"""Unit tests for the deterministic dummy data generator."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from app.portal.dummy_generator import (
    CARRIER_POOL,
    _seed_from_lane_id,
    generate_carrier_crm,
    generate_metrics,
    generate_timeline,
)

_NOW = datetime(2025, 6, 1, 12, 0, 0)


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


def test_seed_known_uuid() -> None:
    lane_id = uuid.UUID("12345678-aaaa-bbbb-cccc-000000000000")
    assert _seed_from_lane_id(lane_id) == int("12345678", 16)


def test_seed_deterministic() -> None:
    lane_id = uuid.uuid4()
    assert _seed_from_lane_id(lane_id) == _seed_from_lane_id(lane_id)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_metrics_deterministic() -> None:
    lane_id = uuid.uuid4()
    assert generate_metrics(lane_id) == generate_metrics(lane_id)


def test_metrics_varies_across_lanes() -> None:
    m1 = generate_metrics(uuid.uuid4())
    m2 = generate_metrics(uuid.uuid4())
    assert m1 != m2


def test_metrics_carriers_contacted_range() -> None:
    for _ in range(20):
        m = generate_metrics(uuid.uuid4())
        assert 15 <= m["carriers_contacted"] <= 30


def test_metrics_responded_lte_contacted() -> None:
    for _ in range(20):
        m = generate_metrics(uuid.uuid4())
        assert m["carriers_responded"] <= m["carriers_contacted"]


def test_metrics_channel_counts_lte_contacted() -> None:
    for _ in range(20):
        m = generate_metrics(uuid.uuid4())
        assert m["emails_sent"] <= m["carriers_contacted"]
        assert m["emails_clicked"] <= m["emails_sent"]
        assert m["email_replies"] <= m["emails_clicked"]
        assert m["sms_sent"] <= m["carriers_contacted"]
        assert m["sms_replies"] <= m["sms_sent"]
        assert m["whatsapp_sent"] <= m["carriers_contacted"]
        assert m["whatsapp_replies"] <= m["whatsapp_sent"]


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


def test_timeline_always_4_events() -> None:
    assert len(generate_timeline(uuid.uuid4(), _NOW)) == 4


def test_timeline_deterministic() -> None:
    lane_id = uuid.uuid4()
    assert generate_timeline(lane_id, _NOW) == generate_timeline(lane_id, _NOW)


def test_timeline_ascending_order() -> None:
    events = generate_timeline(uuid.uuid4(), _NOW)
    timestamps = [e["event_at"] for e in events]
    assert timestamps == sorted(timestamps)


def test_timeline_first_event_at_creation_time() -> None:
    events = generate_timeline(uuid.uuid4(), _NOW)
    assert events[0]["event_at"] == _NOW


def test_timeline_event_types() -> None:
    events = generate_timeline(uuid.uuid4(), _NOW)
    types = [e["event_type"] for e in events]
    assert types == [
        "lane_created",
        "outreach_simulated",
        "engagement_simulated",
        "response_simulated",
    ]


# ---------------------------------------------------------------------------
# Carrier CRM
# ---------------------------------------------------------------------------


def test_crm_deterministic() -> None:
    lane_id = uuid.uuid4()
    assert generate_carrier_crm(lane_id, _NOW) == generate_carrier_crm(lane_id, _NOW)


def test_crm_count_range() -> None:
    for _ in range(20):
        carriers = generate_carrier_crm(uuid.uuid4(), _NOW)
        assert 10 <= len(carriers) <= 30


def test_crm_unique_names() -> None:
    carriers = generate_carrier_crm(uuid.uuid4(), _NOW)
    names = [c["carrier_name"] for c in carriers]
    assert len(names) == len(set(names))


def test_crm_names_from_pool() -> None:
    carriers = generate_carrier_crm(uuid.uuid4(), _NOW)
    for c in carriers:
        assert c["carrier_name"] in CARRIER_POOL


def test_crm_response_rate_bounds() -> None:
    for _ in range(10):
        carriers = generate_carrier_crm(uuid.uuid4(), _NOW)
        for c in carriers:
            assert 0.0 <= c["response_rate"] <= 100.0


def test_crm_responded_lte_contacted() -> None:
    for _ in range(10):
        carriers = generate_carrier_crm(uuid.uuid4(), _NOW)
        for c in carriers:
            assert c["times_responded"] <= c["times_contacted"]


def test_crm_channel_valid() -> None:
    carriers = generate_carrier_crm(uuid.uuid4(), _NOW)
    for c in carriers:
        assert c["preferred_channel"] in ("email", "sms", "whatsapp")


def test_carrier_pool_has_60() -> None:
    assert len(CARRIER_POOL) == 60
    assert len(set(CARRIER_POOL)) == 60  # no duplicates
