from __future__ import annotations

from sqlalchemy import create_engine, text

from app.core.settings import settings

_engine = None

_MOCK_CARRIERS = [
    "Swift Transportation",
    "Werner Enterprises",
    "JB Hunt Transport",
    "Schneider National",
    "Old Dominion Freight",
    "XPO Logistics",
    "Knight-Swift Holdings",
    "Hub Group",
]


def _get_engine():
    global _engine
    if _engine is None and settings.turvo_db_url:
        _engine = create_engine(settings.turvo_db_url)
    return _engine


_TABLE = settings.route_shipments_table

# pickup_date is stored as TEXT in MM/DD/YYYY format (confirmed against production data),
# so it must be parsed with to_date(..., 'MM/DD/YYYY') for recency ordering to be
# chronological rather than lexicographic.
_SQL = text(
    f"""
    SELECT carrier_name
    FROM public.{_TABLE}
    WHERE lower(coalesce(origin_city, '')) = lower(:origin_city)
      AND lower(coalesce(origin_state, '')) = lower(:origin_state)
      AND lower(coalesce(destination_state, '')) = lower(:destination_state)
      AND carrier_name IS NOT NULL
      AND btrim(carrier_name) <> ''
    GROUP BY carrier_name
    ORDER BY count(*) DESC, max(to_date(nullif(pickup_date, ''), 'MM/DD/YYYY')) DESC;
    """
)

_SQL_STATE_ONLY = text(
    f"""
    SELECT carrier_name
    FROM public.{_TABLE}
    WHERE lower(coalesce(origin_state, '')) = lower(:origin_state)
      AND lower(coalesce(destination_state, '')) = lower(:destination_state)
      AND carrier_name IS NOT NULL
      AND btrim(carrier_name) <> ''
    GROUP BY carrier_name
    ORDER BY count(*) DESC, max(to_date(nullif(pickup_date, ''), 'MM/DD/YYYY')) DESC;
    """
)


def query_covered_loads(
    origin_city: str,
    origin_state: str,
    destination_state: str,
    filter_mode: str = "city_state",
) -> list[str]:
    if settings.turvo_mock_carriers:
        return _MOCK_CARRIERS

    engine = _get_engine()
    if engine is None:
        return []
    with engine.connect() as conn:
        if filter_mode == "state_only":
            rows = conn.execute(
                _SQL_STATE_ONLY,
                {
                    "origin_state": origin_state,
                    "destination_state": destination_state,
                },
            ).fetchall()
        else:
            rows = conn.execute(
                _SQL,
                {
                    "origin_city": origin_city,
                    "origin_state": origin_state,
                    "destination_state": destination_state,
                },
            ).fetchall()
    return [row[0] for row in rows]
