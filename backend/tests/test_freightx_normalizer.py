"""Unit tests for FreightX Source 3 normalizer."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from app.portal.carriers.source_3_freightx.normalizer import (
    deduplicate,
    normalize_row,
    _strip_mc,
)

_NOW = datetime(2026, 6, 1, 12, 0, 0)
_RUN_ID = uuid.uuid4()
_LANE_ID = uuid.uuid4()


def _make_row(**kwargs) -> dict:
    base = {
        "DOCKET_NUMBER": "MC1234567",
        "DOT_NUMBER": "9876543",
        "LEGAL_NAME": "Acme Freight LLC",
        "EMAIL_ADDRESS": "dispatch@acme.com",
        "PHONE": "5551234567",
        "LABEL": "1_4_5",
    }
    base.update(kwargs)
    return base


class TestStripMc:
    def test_strips_uppercase_mc(self):
        assert _strip_mc("MC1234567") == "1234567"

    def test_strips_lowercase_mc(self):
        assert _strip_mc("mc9876543") == "9876543"

    def test_strips_mixed_case_mc(self):
        assert _strip_mc("Mc1234567") == "1234567"

    def test_no_prefix_unchanged(self):
        assert _strip_mc("1234567") == "1234567"

    def test_mc_only_returns_empty(self):
        assert _strip_mc("MC") == ""

    def test_none_returns_empty(self):
        assert _strip_mc(None) == ""

    def test_nan_string_returns_empty(self):
        assert _strip_mc("nan") == ""

    def test_empty_string_returns_empty(self):
        assert _strip_mc("") == ""


class TestNormalizeRow:
    def test_docket_number_mc_stripped(self):
        row = normalize_row(_make_row(DOCKET_NUMBER="MC1234567"), 1, _RUN_ID, _LANE_ID, _NOW)
        assert row["docket_number"] == "1234567"

    def test_dot_number_not_in_normalized_fields(self):
        row = normalize_row(_make_row(DOT_NUMBER="9876543"), 1, _RUN_ID, _LANE_ID, _NOW)
        assert "dot_number" not in row
        assert "DOT_NUMBER" not in row

    def test_dot_number_in_raw_payload(self):
        row = normalize_row(_make_row(DOT_NUMBER="9876543"), 1, _RUN_ID, _LANE_ID, _NOW)
        payload = json.loads(row["raw_payload_json"])
        assert payload["DOT_NUMBER"] == "9876543"

    def test_all_normalized_fields_present(self):
        row = normalize_row(_make_row(), 1, _RUN_ID, _LANE_ID, _NOW)
        for field in ("docket_number", "legal_name", "email_address", "phone", "label", "source_type"):
            assert field in row

    def test_source_type_is_freightx_relevancy(self):
        row = normalize_row(_make_row(), 1, _RUN_ID, _LANE_ID, _NOW)
        assert row["source_type"] == "freightx_relevancy"

    def test_rank_assigned(self):
        row = normalize_row(_make_row(), 5, _RUN_ID, _LANE_ID, _NOW)
        assert row["rank"] == 5

    def test_extra_columns_in_raw_payload(self):
        row = normalize_row(_make_row(EXTRA_COL="extra_value"), 1, _RUN_ID, _LANE_ID, _NOW)
        payload = json.loads(row["raw_payload_json"])
        assert payload["EXTRA_COL"] == "extra_value"

    def test_none_fields_become_empty_string(self):
        row = normalize_row(_make_row(LEGAL_NAME=None), 1, _RUN_ID, _LANE_ID, _NOW)
        assert row["legal_name"] == ""

    def test_nan_docket_becomes_empty_string(self):
        row = normalize_row(_make_row(DOCKET_NUMBER=float("nan")), 1, _RUN_ID, _LANE_ID, _NOW)
        assert row["docket_number"] == ""


class TestDeduplicate:
    def _rows(self, dockets: list[str]) -> list[dict]:
        return [
            normalize_row(_make_row(DOCKET_NUMBER=d), i + 1, _RUN_ID, _LANE_ID, _NOW)
            for i, d in enumerate(dockets)
        ]

    def test_unique_rows_unchanged(self):
        rows = self._rows(["MC100", "MC200", "MC300"])
        result = deduplicate(rows)
        assert len(result) == 3

    def test_duplicate_docket_keeps_first(self):
        rows = self._rows(["MC100", "MC100", "MC200"])
        result = deduplicate(rows)
        assert len(result) == 2
        assert result[0]["docket_number"] == "100"

    def test_empty_docket_numbers_not_deduped(self):
        rows = self._rows(["", "", "MC100"])
        result = deduplicate(rows)
        assert len(result) == 3

    def test_order_preserved(self):
        rows = self._rows(["MC300", "MC100", "MC200"])
        result = deduplicate(rows)
        assert [r["docket_number"] for r in result] == ["300", "100", "200"]
