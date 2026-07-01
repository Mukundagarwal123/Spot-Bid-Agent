from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import bindparam, text

from app.core.settings import settings
from app.portal.carriers.source_1_internal_turvo.db import _get_engine

_TABLE = settings.carriers_table


def normalize_carrier_key(name: str) -> str:
    """Case-insensitive, whitespace-collapsed key used to match free-text carrier names."""
    return " ".join(name.strip().casefold().split())


# Matches on normalized carrier name since route_complete_shipments.carrier_name and
# carriers.name are free-text, not joined by id. `keys` is an expanding IN-list so a
# whole lane's worth of carriers can be resolved in a single round trip.
_SQL_MANY = text(
    f"""
    SELECT name, email, country_code, phone, mc
    FROM public.{_TABLE}
    WHERE lower(regexp_replace(btrim(name), '\\s+', ' ', 'g')) IN :keys
    """
).bindparams(bindparam("keys", expanding=True))


@dataclass(frozen=True)
class CarrierContactRecord:
    carrier_name: str
    email: str | None
    phone: str | None
    mc_number: str | None


class CarrierContactStore:
    """Read-only lookup against the `carriers` table (Feature 002 contact source)."""

    def get(self, carrier_name: str) -> CarrierContactRecord | None:
        return self.get_many([carrier_name]).get(normalize_carrier_key(carrier_name))

    def get_many(self, carrier_names: list[str]) -> dict[str, CarrierContactRecord]:
        """Resolve many carrier names in a single query, keyed by normalize_carrier_key()."""
        engine = _get_engine()
        if engine is None or not carrier_names:
            return {}
        keys = list({normalize_carrier_key(n) for n in carrier_names})
        with engine.connect() as conn:
            rows = conn.execute(_SQL_MANY, {"keys": keys}).fetchall()
        result: dict[str, CarrierContactRecord] = {}
        for name, email, country_code, phone, mc in rows:
            full_phone = f"{country_code}{phone}" if country_code and phone else phone
            result[normalize_carrier_key(name)] = CarrierContactRecord(
                carrier_name=name,
                email=email,
                phone=full_phone,
                mc_number=mc,
            )
        return result


_store: CarrierContactStore | None = None


def get_carrier_contact_store() -> CarrierContactStore:
    global _store
    if _store is None:
        _store = CarrierContactStore()
    return _store
