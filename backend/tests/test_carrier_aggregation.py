"""
Tests for Feature 005: multi-source carrier aggregation.

Unit tests cover pure deduplication logic.
Integration tests use the in-memory SQLite client fixture from conftest.py.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime

import pytest

from app.portal.carriers.aggregation.deduplicator import deduplicate, _make_dedupe_key
from app.portal.carriers.aggregation.schemas import AggregatedCarrier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(carrier_name="ACME Freight", phone="", email="", mc_number="",
         source="internal", source_row_id=None) -> AggregatedCarrier:
    return AggregatedCarrier(
        carrier_name=carrier_name,
        phone=phone,
        email=email,
        mc_number=mc_number,
        source=source,
        source_row_id=source_row_id or str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# Unit tests — deduplication logic
# ---------------------------------------------------------------------------

class TestDedupKey:
    def test_mc_number_wins_over_name(self):
        row = _row(carrier_name="acme", mc_number="12345")
        assert _make_dedupe_key(row) == "12345"

    def test_mc_prefix_stripped(self):
        row = _row(carrier_name="acme", mc_number="MC12345")
        assert _make_dedupe_key(row) == "12345"

    def test_mc_prefix_stripped_lowercase(self):
        row = _row(carrier_name="acme", mc_number="mc 67890")
        assert _make_dedupe_key(row) == "67890"

    def test_name_fallback_when_no_mc(self):
        row = _row(carrier_name="  ACME Freight  ", mc_number="")
        assert _make_dedupe_key(row) == "acme freight"


class TestDeduplicate:
    def test_same_mc_collapses_to_one(self):
        rows = [
            _row(carrier_name="ACME", mc_number="111", source="internal"),
            _row(carrier_name="ACME", mc_number="111", source="dat"),
        ]
        result = deduplicate(rows)
        assert len(result) == 1

    def test_same_name_no_mc_collapses(self):
        rows = [
            _row(carrier_name="ACME Freight", mc_number="", source="internal"),
            _row(carrier_name="ACME Freight", mc_number="", source="dat"),
        ]
        result = deduplicate(rows)
        assert len(result) == 1

    def test_distinct_carriers_preserved(self):
        rows = [
            _row(carrier_name="ACME", mc_number="111", source="internal"),
            _row(carrier_name="Blue Hawk", mc_number="222", source="dat"),
        ]
        result = deduplicate(rows)
        assert len(result) == 2

    def test_source_precedence_internal_beats_dat(self):
        rows = [
            _row(carrier_name="ACME", mc_number="111", source="dat", email="dat@x.com"),
            _row(carrier_name="ACME", mc_number="111", source="internal", email="int@x.com"),
        ]
        result = deduplicate(rows)
        assert result[0].source == "internal"
        assert result[0].email == "int@x.com"

    def test_source_precedence_freightx_beats_dat(self):
        rows = [
            _row(carrier_name="ACME", mc_number="111", source="dat", phone="999"),
            _row(carrier_name="ACME", mc_number="111", source="freightx", phone="111"),
        ]
        result = deduplicate(rows)
        assert result[0].source == "freightx"
        assert result[0].phone == "111"

    def test_freightx_label_preserved_as_source(self):
        rows = [
            _row(carrier_name="Speed Haulers", mc_number="777", source="1_4"),
        ]
        result = deduplicate(rows)
        assert result[0].source == "1_4"

    def test_missing_phone_filled_from_lower_source(self):
        rows = [
            _row(carrier_name="ACME", mc_number="111", source="internal", phone=""),
            _row(carrier_name="ACME", mc_number="111", source="dat", phone="555-1234"),
        ]
        result = deduplicate(rows)
        assert result[0].source == "internal"
        assert result[0].phone == "555-1234"

    def test_missing_email_filled_from_lower_source(self):
        rows = [
            _row(carrier_name="ACME", mc_number="111", source="internal", email=""),
            _row(carrier_name="ACME", mc_number="111", source="dat", email="fallback@x.com"),
        ]
        result = deduplicate(rows)
        assert result[0].email == "fallback@x.com"

    def test_all_source_row_ids_tracked(self):
        id1, id2 = str(uuid.uuid4()), str(uuid.uuid4())
        rows = [
            _row(mc_number="111", source="internal", source_row_id=id1),
            _row(mc_number="111", source="dat", source_row_id=id2),
        ]
        result = deduplicate(rows)
        assert id1 in result[0].source_row_ids
        assert id2 in result[0].source_row_ids

    def test_empty_input(self):
        assert deduplicate([]) == []


# ---------------------------------------------------------------------------
# Integration tests — API endpoints
# ---------------------------------------------------------------------------

def _create_lane(client) -> str:
    resp = client.post(
        "/portal/lanes",
        json={
            "origin_city": "Dallas",
            "origin_state": "TX",
            "origin_zip": "75001",
            "destination_city": "Phoenix",
            "destination_state": "AZ",
            "destination_zip": "85001",
            "equipment_type": "dry_van",
        },
    )
    assert resp.status_code == 201
    return resp.get_json()["lane_id"]


def _seed_internal_carrier(db_session, lane_id: str):
    """Insert a minimal internal carrier record directly into the DB."""
    from app.db.models import PortalLaneCarrierRecord, PortalLaneCarrierSource

    source = PortalLaneCarrierSource(
        id=uuid.uuid4(),
        lane_id=uuid.UUID(lane_id),
        source_type="internal",
        parsed_count=1,
        status="ok",
        created_at=datetime.utcnow(),
    )
    db_session.add(source)
    db_session.flush()

    record = PortalLaneCarrierRecord(
        id=uuid.uuid4(),
        lane_id=uuid.UUID(lane_id),
        source_id=source.id,
        source_type="internal",
        carrier_name="Test Carrier Inc",
        email="tc@test.com",
        phone="555-0001",
        mc_number="MC100001",
        source_notes="",
        created_at=datetime.utcnow(),
    )
    db_session.add(record)
    db_session.commit()


def _seed_dat_carrier(db_session, lane_id: str):
    from app.db.models import PortalLaneCarrierRecord, PortalLaneCarrierSource

    source = PortalLaneCarrierSource(
        id=uuid.uuid4(),
        lane_id=uuid.UUID(lane_id),
        source_type="dat",
        parsed_count=1,
        status="ok",
        created_at=datetime.utcnow(),
    )
    db_session.add(source)
    db_session.flush()

    record = PortalLaneCarrierRecord(
        id=uuid.uuid4(),
        lane_id=uuid.UUID(lane_id),
        source_id=source.id,
        source_type="dat",
        carrier_name="DAT Only Carrier",
        email="dat@carrier.com",
        phone="555-0002",
        mc_number="MC200002",
        source_notes="",
        created_at=datetime.utcnow(),
    )
    db_session.add(record)
    db_session.commit()


@pytest.fixture()
def db_session(client, monkeypatch):
    """Expose the test DB session for direct record seeding."""
    from app.db import base as db_base
    session = db_base.SessionLocal()
    yield session
    session.close()


class TestOutreachSetEndpoints:
    def test_post_creates_set_status_ready(self, client, db_session):
        lane_id = _create_lane(client)
        _seed_internal_carrier(db_session, lane_id)

        resp = client.post(f"/portal/lanes/{lane_id}/carrier-outreach-sets", json={})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "ready"
        assert data["row_count"] >= 1
        assert data["lane_id"] == lane_id

    def test_post_unknown_lane_returns_404(self, client):
        unknown = str(uuid.uuid4())
        resp = client.post(f"/portal/lanes/{unknown}/carrier-outreach-sets", json={})
        assert resp.status_code == 404

    def test_post_exclude_dat_omits_dat_carriers(self, client, db_session):
        lane_id = _create_lane(client)
        _seed_internal_carrier(db_session, lane_id)
        _seed_dat_carrier(db_session, lane_id)

        resp = client.post(
            f"/portal/lanes/{lane_id}/carrier-outreach-sets",
            json={"include_dat": False},
        )
        assert resp.status_code == 201
        set_id = resp.get_json()["outreach_set_id"]

        rows_resp = client.get(f"/portal/lanes/{lane_id}/carrier-outreach-sets/{set_id}/rows")
        rows = rows_resp.get_json()["rows"]
        sources = {r["source"] for r in rows}
        assert "DAT" not in sources

    def test_post_idempotent_creates_new_set(self, client, db_session):
        lane_id = _create_lane(client)
        _seed_internal_carrier(db_session, lane_id)

        r1 = client.post(f"/portal/lanes/{lane_id}/carrier-outreach-sets", json={})
        r2 = client.post(f"/portal/lanes/{lane_id}/carrier-outreach-sets", json={})
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.get_json()["outreach_set_id"] != r2.get_json()["outreach_set_id"]

    def test_get_latest_returns_most_recent_set(self, client, db_session):
        lane_id = _create_lane(client)
        _seed_internal_carrier(db_session, lane_id)

        r1 = client.post(f"/portal/lanes/{lane_id}/carrier-outreach-sets", json={})
        time.sleep(0.01)  # ensure distinct created_at timestamps in SQLite
        r2 = client.post(f"/portal/lanes/{lane_id}/carrier-outreach-sets", json={})
        latest_id = r2.get_json()["outreach_set_id"]

        resp = client.get(f"/portal/lanes/{lane_id}/carrier-outreach-sets/latest")
        assert resp.status_code == 200
        assert resp.get_json()["outreach_set_id"] == latest_id

    def test_get_latest_no_sets_returns_404(self, client):
        lane_id = _create_lane(client)
        resp = client.get(f"/portal/lanes/{lane_id}/carrier-outreach-sets/latest")
        assert resp.status_code == 404

    def test_get_rows_returns_required_fields(self, client, db_session):
        lane_id = _create_lane(client)
        _seed_internal_carrier(db_session, lane_id)
        _seed_dat_carrier(db_session, lane_id)

        post_resp = client.post(f"/portal/lanes/{lane_id}/carrier-outreach-sets", json={})
        set_id = post_resp.get_json()["outreach_set_id"]

        rows_resp = client.get(f"/portal/lanes/{lane_id}/carrier-outreach-sets/{set_id}/rows")
        assert rows_resp.status_code == 200
        rows = rows_resp.get_json()["rows"]
        assert len(rows) >= 1
        for row in rows:
            assert "carrier_name" in row
            assert "phone" in row
            assert "email" in row
            assert "mc_number" in row
            assert "source" in row
            assert "dedupe_key" in row
