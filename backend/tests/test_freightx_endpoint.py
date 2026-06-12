"""Integration tests for FreightX Source 3 endpoints.

The FreightX adapter is monkeypatched so tests don't need precomputed parquet files.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from app.db.models import CarrierRelevancyRecord, CarrierRelevancyRun


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


_SAMPLE_ROWS = [
    {"DOCKET_NUMBER": "MC1111111", "DOT_NUMBER": "111", "LEGAL_NAME": "Alpha Freight", "EMAIL_ADDRESS": "a@alpha.com", "PHONE": "5550001111", "LABEL": "1_4"},
    {"DOCKET_NUMBER": "MC2222222", "DOT_NUMBER": "222", "LEGAL_NAME": "Beta Logistics", "EMAIL_ADDRESS": "b@beta.com", "PHONE": "5550002222", "LABEL": "2_5"},
    {"DOCKET_NUMBER": "MC3333333", "DOT_NUMBER": "333", "LEGAL_NAME": "Gamma Haul", "EMAIL_ADDRESS": "g@gamma.com", "PHONE": "5550003333", "LABEL": "1"},
]


def _create_lane(client):
    # Suppress the auto-triggered background FreightX run so it doesn't
    # race with the test's StaticPool SQLite connection.
    with patch("app.portal.api._bg_run_freightx_relevancy"):
        resp = client.post(
            "/portal/lanes",
            json={
                "origin_city": "Dallas", "origin_state": "TX", "origin_zip": "75001",
                "destination_city": "Phoenix", "destination_state": "AZ", "destination_zip": "85001",
                "equipment_type": "dry_van",
            },
        )
    assert resp.status_code == 201
    return resp.get_json()["lane_id"]


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestFreightXValidation:
    def test_missing_origin_zip(self, client):
        lane_id = _create_lane(client)
        resp = client.post(
            f"/portal/lanes/{lane_id}/freightx-relevancy",
            json={"destination_zip": "85001", "equipment_type": "dryvan"},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "origin_zip" in body["fields"]

    def test_missing_destination_zip(self, client):
        lane_id = _create_lane(client)
        resp = client.post(
            f"/portal/lanes/{lane_id}/freightx-relevancy",
            json={"origin_zip": "75001", "equipment_type": "dryvan"},
        )
        assert resp.status_code == 400
        assert "destination_zip" in resp.get_json()["fields"]

    def test_invalid_equipment_type(self, client):
        lane_id = _create_lane(client)
        resp = client.post(
            f"/portal/lanes/{lane_id}/freightx-relevancy",
            json={"origin_zip": "75001", "destination_zip": "85001", "equipment_type": "power_only"},
        )
        assert resp.status_code == 400
        assert "equipment_type" in resp.get_json()["fields"]

    def test_dry_van_normalized_to_dryvan(self, client):
        lane_id = _create_lane(client)
        with patch(
            "app.portal.carriers.source_3_freightx.service.run_freightx_model",
            return_value=_make_df(_SAMPLE_ROWS),
        ):
            resp = client.post(
                f"/portal/lanes/{lane_id}/freightx-relevancy",
                json={"origin_zip": "75001", "destination_zip": "85001", "equipment_type": "dry_van"},
            )
        assert resp.status_code == 200

    def test_reefer_accepted(self, client):
        lane_id = _create_lane(client)
        with patch(
            "app.portal.carriers.source_3_freightx.service.run_freightx_model",
            return_value=_make_df(_SAMPLE_ROWS),
        ):
            resp = client.post(
                f"/portal/lanes/{lane_id}/freightx-relevancy",
                json={"origin_zip": "75001", "destination_zip": "85001", "equipment_type": "reefer"},
            )
        assert resp.status_code == 200

    def test_lane_not_found(self, client):
        resp = client.post(
            f"/portal/lanes/{uuid.uuid4()}/freightx-relevancy",
            json={"origin_zip": "75001", "destination_zip": "85001", "equipment_type": "dryvan"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Success path tests
# ---------------------------------------------------------------------------

class TestFreightXSuccess:
    def _run(self, client, lane_id, rows=_SAMPLE_ROWS):
        with patch(
            "app.portal.carriers.source_3_freightx.service.run_freightx_model",
            return_value=_make_df(rows),
        ):
            return client.post(
                f"/portal/lanes/{lane_id}/freightx-relevancy",
                json={"origin_zip": "75001", "destination_zip": "85001", "equipment_type": "dryvan"},
            )

    def test_returns_200(self, client):
        lane_id = _create_lane(client)
        resp = self._run(client, lane_id)
        assert resp.status_code == 200

    def test_carrier_count_matches(self, client):
        lane_id = _create_lane(client)
        body = self._run(client, lane_id).get_json()
        assert body["row_count"] == 3
        assert len(body["carriers"]) == 3

    def test_mc_prefix_stripped(self, client):
        lane_id = _create_lane(client)
        body = self._run(client, lane_id).get_json()
        for carrier in body["carriers"]:
            assert not carrier["docket_number"].upper().startswith("MC")

    def test_dot_number_not_in_response(self, client):
        lane_id = _create_lane(client)
        body = self._run(client, lane_id).get_json()
        response_text = json.dumps(body)
        for row in _SAMPLE_ROWS:
            assert row["DOT_NUMBER"] not in response_text or "raw_payload" not in response_text
        for carrier in body["carriers"]:
            assert "dot_number" not in carrier
            assert "DOT_NUMBER" not in carrier

    def test_rank_order(self, client):
        lane_id = _create_lane(client)
        body = self._run(client, lane_id).get_json()
        ranks = [c["rank"] for c in body["carriers"]]
        assert ranks == [1, 2, 3]

    def test_run_id_in_response(self, client):
        lane_id = _create_lane(client)
        body = self._run(client, lane_id).get_json()
        assert body["run_id"]

    def test_source_type_freightx_relevancy(self, client):
        lane_id = _create_lane(client)
        body = self._run(client, lane_id).get_json()
        for carrier in body["carriers"]:
            assert carrier["source_type"] == "freightx_relevancy"


# ---------------------------------------------------------------------------
# No-match and error path tests
# ---------------------------------------------------------------------------

class TestFreightXNoMatches:
    def test_empty_df_returns_no_matches(self, client):
        lane_id = _create_lane(client)
        with patch(
            "app.portal.carriers.source_3_freightx.service.run_freightx_model",
            return_value=pd.DataFrame(),
        ):
            resp = client.post(
                f"/portal/lanes/{lane_id}/freightx-relevancy",
                json={"origin_zip": "75001", "destination_zip": "85001", "equipment_type": "dryvan"},
            )
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["status"] == "NO_MATCHES"
        assert body["row_count"] == 0
        assert body["carriers"] == []


class TestFreightXModelError:
    def test_model_error_returns_500(self, client):
        from app.portal.carriers.source_3_freightx.adapter import FreightXModelError
        lane_id = _create_lane(client)
        with patch(
            "app.portal.carriers.source_3_freightx.service.run_freightx_model",
            side_effect=FreightXModelError("model_execution_failed"),
        ):
            resp = client.post(
                f"/portal/lanes/{lane_id}/freightx-relevancy",
                json={"origin_zip": "75001", "destination_zip": "85001", "equipment_type": "dryvan"},
            )
        assert resp.status_code == 500
        body = resp.get_json()
        assert body["status"] == "freightx_model_failure"


# ---------------------------------------------------------------------------
# GET endpoint and isolation tests
# ---------------------------------------------------------------------------

class TestFreightXGet:
    def test_get_no_runs_returns_no_runs_status(self, client):
        lane_id = _create_lane(client)
        resp = client.get(f"/portal/lanes/{lane_id}/freightx-relevancy")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "NO_RUNS"

    def test_get_returns_stored_results(self, client):
        lane_id = _create_lane(client)
        with patch(
            "app.portal.carriers.source_3_freightx.service.run_freightx_model",
            return_value=_make_df(_SAMPLE_ROWS),
        ):
            client.post(
                f"/portal/lanes/{lane_id}/freightx-relevancy",
                json={"origin_zip": "75001", "destination_zip": "85001", "equipment_type": "dryvan"},
            )
        resp = client.get(f"/portal/lanes/{lane_id}/freightx-relevancy")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["row_count"] == 3
        assert len(body["carriers"]) == 3

    def test_get_lane_not_found(self, client):
        resp = client.get(f"/portal/lanes/{uuid.uuid4()}/freightx-relevancy")
        assert resp.status_code == 404

    def test_source_3_isolated_from_carrier_records(self, client):
        """Source 3 records must not appear in the portal_lane_carrier_records GET endpoint."""
        lane_id = _create_lane(client)
        with patch(
            "app.portal.carriers.source_3_freightx.service.run_freightx_model",
            return_value=_make_df(_SAMPLE_ROWS),
        ):
            client.post(
                f"/portal/lanes/{lane_id}/freightx-relevancy",
                json={"origin_zip": "75001", "destination_zip": "85001", "equipment_type": "dryvan"},
            )
        resp = client.get(f"/portal/lanes/{lane_id}/carrier-records")
        assert resp.status_code == 200
        body = resp.get_json()
        sources = body.get("sources", {})
        assert "freightx_relevancy" not in sources
