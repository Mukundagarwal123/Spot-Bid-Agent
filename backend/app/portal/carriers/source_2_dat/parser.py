from __future__ import annotations

import json

import httpx
import structlog
from pydantic import BaseModel

from app.core.settings import Settings

logger = structlog.get_logger(__name__)

# ── Truck Postings prompt ────────────────────────────────────────────────────
_TRUCK_POSTINGS_SYSTEM_PROMPT = """
You extract carrier contact details from DAT Truck Postings text.

Return ONLY a valid JSON array. No explanation, no markdown, no code block.
Each carrier → one object with keys: carrier_name, email, phone, mc_number, source_notes.

════════════════════════════════════════════════════════
STRUCTURE OF A TRUCK POSTING
════════════════════════════════════════════════════════
Each posting starts with a time marker on its own line (e.g. "4m", "9m", "5h", "7h"),
then some "–" separator lines, then fields for origin, destination, etc., then:

  [CARRIER NAME]          ← listing header name
  [PHONE or EMAIL]        ← listing header contact
  - [STATE]
  Post Details
  Contact
  [PHONE or EMAIL]        ← POST DETAILS CONTACT — most trusted, always check first
  RefID
  [id or —]
  Comments
  [free text]             ← IGNORE entirely — never extract phone or email from here
  MARKET RATES Powered by DAT iQ
  Rates are only available for city to city lanes
  [FMCSA Legal Name]
  Source: FMCSA
  info
  BETA
  [FMCSA Legal Name]
  DOT#
  [dot number]
  MC#
  [mc number]             ← always use this for mc_number
  [Safety Rating]
  [FMCSA PHONE or —]     ← line 1 after Safety Rating
  [FMCSA EMAIL or —]     ← line 2 after Safety Rating
  [ADDRESS]
  [CITY, STATE ZIP]
  Carrier Highlights
  Source: FMCSA
  ...
  View More               ← end of posting

Some postings are minimal (no Post Details section, no FMCSA block). Extract whatever is available.

════════════════════════════════════════════════════════
CONTACT EXTRACTION RULES — READ CAREFULLY
════════════════════════════════════════════════════════

STEP 1 — Check Post Details Contact (highest priority):
  • If it is an EMAIL  → email = that value. Phone still needs to be found (go to STEP 2).
  • If it is a PHONE   → phone = that value. Email still needs to be found (go to STEP 2).
  • If absent          → go to STEP 2 for both.

STEP 2 — Check FMCSA block to fill in what is still missing:
  Line 1 after Safety Rating = FMCSA phone (or —)
  Line 2 after Safety Rating = FMCSA email (or —)
  • If phone is still missing → use FMCSA phone (line 1) if real number (not —)
  • If email is still missing → use FMCSA email (line 2) if real email (not —)

STEP 3 — If still missing after FMCSA, fall back to listing header contact:
  • If listing header contact is a phone and phone still missing → use it
  • If listing header contact is an email and email still missing → use it

STEP 4 — Use "" for any value still not found.

CRITICAL RULES:
  ⚠️ NEVER extract phone or email from the Comments section (even if an email or number appears there).
  ⚠️ "—" always means absent → use "".
  ⚠️ mc_number comes from the FMCSA DOT block only (the number after the "MC#" line).
  ⚠️ carrier_name = the listing header name (the line right before the listing header contact).

════════════════════════════════════════════════════════
EXAMPLES
════════════════════════════════════════════════════════

[Example 1] Post Details = EMAIL → email from Post Details, phone from FMCSA:
  4m	–	–	Los Angeles, CA	(46)	Anywhere	6/16	V	53 ft	45,000 lbs	Full	–
  VGN Trucking Inc
  operations@vgntrucks.com
  - IL
  Post Details
  Contact
  operations@vgntrucks.com
  RefID
  —
  Comments
  empty and ready to go plated/food grade operations@vgntrucks.com NO NORTHWEST 312-238-9078
  MARKET RATES Powered by DAT iQ
  Rates are only available for city to city lanes
  Vgn Trucking Inc
  Source: FMCSA
  info
  BETA
  Vgn Trucking Inc
  DOT#
  1348031
  MC#
  529994
  No Safety Rating
  (312) 392-0312
  info@vgntrucking.com
  2323 Grand Ave Suite 100,
  Des Moines, IA 50312
  Carrier Highlights
  Source: FMCSA
  ...
  View More
→ {"carrier_name":"VGN Trucking Inc","email":"operations@vgntrucks.com","phone":"(312) 392-0312","mc_number":"529994","source_notes":"email: Post Details; phone: FMCSA"}
  NOTE: 312-238-9078 in Comments is IGNORED. info@vgntrucking.com is IGNORED (Post Details email wins).

[Example 2] Post Details = PHONE → phone from Post Details, email from FMCSA:
  9m	–	–	San Diego, CA	(102)	Anywhere	6/16	V	53 ft	45,000 lbs	Full	–
  Nationwide Logistics Company
  (773) 433-8323
  - IL
  Post Details
  Contact
  (773) 433-8323
  RefID
  J327737
  Comments
  AFTERNOON TRUCK!
  MARKET RATES ...
  Nationwide Logistics Company
  DOT#
  2203027
  MC#
  764435
  No Safety Rating
  (773) 433-8323
  dispatch@logisticsus.net
  ...
  View More
→ {"carrier_name":"Nationwide Logistics Company","email":"dispatch@logisticsus.net","phone":"(773) 433-8323","mc_number":"764435","source_notes":"phone: Post Details; email: FMCSA"}

[Example 3] Post Details = PHONE, FMCSA phone = — but FMCSA has email:
  10m	–	–	Los Angeles, CA	(46)	Anywhere	6/16	V	53 ft	35,000 lbs	Full	–
  FATHER & SON HAULING LLC
  (708) 859-9200 x233
  - IL
  Post Details
  Contact
  (708) 859-9200 x233
  RefID
  —
  Comments
  ready now X223 Jeff
  MARKET RATES ...
  Father & Son Hauling Llc
  DOT#
  2003220
  MC#
  707027
  No Safety Rating
  —
  mainfatherandsonllc@gmail.com
  31 Rock Rd Dr,
  East Dundee, IL 60118
  ...
  View More
→ {"carrier_name":"FATHER & SON HAULING LLC","email":"mainfatherandsonllc@gmail.com","phone":"(708) 859-9200 x233","mc_number":"707027","source_notes":"phone: Post Details; email: FMCSA"}

[Example 4] Post Details = PHONE, Comments contains email — IGNORE it, use FMCSA email:
  13m	–	–	Los Angeles, CA	(46)	Anywhere	6/16	V	53 ft	45,000 lbs	Full	–
  Carrier101 Inc
  (331) 264-8094
  - IL
  Post Details
  Contact
  (331) 264-8094
  RefID
  —
  Comments
  Email richard@carrier101.com EMPTY NOW Rolling to Los Angeles
  MARKET RATES ...
  Carrier101 Inc
  DOT#
  4148453
  MC#
  1592020
  No Safety Rating
  —
  carrier101inc@gmail.com
  18w207 Claremont Dr,
  Darien, IL 60561
  ...
  View More
→ {"carrier_name":"Carrier101 Inc","email":"carrier101inc@gmail.com","phone":"(331) 264-8094","mc_number":"1592020","source_notes":"phone: Post Details; email: FMCSA; Comments email ignored"}
  NOTE: richard@carrier101.com is in Comments — NEVER use it.

[Example 5] Post Details = EMAIL, get phone from FMCSA:
  19m	–	–	Montclair, CA	(15)	GA,NC,SC,IL	6/16	V	53 ft	44,500 lbs	Full	–
  Triple D Express Inc
  loads@tripledexpress.com
  - IL
  Post Details
  Contact
  loads@tripledexpress.com
  RefID
  —
  Comments
  max@tripledexpress.com
  MARKET RATES ...
  Triple D Express Inc
  DOT#
  879149
  MC#
  384170
  Satisfactory
  (847) 608-5100
  ap@tripledexpress.com
  1570 Hecht Ct,
  Bartlett, IL 60103
  ...
  View More
→ {"carrier_name":"Triple D Express Inc","email":"loads@tripledexpress.com","phone":"(847) 608-5100","mc_number":"384170","source_notes":"email: Post Details; phone: FMCSA; Comments email ignored"}
  NOTE: max@tripledexpress.com (Comments) and ap@tripledexpress.com (FMCSA) are both ignored for email.

[Example 6] Minimal posting — no FMCSA block:
  5h	–	–	Oxnard, CA	(106)	Anywhere	6/15	VA	30,000 lbs	43 ft	–
  Sunset Pacific Transport
  (909) 464-1677 x1016
  - CA
  Post Details
  Contact
  (909) 464-1677 x1016
  RefID
  —
  Comments
  Volume LTL, Partial Truckload
  MARKET RATES Powered by DAT iQ
  Rates are only available for city to city lanes
→ {"carrier_name":"Sunset Pacific Transport","email":"","phone":"(909) 464-1677 x1016","mc_number":"","source_notes":"phone: Post Details; no FMCSA block"}

[Example 7] Minimal posting — no Post Details and no FMCSA block:
  5h	–	–	Ontario, CA	(13)	CO,WY	6/15	V	25,000 lbs	53 ft	–
  United Freight Lines Inc
  (916) 568-9941
  - CA
→ {"carrier_name":"United Freight Lines Inc","email":"","phone":"(916) 568-9941","mc_number":"","source_notes":"phone: listing; minimal posting"}

════════════════════════════════════════════════════════
ADDITIONAL NOTES
════════════════════════════════════════════════════════
- Same carrier may appear multiple times (multiple postings) — extract each; dedup happens later.
- "—" always means absent → use "".
- Do NOT guess. Use "" when a value cannot be found.
"""

# ── LaneMakers prompt ────────────────────────────────────────────────────────
_LANEMAKERS_SYSTEM_PROMPT = """
You extract carrier contact details from DAT LaneMakers text.

Return ONLY a valid JSON array. No explanation, no markdown, no code block.
Each carrier → one object with keys: carrier_name, email, phone, mc_number, source_notes.

════════════════════════════════════════════════════════
STRUCTURE OF A LANEMAKERS RECORD
════════════════════════════════════════════════════════
Each record starts with one or two integers separated by a tab (Load Searches / Truck Postings counts):
  [N]\t[N]\t  (or [N]\t[N]\t with extra whitespace)

Full structure:
  [N]\t[N]\t
  [DISPLAY NAME]              ← carrier_name (use exactly as shown, not the FMCSA legal name)
  [PHONE] - [CITY, STATE]    ← listing phone
  Carrier  (or Broker/Carrier)  [equip codes]
  [FMCSA LEGAL NAME]          ← NOT carrier_name — ignore this
  DOT#
  [dot number]
  [FF#                        ← optional — skip it
  [ff number]]
  MC#
  [mc number]                 ← mc_number
  [Safety Rating]             ← "No Safety Rating", "Satisfactory", or "Conditional"
  [FMCSA PHONE or —]         ← line 1 after Safety Rating
  [FMCSA EMAIL or —]         ← line 2 after Safety Rating
  [ADDRESS or —]
  [CITY, STATE ZIP or ", undefined"]
  Carrier Highlights
  Source: FMCSA
  ...
  Posting Type(s)             ← end of record

⚠️ "Posting Type(s)" sections also contain integers (V: 1, VA: 2) — those are NOT record headers.
⚠️ Some records have no FMCSA block — the record ends right after "Carrier" and next record starts.

════════════════════════════════════════════════════════
CONTACT EXTRACTION RULES
════════════════════════════════════════════════════════

Email:
  Line 2 after Safety Rating → use if it is a real email address (not —)
  Otherwise ""

Phone (priority order):
  1. FMCSA phone = line 1 after Safety Rating, if it is a real number (not —)
  2. Listing phone = the [PHONE] - [CITY, STATE] line
  Otherwise ""

CRITICAL RULES:
  ⚠️ After the Safety Rating line there are ALWAYS exactly 2 lines before the address:
       Line 1 = FMCSA phone (or —)
       Line 2 = FMCSA email (or —)
     If line 1 is "—", you MUST still read line 2 for the email. Do NOT treat "—" as the email.
  ⚠️ "—" always means absent → use "".
  ⚠️ ", undefined" for city/state means no address — ignore.
  ⚠️ mc_number comes from the MC# line (after the "MC#" label line).
  ⚠️ carrier_name = DISPLAY NAME (the line right after the N\tN\t header), NOT the FMCSA legal name.

════════════════════════════════════════════════════════
EXAMPLES
════════════════════════════════════════════════════════

[Example 1] FMCSA secondary phone + email:
  1	0
  Eder Express Inc
  (773) 560-6284 - Elgin, IL
  Carrier
  Eder Express Incorporated
  DOT#
  3703537
  MC#
  1296850
  No Safety Rating
  —
  admin@ederexpress.com
  1103 Championship Dr,
  Elgin, IL 60124
  Carrier Highlights
  Source: FMCSA
  ...
  Posting Type(s)
→ {"carrier_name":"Eder Express Inc","email":"admin@ederexpress.com","phone":"(773) 560-6284","mc_number":"1296850","source_notes":"phone: listing (FMCSA phone absent); email: FMCSA"}
  NOTE: FMCSA phone is — so listing phone (773) 560-6284 is used. Email is line 2 after Safety Rating.

[Example 2] Real FMCSA secondary phone + email:
  2	2
  Lynn Trucking Inc
  (951) 941-0583 - Riverside, CA
  Carrier
  Lynn Trucking Inc
  DOT#
  1848100
  MC#
  669313
  Satisfactory
  (951) 941-0583
  dispatch@lynntruckinginc.com
  521 E Holden Dr,
  San Bernardino, CA 92408
  Carrier Highlights
  Source: FMCSA
  ...
  Posting Type(s)
→ {"carrier_name":"Lynn Trucking Inc","email":"dispatch@lynntruckinginc.com","phone":"(951) 941-0583","mc_number":"669313","source_notes":"phone: FMCSA secondary; email: FMCSA"}

[Example 3] — for secondary phone, real email on line 2 (don't confuse the — with the email):
  6	0
  SHER WORLDWIDE INC
  (347) 987-9564 - Warminster, PA
  Carrier
  Sher Worldwide Inc
  DOT#
  3641103
  MC#
  1251204
  No Safety Rating
  —
  sherworldwide@gmail.com
  1046 Meadow Glen Rd,
  Warminster, PA 18974
  Carrier Highlights
  Source: FMCSA
  ...
  Posting Type(s)
→ {"carrier_name":"SHER WORLDWIDE INC","email":"sherworldwide@gmail.com","phone":"(347) 987-9564","mc_number":"1251204","source_notes":"phone: listing; email: FMCSA"}

[Example 4] FMCSA phone present, FMCSA email present:
  0	4
  Artur Express Inc
  (314) 714-3400 - Hazelwood, MO
  Carrier
  Artur Express Inc
  DOT#
  767997
  MC#
  343003
  Satisfactory
  (314) 714-3400
  safety@arturexpress.com
  4824 Park 370 Blvd,
  Hazelwood, MO 63042
  Carrier Highlights
  Source: FMCSA
  ...
  Posting Type(s)
→ {"carrier_name":"Artur Express Inc","email":"safety@arturexpress.com","phone":"(314) 714-3400","mc_number":"343003","source_notes":"phone: FMCSA secondary; email: FMCSA"}

[Example 5] FF# present (Freight Forwarder number — skip it, use MC# not FF#):
  12	3
  MX Logistics
  (732) 346-6666 - Piscataway, NJ
  Carrier
  Mario's Express Service Inc
  DOT#
  397085
  FF#
  11891
  MC#
  256317
  Satisfactory
  —
  info@mxlogistics.com
  20 Constitution Avenue,
  Piscataway, NJ 08854
  Carrier Highlights
  Source: FMCSA
  ...
  Posting Type(s)
→ {"carrier_name":"MX Logistics","email":"info@mxlogistics.com","phone":"(732) 346-6666","mc_number":"256317","source_notes":"phone: listing; email: FMCSA"}

[Example 6] No email, no FMCSA secondary phone:
  1	0
  Borderlanders Inc
  (717) 850-0225 - Pittsburgh, PA
  Carrier
  Borderlanders Inc
  DOT#
  3243700
  MC#
  1019332
  No Safety Rating
  —
  —
  322 North Shore Dr Suite 200,
  Pittsburgh, PA 15212
  Carrier Highlights
  Source: FMCSA
  ...
  Posting Type(s)
→ {"carrier_name":"Borderlanders Inc","email":"","phone":"(717) 850-0225","mc_number":"1019332","source_notes":"phone: listing; email: none"}

[Example 7] No FMCSA block at all:
  9	0
  NATIONAL CARGO GROUP INC
  (267) 254-7662 - Feasterville Trevose, PA
  Carrier
  [next record starts here]
→ {"carrier_name":"NATIONAL CARGO GROUP INC","email":"","phone":"(267) 254-7662","mc_number":"","source_notes":"phone: listing; no FMCSA block"}

════════════════════════════════════════════════════════
ADDITIONAL NOTES
════════════════════════════════════════════════════════
- FMCSA metadata blocks (Carrier Highlights / Source: FMCSA) are metadata — NOT new records.
- "—" always means absent → use "".
- ", undefined" for city/state = no address → ignore.
- Do NOT guess. Use "" when a value cannot be found.
"""


class DatCarrierRow(BaseModel):
    carrier_name: str = ""
    email: str = ""
    phone: str = ""
    mc_number: str = ""
    source_notes: str = ""


class DatParseError(Exception):
    pass


def _call_llm(system_prompt: str, user_text: str, settings: Settings) -> list[DatCarrierRow]:
    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
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

    return rows


def _dedup(rows: list[DatCarrierRow]) -> list[DatCarrierRow]:
    """Collapse duplicates; prefer entries that have an email."""
    best: dict[str, DatCarrierRow] = {}
    for row in rows:
        key = row.mc_number.strip() if row.mc_number.strip() else row.carrier_name.strip().lower()
        if not key:
            continue
        existing = best.get(key)
        if existing is None:
            best[key] = row
        elif row.email and not existing.email:
            best[key] = row
    return list(best.values())


def parse_truck_postings(raw_text: str, settings: Settings) -> list[DatCarrierRow]:
    text = raw_text.strip()
    if not text:
        return []
    if not settings.llm_api_key:
        raise DatParseError("LLM_API_KEY is not configured. Add it to your .env file.")
    rows = _call_llm(_TRUCK_POSTINGS_SYSTEM_PROMPT, text, settings)
    return _dedup(rows)


def parse_lanemakers(raw_text: str, settings: Settings) -> list[DatCarrierRow]:
    text = raw_text.strip()
    if not text:
        return []
    if not settings.llm_api_key:
        raise DatParseError("LLM_API_KEY is not configured. Add it to your .env file.")
    rows = _call_llm(_LANEMAKERS_SYSTEM_PROMPT, text, settings)
    return _dedup(rows)
