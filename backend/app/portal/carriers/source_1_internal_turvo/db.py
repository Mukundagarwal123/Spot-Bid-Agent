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


_SQL = text(
    """
    SELECT carrier
    FROM public.covered_loads
    WHERE lower(coalesce(origin_city, '')) = lower(:origin_city)
      AND lower(coalesce(origin_state, '')) = lower(:origin_state)
      AND lower(coalesce(destination_state, '')) = lower(:destination_state)
      AND carrier IS NOT NULL
      AND btrim(carrier) <> ''
    GROUP BY carrier
    ORDER BY count(*) DESC, max(covered_date) DESC;
    """
)


def query_covered_loads(
    origin_city: str,
    origin_state: str,
    destination_state: str,
) -> list[str]:
    if settings.turvo_mock_carriers:
        return _MOCK_CARRIERS

    engine = _get_engine()
    if engine is None:
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            _SQL,
            {
                "origin_city": origin_city,
                "origin_state": origin_state,
                "destination_state": destination_state,
            },
        ).fetchall()
    return [row[0] for row in rows]
