from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

_MC_PREFIX = re.compile(r"^[Mm][Cc]")


def _strip_mc(value: Any) -> str:
    """Strip leading MC/mc prefix from a DOCKET_NUMBER value."""
    if value is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(value):
            return ""
    except (TypeError, ImportError):
        pass
    s = str(value).strip()
    if not s or s.lower() in ("nan", "<na>", "nat", "none"):
        return ""
    return _MC_PREFIX.sub("", s)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(value):
            return ""
    except (TypeError, ImportError):
        pass
    s = str(value).strip()
    return "" if s.lower() in ("nan", "<na>", "nat", "none") else s


def _row_to_json(row_dict: dict) -> str:
    """Serialize all model columns to JSON, converting NaN/NA to None."""
    clean: dict[str, Any] = {}
    for k, v in row_dict.items():
        if v is None:
            clean[k] = None
            continue
        try:
            import pandas as pd
            if pd.isna(v):
                clean[k] = None
                continue
        except (TypeError, ImportError):
            pass
        clean[k] = v
    return json.dumps(clean, default=str)


def normalize_row(
    row_dict: dict,
    rank: int,
    run_id: uuid.UUID,
    lane_id: uuid.UUID,
    now: datetime,
) -> dict:
    """Convert one raw model row dict into a CarrierRelevancyRecord-ready dict.

    DOT_NUMBER is excluded from normalized fields but preserved in raw_payload_json.
    """
    return {
        "id": uuid.uuid4(),
        "run_id": run_id,
        "lane_id": lane_id,
        "rank": rank,
        "docket_number": _strip_mc(row_dict.get("DOCKET_NUMBER")),
        "legal_name": _safe_str(row_dict.get("LEGAL_NAME")),
        "email_address": _safe_str(row_dict.get("EMAIL_ADDRESS")),
        "phone": _safe_str(row_dict.get("PHONE")),
        "label": _safe_str(row_dict.get("LABEL")),
        "source_type": "freightx_relevancy",
        "raw_payload_json": _row_to_json(row_dict),
        "created_at": now,
    }


def deduplicate(normalized_rows: list[dict]) -> list[dict]:
    """Keep first occurrence per docket_number. Empty docket_numbers are never deduped."""
    seen: set[str] = set()
    out: list[dict] = []
    for row in normalized_rows:
        dk = row["docket_number"]
        if dk == "":
            out.append(row)
            continue
        if dk in seen:
            continue
        seen.add(dk)
        out.append(row)
    return out
