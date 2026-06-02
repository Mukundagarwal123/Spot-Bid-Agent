"""Integration tests for /portal/* endpoints using Flask test client."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

_VALID = {
    "origin_city": "Chicago",
    "origin_state": "IL",
    "origin_zip": "60601",
    "destination_city": "Dallas",
    "destination_state": "TX",
    "destination_zip": "75201",
    "equipment_type": "dry_van",
    "stops": [],
}


def _json(response):
    return response.get_json()


def test_portal_page_renders(client) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert b"Spot Bid Portal" in r.data
    assert b"Active Lanes" in r.data
    assert b"Completed" in r.data
    assert b"Carrier CRM" in r.data


def test_portal_alias_renders(client) -> None:
    r = client.get("/portal")
    assert r.status_code == 200
    assert b"Spot Bid Portal" in r.data


def test_create_lane_returns_201(client) -> None:
    r = client.post("/portal/lanes", json=_VALID)
    assert r.status_code == 201


@patch("app.portal.api.get_internal_turvo_recommendations")
def test_create_lane_triggers_source1(mock_source1, client) -> None:
    mock_source1.return_value = SimpleNamespace(carriers=[1, 2, 3])
    r = client.post("/portal/lanes", json=_VALID)
    assert r.status_code == 201
    assert mock_source1.called


def test_create_lane_response_shape(client) -> None:
    r = client.post("/portal/lanes", json=_VALID)
    data = _json(r)
    assert data["label"] == "Chicago, IL -> Dallas, TX"
    assert data["status"] == "new"
    uuid.UUID(data["lane_id"])


def test_create_lane_missing_origin_city_422(client) -> None:
    payload = {k: v for k, v in _VALID.items() if k != "origin_city"}
    assert client.post("/portal/lanes", json=payload).status_code == 422


def test_create_lane_invalid_equipment_422(client) -> None:
    assert client.post("/portal/lanes", json={**_VALID, "equipment_type": "spaceship"}).status_code == 422


def test_create_lane_missing_origin_zip_422(client) -> None:
    payload = {k: v for k, v in _VALID.items() if k != "origin_zip"}
    assert client.post("/portal/lanes", json=payload).status_code == 422


def test_create_lane_missing_destination_zip_422(client) -> None:
    payload = {k: v for k, v in _VALID.items() if k != "destination_zip"}
    assert client.post("/portal/lanes", json=payload).status_code == 422


def test_create_lane_with_stops(client) -> None:
    payload = {
        **_VALID,
        "stops": [
            {"city": "Memphis", "state": "TN"},
            {"city": "Little Rock", "state": "AR", "zip": "72201"},
        ],
    }
    assert client.post("/portal/lanes", json=payload).status_code == 201


def test_list_lanes_empty(client) -> None:
    r = client.get("/portal/lanes")
    assert r.status_code == 200
    assert _json(r)["lanes"] == []


def test_list_lanes_after_create(client) -> None:
    client.post("/portal/lanes", json=_VALID)
    r = client.get("/portal/lanes")
    assert len(_json(r)["lanes"]) == 1


def test_list_lanes_includes_metrics_preview(client) -> None:
    client.post("/portal/lanes", json=_VALID)
    lane = _json(client.get("/portal/lanes"))["lanes"][0]
    assert "metrics_preview" in lane
    assert lane["metrics_preview"]["carriers_contacted"] >= 15


def test_get_lane_detail_200(client) -> None:
    lane_id = _json(client.post("/portal/lanes", json=_VALID))["lane_id"]
    r = client.get(f"/portal/lanes/{lane_id}")
    assert r.status_code == 200


def test_get_lane_detail_label(client) -> None:
    lane_id = _json(client.post("/portal/lanes", json=_VALID))["lane_id"]
    data = _json(client.get(f"/portal/lanes/{lane_id}"))
    assert data["lane"]["label"] == "Chicago, IL -> Dallas, TX"


def test_get_lane_detail_timeline_4_events(client) -> None:
    lane_id = _json(client.post("/portal/lanes", json=_VALID))["lane_id"]
    tl = _json(client.get(f"/portal/lanes/{lane_id}"))["timeline"]
    assert len(tl) == 4


def test_get_lane_detail_not_found(client) -> None:
    r = client.get("/portal/lanes/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_carrier_crm_200(client) -> None:
    lane_id = _json(client.post("/portal/lanes", json=_VALID))["lane_id"]
    r = client.get(f"/portal/lanes/{lane_id}/carrier-crm")
    assert r.status_code == 200


def test_carrier_crm_sorted_by_response_rate_desc(client) -> None:
    lane_id = _json(client.post("/portal/lanes", json=_VALID))["lane_id"]
    carriers = _json(client.get(f"/portal/lanes/{lane_id}/carrier-crm"))["carriers"]
    rates = [c["response_rate"] for c in carriers]
    assert rates == sorted(rates, reverse=True)


def test_carrier_crm_not_found(client) -> None:
    r = client.get("/portal/lanes/00000000-0000-0000-0000-000000000000/carrier-crm")
    assert r.status_code == 404
