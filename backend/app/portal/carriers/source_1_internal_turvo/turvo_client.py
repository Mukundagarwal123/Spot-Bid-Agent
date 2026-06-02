from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx
import structlog

from app.core.settings import settings

log = structlog.get_logger(__name__)

_MIN_DELAY = 0.25
_MAX_RETRIES = 5
_BASE_BACKOFF = 1.5


@dataclass
class CarrierContact:
    email: str | None
    phone: str | None
    mc_number: str | None


class TurvoApiClient:
    def __init__(
        self,
        token_url: str | None = None,
        search_url: str | None = None,
        client_id: str = "",
        client_secret: str = "",
        username: str = "",
        password: str = "",
        api_key: str = "",
        base_url: str | None = None,
    ) -> None:
        if base_url and not token_url:
            normalized_base_url = base_url.rstrip("/")
            token_url = f"{normalized_base_url}/lobby/oauth/token"
            search_url = search_url or f"{normalized_base_url}/api/search"
        if not token_url or not search_url:
            raise ValueError("token_url and search_url are required")
        self._token_url = token_url
        self._search_url = search_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._username = username
        self._password = password
        self._api_key = api_key
        self._token: str | None = None
        self._http = httpx.Client(timeout=30.0)

    def _fetch_token(self) -> str:
        resp = self._http.post(
            self._token_url,
            headers={"Content-Type": "application/json", "x-api-key": self._api_key},
            json={
                "grant_type": "password",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "username": self._username,
                "password": self._password,
                "scope": "read trust write",
                "type": "business",
            },
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        self._http.headers.update({
            "Authorization": f"Bearer {self._token}",
            "x-api-key": self._api_key,
            "Accept": "application/json",
        })
        log.info("turvo_api.token_refreshed")
        return self._token

    def _get_token(self) -> str:
        if self._token is None:
            return self._fetch_token()
        return self._token

    def _mock_contact(self, carrier_name: str) -> CarrierContact:
        slug = carrier_name.lower().replace(" ", "").replace("-", "")[:12]
        seed = sum(ord(c) for c in carrier_name)
        return CarrierContact(
            email=f"dispatch@{slug}.com",
            phone=f"+1 (555) {100 + seed % 800:03d}-{1000 + seed % 8999:04d}",
            mc_number=f"MC-{100000 + seed % 900000}",
        )

    def get_carrier_contact(self, carrier_name: str) -> CarrierContact:
        if settings.turvo_mock_carriers:
            return self._mock_contact(carrier_name)

        self._get_token()
        time.sleep(_MIN_DELAY)

        filters_params = {
            "q": carrier_name,
            "qField": "name",
            "filters": json.dumps({"contextType": {"$in": ["carrier"]}}, separators=(",", ":")),
        }
        no_filter_params = {"q": carrier_name, "qField": "name"}
        token_refreshed = False

        for attempt in range(_MAX_RETRIES + 1):
            resp = self._http.get(self._search_url, params=filters_params)

            # Turvo intermittently 500s with filters — retry without them
            if resp.status_code >= 500:
                log.info("turvo_api.filter_500_fallback", carrier_name=carrier_name, attempt=attempt)
                resp = self._http.get(self._search_url, params=no_filter_params)

            if resp.status_code == 429:
                retry_after_raw = resp.headers.get("Retry-After", "")
                wait = float(retry_after_raw) if retry_after_raw.isdigit() else _BASE_BACKOFF * (2 ** attempt)
                log.info("turvo_api.rate_limited", carrier_name=carrier_name, wait=wait, attempt=attempt)
                time.sleep(wait)
                continue

            if resp.status_code == 401 and not token_refreshed:
                self._token = None
                self._fetch_token()
                token_refreshed = True
                continue

            resp.raise_for_status()
            return _extract_contact(resp.json())

        return CarrierContact(email=None, phone=None, mc_number=None)

    def get_carrier_email(self, carrier_name: str) -> str | None:
        return self.get_carrier_contact(carrier_name).email


def _pick_primary(record: dict, primary_key: str, list_key: str, flag_key: str) -> str | None:
    val = record.get(primary_key)
    if val:
        return str(val).strip() or None
    values = record.get(list_key) or []
    flags = record.get(flag_key) or []
    for i, v in enumerate(values):
        if i < len(flags) and flags[i] and v:
            return str(v).strip()
    for v in values:
        if v:
            return str(v).strip()
    return None


def _extract_contact(payload: dict) -> CarrierContact:
    data = payload.get("data") or []
    if not data:
        return CarrierContact(email=None, phone=None, mc_number=None)
    c = data[0] if isinstance(data, list) else data
    email = _pick_primary(c, "primaryEmail", "email", "emailPrimary")
    phone = _pick_primary(c, "primaryPhone", "phone", "phonePrimary")
    mc_number = str(c.get("mcNumber") or "").strip() or None
    return CarrierContact(email=email, phone=phone, mc_number=mc_number)


turvo_client: TurvoApiClient | None = None

if settings.turvo_mock_carriers or (
    settings.turvo_api_client_id
    and settings.turvo_api_client_secret
    and settings.turvo_api_username
    and settings.turvo_api_password
    and settings.turvo_api_key
):
    turvo_client = TurvoApiClient(
        token_url=f"{settings.turvo_api_base_url}/lobby/oauth/token",
        search_url="https://app.turvo.com/api/search",
        client_id=settings.turvo_api_client_id or "",
        client_secret=settings.turvo_api_client_secret or "",
        username=settings.turvo_api_username or "",
        password=settings.turvo_api_password or "",
        api_key=settings.turvo_api_key or "",
    )
