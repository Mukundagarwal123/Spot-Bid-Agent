"""Integration tests for /portal/* endpoints using an in-memory SQLite DB."""

from __future__ import annotations

import uuid

import pytest

# ---------------------------------------------------------------------------
# Test payloads
# ---------------------------------------------------------------------------

_VALID = {
    "origin_city": "Chicago",
    "origin_state": "IL",
    "destination_city": "Dallas",
    "destination_state": "TX",
    "equipment_type": "dry_van",
    "stops": [],
}


# ---------------------------------------------------------------------------
# POST /portal/lanes
# ---------------------------------------------------------------------------


def test_create_lane_returns_201(client) -> None:
    r = client.post("/portal/lanes", json=_VALID)
    assert r.status_code == 201


def test_create_lane_response_shape(client) -> None:
    r = client.post("/portal/lanes", json=_VALID)
    data = r.json()
    assert data["label"] == "Chicago, IL → Dallas, TX"
    assert data["status"] == "new"
    uuid.UUID(data["lane_id"])  # raises if invalid UUID


def test_create_lane_missing_origin_city_422(client) -> None:
    payload = {k: v for k, v in _VALID.items() if k != "origin_city"}
    assert client.post("/portal/lanes", json=payload).status_code == 422


def test_create_lane_missing_destination_state_422(client) -> None:
    payload = {k: v for k, v in _VALID.items() if k != "destination_state"}
    assert client.post("/portal/lanes", json=payload).status_code == 422


def test_create_lane_invalid_equipment_422(client) -> None:
    assert (
        client.post("/portal/lanes", json={**_VALID, "equipment_type": "spaceship"}).status_code
        == 422
    )


def test_create_lane_invalid_zip_422(client) -> None:
    assert (
        client.post("/portal/lanes", json={**_VALID, "origin_zip": "ABCDE"}).status_code == 422
    )


def test_create_lane_with_stops(client) -> None:
    payload = {
        **_VALID,
        "stops": [
            {"city": "Memphis", "state": "TN"},
            {"city": "Little Rock", "state": "AR", "zip": "72201"},
        ],
    }
    assert client.post("/portal/lanes", json=payload).status_code == 201


def test_create_lane_with_pickup_date(client) -> None:
    assert (
        client.post("/portal/lanes", json={**_VALID, "pickup_date": "2025-08-01"}).status_code
        == 201
    )


def test_create_lane_all_equipment_types(client) -> None:
    for eq in ("dry_van", "reefer", "flatbed", "power_only", "other"):
        r = client.post("/portal/lanes", json={**_VALID, "equipment_type": eq})
        assert r.status_code == 201, f"Failed for equipment_type={eq}"


# ---------------------------------------------------------------------------
# GET /portal/lanes
# ---------------------------------------------------------------------------


def test_list_lanes_empty(client) -> None:
    r = client.get("/portal/lanes")
    assert r.status_code == 200
    assert r.json()["lanes"] == []


def test_list_lanes_after_create(client) -> None:
    client.post("/portal/lanes", json=_VALID)
    r = client.get("/portal/lanes")
    assert len(r.json()["lanes"]) == 1


def test_list_lanes_includes_metrics_preview(client) -> None:
    client.post("/portal/lanes", json=_VALID)
    lane = client.get("/portal/lanes").json()["lanes"][0]
    assert "metrics_preview" in lane
    assert lane["metrics_preview"]["carriers_contacted"] >= 15


def test_list_lanes_no_dedup(client) -> None:
    client.post("/portal/lanes", json=_VALID)
    client.post("/portal/lanes", json=_VALID)
    assert len(client.get("/portal/lanes").json()["lanes"]) == 2


# ---------------------------------------------------------------------------
# GET /portal/lanes/{lane_id}
# ---------------------------------------------------------------------------


def test_get_lane_detail_200(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    r = client.get(f"/portal/lanes/{lane_id}")
    assert r.status_code == 200


def test_get_lane_detail_label(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    data = client.get(f"/portal/lanes/{lane_id}").json()
    assert data["lane"]["label"] == "Chicago, IL → Dallas, TX"


def test_get_lane_detail_metrics_nonzero(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    m = client.get(f"/portal/lanes/{lane_id}").json()["metrics"]
    assert m["carriers_contacted"] >= 15
    assert m["emails_sent"] >= 1


def test_get_lane_detail_timeline_4_events(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    tl = client.get(f"/portal/lanes/{lane_id}").json()["timeline"]
    assert len(tl) == 4


def test_get_lane_detail_stops_included(client) -> None:
    payload = {**_VALID, "stops": [{"city": "Memphis", "state": "TN"}]}
    lane_id = client.post("/portal/lanes", json=payload).json()["lane_id"]
    stops = client.get(f"/portal/lanes/{lane_id}").json()["stops"]
    assert len(stops) == 1
    assert stops[0]["city"] == "Memphis"


def test_get_lane_detail_not_found(client) -> None:
    r = client.get("/portal/lanes/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_get_lane_detail_metrics_deterministic(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    url = f"/portal/lanes/{lane_id}"
    assert client.get(url).json()["metrics"] == client.get(url).json()["metrics"]


# ---------------------------------------------------------------------------
# GET /portal/lanes/{lane_id}/carrier-crm
# ---------------------------------------------------------------------------


def test_carrier_crm_200(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    r = client.get(f"/portal/lanes/{lane_id}/carrier-crm")
    assert r.status_code == 200


def test_carrier_crm_count_range(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    carriers = client.get(f"/portal/lanes/{lane_id}/carrier-crm").json()["carriers"]
    assert 10 <= len(carriers) <= 30


def test_carrier_crm_fields_present(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    carrier = client.get(f"/portal/lanes/{lane_id}/carrier-crm").json()["carriers"][0]
    for field in (
        "carrier_name",
        "times_contacted",
        "times_responded",
        "avg_response_time_minutes",
        "preferred_channel",
        "response_rate",
        "last_contacted_at",
    ):
        assert field in carrier, f"Missing field: {field}"


def test_carrier_crm_deterministic(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    url = f"/portal/lanes/{lane_id}/carrier-crm"
    assert client.get(url).json() == client.get(url).json()


def test_carrier_crm_not_found(client) -> None:
    r = client.get("/portal/lanes/00000000-0000-0000-0000-000000000000/carrier-crm")
    assert r.status_code == 404


def test_carrier_crm_sorted_by_response_rate_desc(client) -> None:
    lane_id = client.post("/portal/lanes", json=_VALID).json()["lane_id"]
    carriers = client.get(f"/portal/lanes/{lane_id}/carrier-crm").json()["carriers"]
    rates = [c["response_rate"] for c in carriers]
    assert rates == sorted(rates, reverse=True)
