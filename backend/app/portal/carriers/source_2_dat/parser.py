from __future__ import annotations

import json

import httpx
import structlog
from pydantic import BaseModel

from app.core.settings import Settings

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """
You extract carrier contact details from DAT load board copied text.

Return ONLY a valid JSON array. No explanation, no markdown, no code block.

Each DAT posting becomes ONE result object with these fields:
- carrier_name
- email
- phone
- mc_number
- source_notes

DAT POSTING STRUCTURE — each posting has up to three data zones:

ZONE 1 — LISTING HEADER:
  Carrier name line, then a phone OR email (the listing contact), then state abbreviation.
  Example:
    Go To Logistics Inc/Non Stop Logistics Inc
    dominick.garcia@go2.us
    - IL

ZONE 2 — POST DETAILS section (labeled "Post Details" then "Contact"):
  The direct contact for this specific truck posting. Highest priority.
  Example:
    Post Details
    Contact
    (530) 777-3848

ZONE 3 — FMCSA PROFILE section (labeled "Source: FMCSA", not always present):
  The official carrier profile. Contains MC#, phone, and email.
  Example:
    AR Logistics
    Source: FMCSA
    ...
    MC# 123456
    (530) 777-3848
    dispatch@arlogistics.com
    123 Main St, ...

EXTRACTION RULES — apply in this exact priority order:

carrier_name:
  Use the name from the LISTING HEADER exactly as shown. Never modify it.
  Example: "Go To Logistics Inc/Non Stop Logistics Inc" must stay exactly that.

phone:
  1. If POST DETAILS Contact contains a phone number → use it
  2. Else if FMCSA PROFILE section has a phone → use it
  3. Else if LISTING HEADER contact is a phone number → use it
  4. Else → ""
  Keep extensions exactly as written (e.g. "(916) 515-8065 x1045").
  Ignore any phone numbers found only in Comments (driver phones).

email:
  1. If POST DETAILS Contact contains an email address → use it
  2. Else if FMCSA PROFILE section has an email → use it
  3. Else if LISTING HEADER contact is an email address → use it
  4. Else → ""

mc_number:
  ONLY from the FMCSA "Source: FMCSA" section MC# field.
  If no FMCSA section is present → ""
  Never infer MC# from any other part of the text.

source_notes:
  Brief note on where the phone and email came from.
  Example: "phone: Post Details; email: FMCSA profile"

CRITICAL RULES:
- Do NOT guess. Use "" when a value cannot be found.
- The FMCSA section repeats the carrier name — do NOT count it as a separate posting.
- Each truck posting = one result object, even if the same carrier appears multiple times with different trucks.
- "canceled" in a posting is a status label — ignore it, still extract the carrier.

EXAMPLES:

Example 1 — Post Details has phone only, FMCSA has email:
  Listing: Usko Express Inc / (916) 515-8065 x1045
  Post Details Contact: (916) 515-8065 x1045
  FMCSA: MC# 563453, safety@uskoinc.com
  → {"carrier_name": "Usko Express Inc", "phone": "(916) 515-8065 x1045", "email": "safety@uskoinc.com", "mc_number": "563453", "source_notes": "phone: Post Details; email: FMCSA profile"}

Example 2 — Post Details has email only, FMCSA not present:
  Listing: Go To Logistics Inc/Non Stop Logistics Inc / dominick.garcia@go2.us
  Post Details Contact: dominick.garcia@go2.us
  No FMCSA section.
  → {"carrier_name": "Go To Logistics Inc/Non Stop Logistics Inc", "phone": "", "email": "dominick.garcia@go2.us", "mc_number": "", "source_notes": "email: Post Details"}

Example 3 — No Post Details section, FMCSA present:
  Listing: Mann Bros Llc / (530) 675-5003
  No Post Details Contact.
  FMCSA: MC# 950228, mannbrosllc@gmail.com
  → {"carrier_name": "Mann Bros Llc", "phone": "(530) 675-5003", "email": "mannbrosllc@gmail.com", "mc_number": "950228", "source_notes": "phone: listing header; email: FMCSA profile"}

Example 4 — Post Details has phone, FMCSA has different phone and email:
  Listing: Sabr Cargo Inc / (630) 413-4296 x156
  Post Details Contact: (630) 413-4296 x156
  FMCSA: MC# 1176151, (224) 310-1839, dispatch@sabrcargo.com
  → {"carrier_name": "Sabr Cargo Inc", "phone": "(630) 413-4296 x156", "email": "dispatch@sabrcargo.com", "mc_number": "1176151", "source_notes": "phone: Post Details; email: FMCSA profile"}
"""


class DatCarrierRow(BaseModel):
    carrier_name: str = ""
    email: str = ""
    phone: str = ""
    mc_number: str = ""
    source_notes: str = ""


class DatParseError(Exception):
    pass


def parse_dat_text(raw_text: str, settings: Settings) -> list[DatCarrierRow]:
    text = raw_text.strip()
    if not text:
        return []

    if not settings.llm_api_key:
        raise DatParseError(
            "LLM_API_KEY is not configured. Add it to your .env file."
        )

    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise DatParseError("LLM request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise DatParseError(f"LLM API error: {exc.response.status_code}") from exc
    except httpx.LocalProtocolError as exc:
        raise DatParseError(
            "LLM_API_KEY is missing or invalid. Add it to your .env file."
        ) from exc

    content = response.json()["choices"][0]["message"]["content"].strip()

    try:
        raw_rows = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.error("dat_llm_json_parse_error", content_preview=content[:200])
        raise DatParseError("LLM returned invalid JSON") from exc

    if not isinstance(raw_rows, list):
        raise DatParseError("LLM response was not a JSON array")

    rows: list[DatCarrierRow] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        row = DatCarrierRow(
            carrier_name=item.get("carrier_name") or "",
            email=item.get("email") or "",
            phone=item.get("phone") or "",
            mc_number=item.get("mc_number") or "",
            source_notes=item.get("source_notes") or "",
        )
        if not row.carrier_name.strip():
            continue
        rows.append(row)

    # Deduplicate within the same paste by (carrier_name, mc_number) when mc_number is present
    seen: set[tuple[str, str]] = set()
    deduped: list[DatCarrierRow] = []
    for row in rows:
        if row.mc_number:
            key = (row.carrier_name, row.mc_number)
            if key in seen:
                continue
            seen.add(key)
        deduped.append(row)

    return deduped
