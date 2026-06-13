from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from app.portal.carriers.aggregation.schemas import AggregatedCarrier

# Source precedence: lower index = higher priority.
_SOURCE_ORDER = ("internal", "freightx", "dat")


def _source_rank(source: str) -> int:
    """Return a sort key for source precedence. Unknown sources sort last."""
    lower = source.lower()
    for i, name in enumerate(_SOURCE_ORDER):
        if lower == name or lower.startswith(name):
            return i
    # FreightX model labels like '1_2' or '1_4' rank alongside freightx
    return 1


def _make_dedupe_key(row: AggregatedCarrier) -> str:
    """
    Primary key: normalized MC number (no MC prefix, uppercased).
    Fallback key: lowercased, trimmed carrier name.
    """
    mc = re.sub(r"^mc\s*", "", row.mc_number.strip(), flags=re.IGNORECASE).strip().upper()
    if mc:
        return mc
    return row.carrier_name.strip().lower()


@dataclass
class _Canonical:
    carrier_name: str
    phone: str
    email: str
    mc_number: str
    source: str
    dedupe_key: str
    source_row_ids: List[str] = field(default_factory=list)


def deduplicate(rows: List[AggregatedCarrier]) -> List[_Canonical]:
    """
    Merge rows by dedupe key.

    Rows are sorted by source precedence first so the highest-priority source
    always wins when a collision is detected.  Missing phone/email on the
    winner are filled from lower-precedence rows that share the same key.
    """
    # Sort by source precedence (stable sort preserves original order within
    # the same source tier)
    sorted_rows = sorted(rows, key=lambda r: _source_rank(r.source))

    seen: Dict[str, _Canonical] = {}
    order: List[str] = []  # preserves insertion order

    for row in sorted_rows:
        key = _make_dedupe_key(row)
        if not key:
            continue

        if key not in seen:
            seen[key] = _Canonical(
                carrier_name=row.carrier_name,
                phone=row.phone,
                email=row.email,
                mc_number=row.mc_number,
                source=row.source,
                dedupe_key=key,
                source_row_ids=[row.source_row_id],
            )
            order.append(key)
        else:
            canonical = seen[key]
            canonical.source_row_ids.append(row.source_row_id)
            # Fill missing contact fields from lower-precedence sources
            if not canonical.phone and row.phone:
                canonical.phone = row.phone
            if not canonical.email and row.email:
                canonical.email = row.email
            # Prefer populated mc_number
            if not canonical.mc_number and row.mc_number:
                canonical.mc_number = row.mc_number

    return [seen[k] for k in order]
