from __future__ import annotations

import resend

from app.core.settings import settings

_CHUNK = 100


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
        results = resend.Batch.send(chunk)
        for item in results:
            message_ids.append(item.get("id") if isinstance(item, dict) else getattr(item, "id", None))

    return message_ids
