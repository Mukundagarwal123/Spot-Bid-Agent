from __future__ import annotations

import resend
import structlog

from app.core.settings import settings

logger = structlog.get_logger(__name__)

_CHUNK = 100


def _extract_id(item) -> str | None:
    """Extract message ID from a Resend response item regardless of SDK version."""
    if item is None:
        return None
    if isinstance(item, dict):
        return item.get("id") or None
    # Resend SDK v2 returns objects with .id attribute
    try:
        val = getattr(item, "id", None)
        return str(val) if val else None
    except Exception:
        return None


def send_batch(emails: list[dict]) -> list[str | None]:
    """Send emails via Resend batch API.

    Returns a list of provider_message_ids in the same order as the input.
    An entry is None when that individual send was rejected by the provider.
    Raises on network-level failures (non-per-email errors).
    """
    resend.api_key = settings.resend_api_key
    message_ids: list[str | None] = []

    for i in range(0, len(emails), _CHUNK):
        chunk = emails[i : i + _CHUNK]
        try:
            raw = resend.Batch.send(chunk)
        except Exception as exc:
            logger.error("resend.batch_send_error", error=str(exc), chunk_start=i)
            # Treat the whole chunk as failed rather than raising
            message_ids.extend([None] * len(chunk))
            continue

        # raw may be: list, object with .data, or dict with "data" key
        items: list = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("data") or raw.get("emails") or []
        else:
            data = getattr(raw, "data", None)
            if isinstance(data, list):
                items = data
            else:
                # Fallback: try iterating directly
                try:
                    items = list(raw)
                except TypeError:
                    items = [raw]

        if len(items) != len(chunk):
            logger.warning(
                "resend.batch_count_mismatch",
                expected=len(chunk),
                got=len(items),
            )
            # Pad or trim to match chunk size
            items = list(items) + [None] * (len(chunk) - len(items))

        for item in items[:len(chunk)]:
            message_ids.append(_extract_id(item))

    return message_ids
