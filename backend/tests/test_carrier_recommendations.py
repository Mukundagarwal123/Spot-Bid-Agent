"""Integration and unit tests for Feature 002: internal Turvo carrier recommendation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from app.portal.carriers.source_1_internal_turvo.carrier_contact_store import (
    CarrierContactStore,
    normalize_carrier_key,
)

ENDPOINT = "/portal/carriers/recommendations/internal-turvo"

VALID_BODY = {
    "origin_city": "Dallas",
    "origin_state": "TX",
    "origin_zip": "75001",
    "destination_city": "Phoenix",
    "destination_state": "AZ",
    "destination_zip": "85001",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(client, body, headers=None):
    return client.post(ENDPOINT, json=body, headers=headers or {})


def _empty_store_mock():
    store = MagicMock()
    store.get_many.return_value = {}
    return store


def _turvo_contact(email=None, phone=None, mc_number=None):
    return SimpleNamespace(email=email, phone=phone, mc_number=mc_number)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_missing_origin_zip(client):
    body = {**VALID_BODY, "origin_zip": ""}
    resp = _post(client, body)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "validation_error"
    assert "origin_zip" in data["fields"]


def test_missing_destination_zip(client):
    body = {**VALID_BODY, "destination_zip": ""}
    resp = _post(client, body)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "destination_zip" in data["fields"]


def test_missing_both_zips(client):
    body = {**VALID_BODY, "origin_zip": "", "destination_zip": ""}
    resp = _post(client, body)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "origin_zip" in data["fields"]
    assert "destination_zip" in data["fields"]


def test_blank_zip_treated_as_missing(client):
    body = {**VALID_BODY, "origin_zip": "   "}
    resp = _post(client, body)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "origin_zip" in data["fields"]


def test_missing_origin_city_returns_400(client):
    body = {**VALID_BODY, "origin_city": ""}
    resp = _post(client, body)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@patch("app.portal.carriers.service.get_carrier_contact_store")
@patch("app.portal.carriers.service.query_covered_loads", return_value=["ABC Logistics", "XYZ Freight"])
@patch("app.portal.carriers.service.turvo_client")
def test_valid_request_returns_200(mock_tc, mock_db, mock_store, client):
    mock_store.return_value = _empty_store_mock()
    mock_tc.get_carrier_contact.return_value = _turvo_contact(email="dispatch@abc.com", phone="555-111-2222", mc_number="MC-123")
    resp = _post(client, VALID_BODY)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "carriers" in data
    assert "query" in data
    assert "request_id" in data


@patch("app.portal.carriers.service.get_carrier_contact_store")
@patch("app.portal.carriers.service.query_covered_loads", return_value=["ABC Logistics", "XYZ Freight"])
@patch("app.portal.carriers.service.turvo_client")
def test_carriers_ranked_by_frequency(mock_tc, mock_db, mock_store, client):
    mock_store.return_value = _empty_store_mock()
    mock_tc.get_carrier_contact.return_value = _turvo_contact(email="a@b.com")
    resp = _post(client, VALID_BODY)
    carriers = resp.get_json()["carriers"]
    ranks = [c["match_rank"] for c in carriers]
    assert ranks == [1, 2]
    assert carriers[0]["carrier_name"] == "ABC Logistics"
    assert carriers[1]["carrier_name"] == "XYZ Freight"


@patch("app.portal.carriers.service.get_carrier_contact_store")
@patch("app.portal.carriers.service.query_covered_loads", return_value=["ABC Logistics"])
@patch("app.portal.carriers.service.turvo_client")
def test_email_enrichment_ok(mock_tc, mock_db, mock_store, client):
    mock_store.return_value = _empty_store_mock()
    mock_tc.get_carrier_contact.return_value = _turvo_contact(email="dispatch@abc.com", phone="555-111-2222", mc_number="MC-123")
    resp = _post(client, VALID_BODY)
    carrier = resp.get_json()["carriers"][0]
    assert carrier["status"] == "OK"
    assert carrier["email"] == "dispatch@abc.com"
    assert carrier["source"] == "turvo_internal"


@patch("app.portal.carriers.service.get_carrier_contact_store")
@patch("app.portal.carriers.service.query_covered_loads", return_value=["Unknown Carrier"])
@patch("app.portal.carriers.service.turvo_client")
def test_email_enrichment_not_found(mock_tc, mock_db, mock_store, client):
    mock_store.return_value = _empty_store_mock()
    mock_tc.get_carrier_contact.return_value = _turvo_contact()
    resp = _post(client, VALID_BODY)
    carrier = resp.get_json()["carriers"][0]
    assert carrier["status"] == "NOT_FOUND"
    assert carrier["email"] is None


@patch("app.portal.carriers.service.get_carrier_contact_store")
@patch("app.portal.carriers.service.query_covered_loads", return_value=["Bad Carrier"])
@patch("app.portal.carriers.service.turvo_client")
def test_email_enrichment_error(mock_tc, mock_db, mock_store, client):
    mock_store.return_value = _empty_store_mock()
    mock_tc.get_carrier_contact.side_effect = RuntimeError("connection timeout")
    resp = _post(client, VALID_BODY)
    carrier = resp.get_json()["carriers"][0]
    assert carrier["status"] == "ERROR"
    assert "connection timeout" in carrier["error"]
    assert carrier["email"] is None


@patch("app.portal.carriers.service.get_carrier_contact_store")
@patch("app.portal.carriers.service.query_covered_loads", return_value=["ABC Logistics"])
@patch("app.portal.carriers.service.turvo_client")
def test_request_id_in_response(mock_tc, mock_db, mock_store, client):
    mock_store.return_value = _empty_store_mock()
    mock_tc.get_carrier_contact.return_value = _turvo_contact(email="a@b.com")
    resp = _post(client, VALID_BODY, headers={"X-Request-ID": "test-req-123"})
    assert resp.get_json()["request_id"] == "test-req-123"


@patch("app.portal.carriers.service.get_carrier_contact_store")
@patch("app.portal.carriers.service.query_covered_loads", return_value=[])
@patch("app.portal.carriers.service.turvo_client")
def test_empty_covered_loads_result(mock_tc, mock_db, mock_store, client):
    mock_store.return_value = _empty_store_mock()
    resp = _post(client, VALID_BODY)
    assert resp.status_code == 200
    assert resp.get_json()["carriers"] == []


@patch("app.portal.carriers.service.get_carrier_contact_store")
@patch("app.portal.carriers.service.query_covered_loads", return_value=["Cached Carrier"])
@patch("app.portal.carriers.service.turvo_client")
def test_contact_store_hit_skips_turvo(mock_tc, mock_db, mock_store, client):
    store = _empty_store_mock()
    store.get_many.return_value = {
        normalize_carrier_key("Cached Carrier"): SimpleNamespace(
            carrier_name="Cached Carrier",
            email="cached@carrier.com",
            phone="555-222-3333",
            mc_number="MC-999",
        )
    }
    mock_store.return_value = store

    resp = _post(client, VALID_BODY)

    carrier = resp.get_json()["carriers"][0]
    assert carrier["status"] == "OK"
    assert carrier["email"] == "cached@carrier.com"
    mock_tc.get_carrier_contact.assert_not_called()


def _mock_db_engine(rows):
    """Build a mock SQLAlchemy engine whose `with engine.connect() as conn` yields
    a connection that returns `rows` from `conn.execute(...).fetchall()`."""
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = rows
    conn_cm = MagicMock()
    conn_cm.__enter__.return_value = conn
    engine = MagicMock()
    engine.connect.return_value = conn_cm
    return engine


def test_contact_store_maps_row_and_combines_country_code_with_phone():
    from app.portal.carriers.source_1_internal_turvo import carrier_contact_store as store_mod

    engine = _mock_db_engine([("ABC Logistics", "dispatch@abc.com", "+1", "5551234567", "MC-123")])
    with patch.object(store_mod, "_get_engine", return_value=engine):
        record = CarrierContactStore().get("abc  logistics")

    assert record is not None
    assert record.carrier_name == "ABC Logistics"
    assert record.email == "dispatch@abc.com"
    assert record.phone == "+15551234567"
    assert record.mc_number == "MC-123"


def test_contact_store_get_many_batches_into_one_query():
    from app.portal.carriers.source_1_internal_turvo import carrier_contact_store as store_mod

    engine = _mock_db_engine(
        [
            ("ABC Logistics", "dispatch@abc.com", "+1", "5551234567", "MC-123"),
            ("XYZ Freight", "ops@xyz.com", "+1", "5559876543", "MC-456"),
        ]
    )
    with patch.object(store_mod, "_get_engine", return_value=engine):
        results = CarrierContactStore().get_many(["ABC Logistics", "XYZ Freight", "Unknown Co"])

    conn = engine.connect.return_value.__enter__.return_value
    assert conn.execute.call_count == 1  # one round trip for the whole batch
    assert results[normalize_carrier_key("ABC Logistics")].email == "dispatch@abc.com"
    assert results[normalize_carrier_key("XYZ Freight")].phone == "+15559876543"
    assert normalize_carrier_key("Unknown Co") not in results


def test_contact_store_miss_returns_none():
    from app.portal.carriers.source_1_internal_turvo import carrier_contact_store as store_mod

    engine = _mock_db_engine([])
    with patch.object(store_mod, "_get_engine", return_value=engine):
        assert CarrierContactStore().get("Unknown Carrier") is None


def test_contact_store_no_engine_returns_none():
    from app.portal.carriers.source_1_internal_turvo import carrier_contact_store as store_mod

    with patch.object(store_mod, "_get_engine", return_value=None):
        assert CarrierContactStore().get("Any Carrier") is None


# ---------------------------------------------------------------------------
# turvo_db: no DB config
# ---------------------------------------------------------------------------

def test_turvo_db_url_none_returns_empty():
    from app.portal.carriers.source_1_internal_turvo import db as db_mod

    original_engine = db_mod._engine
    try:
        db_mod._engine = None
        with patch.object(db_mod, "_get_engine", return_value=None):
            result = db_mod.query_covered_loads("Dallas", "TX", "AZ")
        assert result == []
    finally:
        db_mod._engine = original_engine


# ---------------------------------------------------------------------------
# TurvoApiClient unit tests (no Flask needed)
# ---------------------------------------------------------------------------

def _make_client():
    from app.portal.carriers.source_1_internal_turvo.turvo_client import TurvoApiClient
    return TurvoApiClient(
        base_url="https://fake.turvo.com",
        client_id="cid",
        client_secret="csecret",
    )


def _token_response():
    r = MagicMock(spec=httpx.Response)
    r.status_code = 200
    r.json.return_value = {"access_token": "tok123"}
    r.raise_for_status.return_value = None
    return r


def _search_response(email):
    r = MagicMock(spec=httpx.Response)
    r.status_code = 200
    r.json.return_value = {"data": [{"primaryEmail": email}]}
    r.raise_for_status.return_value = None
    return r


def _rate_limit_response(retry_after=None):
    r = MagicMock(spec=httpx.Response)
    r.status_code = 429
    r.headers = {"Retry-After": str(retry_after)} if retry_after else {}
    return r


def _unauthorized_response():
    r = MagicMock(spec=httpx.Response)
    r.status_code = 401
    r.headers = {}
    return r


@patch("app.portal.carriers.source_1_internal_turvo.turvo_client.time.sleep")
def test_turvo_client_429_retry(mock_sleep):
    client = _make_client()
    token_resp = _token_response()
    search_ok = _search_response("ok@carrier.com")

    # First call: 429 with Retry-After=1, second call: 200
    with patch.object(client._http, "post", return_value=token_resp):
        with patch.object(client._http, "get", side_effect=[_rate_limit_response(retry_after=1), search_ok]):
            email = client.get_carrier_email("Test Carrier")

    assert email == "ok@carrier.com"
    # sleep was called at least once for rate limit
    assert any(call.args[0] == 1.0 for call in mock_sleep.call_args_list)


@patch("app.portal.carriers.source_1_internal_turvo.turvo_client.time.sleep")
def test_turvo_client_401_refresh(mock_sleep):
    client = _make_client()
    token_resp = _token_response()
    search_ok = _search_response("fresh@carrier.com")
    unauth = _unauthorized_response()

    with patch.object(client._http, "post", return_value=token_resp):
        # First search: 401, second search (after token refresh): 200
        with patch.object(client._http, "get", side_effect=[unauth, search_ok]):
            email = client.get_carrier_email("Test Carrier")

    assert email == "fresh@carrier.com"
