from __future__ import annotations

import csv
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from app.core.settings import settings

_CSV_FIELDS = ["Account name (account/shipment)", "Billing email", "Billing phone number", "MC number"]


@dataclass(frozen=True)
class CarrierContactRecord:
    carrier_name: str
    email: str | None
    phone: str | None
    mc_number: str | None


class CarrierContactStore:
    def __init__(self, csv_path: str | Path) -> None:
        self._csv_path = Path(csv_path)
        self._lock = threading.RLock()
        self._loaded_mtime: float | None = None
        self._records: list[CarrierContactRecord] = []
        self._index: dict[str, int] = {}

    @staticmethod
    def _key(carrier_name: str) -> str:
        return " ".join(carrier_name.strip().casefold().split())

    @staticmethod
    def _clean(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _load_unlocked(self) -> None:
        path = self._csv_path
        current_mtime = path.stat().st_mtime if path.exists() else None
        if self._loaded_mtime == current_mtime:
            return

        self._records = []
        self._index = {}

        if not path.exists():
            self._loaded_mtime = None
            return

        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                carrier_name = self._clean(
                    row.get("Account name (account/shipment)")
                    or row.get("carrier_name")
                    or row.get("Carrier Name")
                )
                if not carrier_name:
                    continue
                record = CarrierContactRecord(
                    carrier_name=carrier_name,
                    email=self._clean(row.get("Billing email") or row.get("email")),
                    phone=self._clean(row.get("Billing phone number") or row.get("phone")),
                    mc_number=self._clean(row.get("MC number") or row.get("mc_number") or row.get("MC Number")),
                )
                self._index[self._key(record.carrier_name)] = len(self._records)
                self._records.append(record)

        self._loaded_mtime = current_mtime

    def get(self, carrier_name: str) -> CarrierContactRecord | None:
        with self._lock:
            self._load_unlocked()
            record_index = self._index.get(self._key(carrier_name))
            if record_index is None:
                return None
            return self._records[record_index]

    def upsert(self, record: CarrierContactRecord) -> None:
        with self._lock:
            self._load_unlocked()
            key = self._key(record.carrier_name)
            existing_index = self._index.get(key)
            if existing_index is None:
                self._index[key] = len(self._records)
                self._records.append(record)
            else:
                self._records[existing_index] = record
            self._write_unlocked()

    def _write_unlocked(self) -> None:
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8",
            dir=str(self._csv_path.parent),
            prefix=f"{self._csv_path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            for record in self._records:
                writer.writerow(
                    {
                        "Account name (account/shipment)": record.carrier_name,
                        "Billing email": record.email or "",
                        "Billing phone number": record.phone or "",
                        "MC number": record.mc_number or "",
                    }
                )
            temp_path = Path(handle.name)

        temp_path.replace(self._csv_path)
        self._loaded_mtime = self._csv_path.stat().st_mtime


_store: CarrierContactStore | None = None


def get_carrier_contact_store() -> CarrierContactStore:
    global _store
    if _store is None:
        _store = CarrierContactStore(settings.carrier_data_csv_path)
    return _store
