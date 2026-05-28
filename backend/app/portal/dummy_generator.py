"""Deterministic dummy data generator for Feature 001.

Seed is derived from the first 8 hex characters of the lane_id UUID, converted to
an integer. This guarantees identical output for the same lane_id across processes
and Python versions.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Carrier name pool (60 entries — max CRM snapshot size is 30)
# ---------------------------------------------------------------------------
CARRIER_POOL: list[str] = [
    "Swift Transport LLC",
    "Apex Freight Inc",
    "Ridgeline Carriers",
    "Blue Eagle Logistics",
    "Summit Freight Group",
    "Horizon Transport Co",
    "Iron Horse Trucking",
    "Keystone Carriers",
    "Prairie Wind Freight",
    "Titan Logistics LLC",
    "Silver Arrow Transport",
    "Redwood Freight",
    "Cascade Carriers",
    "Lakeside Logistics",
    "Frontier Trucking Co",
    "Mountainview Freight",
    "Coastal Express LLC",
    "Heartland Carriers",
    "Liberty Transport Group",
    "Atlas Freight Solutions",
    "Crossroads Logistics",
    "Gulf Coast Carriers",
    "Great Plains Transport",
    "Pacific Ridge Freight",
    "Sunset Logistics LLC",
    "Valley View Carriers",
    "Northern Star Transport",
    "Southern Cross Freight",
    "Eastern Bound LLC",
    "Western Trails Logistics",
    "Desert Wind Carriers",
    "River Bend Freight",
    "Pine Ridge Transport",
    "Oak Creek Logistics",
    "Maple Leaf Carriers",
    "Rocky Mountain Freight",
    "Lone Star Logistics",
    "Big Sky Transport",
    "Bay Area Carriers",
    "High Plains Freight LLC",
    "Thunder Road Transport",
    "White Mountain Logistics",
    "Green Valley Carriers",
    "Clear Lake Freight",
    "Eagle Eye Transport",
    "Falcon Freight Group",
    "Hawk Logistics LLC",
    "Osprey Carriers",
    "Phoenix Transport Co",
    "Cardinal Freight",
    "Blue Jay Logistics",
    "Sparrow Transport LLC",
    "Stonebridge Freight",
    "Copper Canyon Logistics",
    "Golden Gate Transport",
    "Silver Creek Carriers",
    "Granite Peak Freight",
    "Ironwood Logistics",
    "Timber Ridge Transport",
    "Meadow Brook Carriers",
]

# ---------------------------------------------------------------------------
# Tunable ranges — all percentages are fractions of the "parent" count
# ---------------------------------------------------------------------------
_CARRIERS_CONTACTED = (15, 30)
_RESPONDED_RATE = (0.40, 0.75)
_EMAILS_SENT_RATE = (0.60, 0.80)
_EMAILS_CLICKED_RATE = (0.25, 0.50)
_EMAIL_REPLIES_RATE = (0.30, 0.60)
_SMS_SENT_RATE = (0.50, 0.70)
_SMS_REPLIES_RATE = (0.20, 0.45)
_WA_SENT_RATE = (0.30, 0.50)
_WA_REPLIES_RATE = (0.25, 0.55)
_CARRIER_COUNT = (10, 30)
_AVG_RESPONSE_MINUTES = (10, 240)
_LAST_CONTACTED_DAYS = (1, 90)
_CHANNEL_WEIGHTS = [0.50, 0.30, 0.20]  # email, sms, whatsapp

_CHANNELS = ["email", "sms", "whatsapp"]

# ---------------------------------------------------------------------------
# Fixed timeline templates (offsets are deterministic, not seeded)
# ---------------------------------------------------------------------------
_TIMELINE: list[tuple[int, str, str, str | None]] = [
    (0, "lane_created", "Lane created", None),
    (5, "outreach_simulated", "Outreach campaign simulated (email + SMS + WhatsApp)", None),
    (17, "engagement_simulated", "Carrier engagement signals received", None),
    (55, "response_simulated", "Carrier responses logged", None),
]


def _seed_from_lane_id(lane_id: uuid.UUID) -> int:
    return int(str(lane_id).replace("-", "")[:8], 16)


def generate_metrics(lane_id: uuid.UUID) -> dict[str, int]:
    rng = random.Random(_seed_from_lane_id(lane_id))
    contacted = rng.randint(*_CARRIERS_CONTACTED)
    responded = int(contacted * rng.uniform(*_RESPONDED_RATE))
    emails_sent = int(contacted * rng.uniform(*_EMAILS_SENT_RATE))
    emails_clicked = int(emails_sent * rng.uniform(*_EMAILS_CLICKED_RATE))
    email_replies = int(emails_clicked * rng.uniform(*_EMAIL_REPLIES_RATE))
    sms_sent = int(contacted * rng.uniform(*_SMS_SENT_RATE))
    sms_replies = int(sms_sent * rng.uniform(*_SMS_REPLIES_RATE))
    whatsapp_sent = int(contacted * rng.uniform(*_WA_SENT_RATE))
    whatsapp_replies = int(whatsapp_sent * rng.uniform(*_WA_REPLIES_RATE))
    return {
        "carriers_contacted": contacted,
        "carriers_responded": responded,
        "emails_sent": emails_sent,
        "emails_clicked": emails_clicked,
        "email_replies": email_replies,
        "sms_sent": sms_sent,
        "sms_replies": sms_replies,
        "whatsapp_sent": whatsapp_sent,
        "whatsapp_replies": whatsapp_replies,
    }


def generate_timeline(
    lane_id: uuid.UUID, created_at: datetime
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for i, (offset_min, event_type, label, channel) in enumerate(_TIMELINE):
        events.append(
            {
                "event_type": event_type,
                "label": label,
                "channel": channel,
                "event_at": created_at + timedelta(minutes=offset_min),
                "sort_order": i,
            }
        )
    return events


def generate_carrier_crm(
    lane_id: uuid.UUID, created_at: datetime
) -> list[dict[str, object]]:
    rng = random.Random(_seed_from_lane_id(lane_id))
    count = rng.randint(*_CARRIER_COUNT)
    names = rng.sample(CARRIER_POOL, count)
    result: list[dict[str, object]] = []
    for name in names:
        times_contacted = rng.randint(1, 8)
        times_responded = rng.randint(0, times_contacted)
        response_rate = round(
            (times_responded / times_contacted * 100) if times_contacted else 0.0, 2
        )
        avg_rt = rng.randint(*_AVG_RESPONSE_MINUTES)
        channel = rng.choices(_CHANNELS, weights=_CHANNEL_WEIGHTS, k=1)[0]
        days_ago = rng.randint(*_LAST_CONTACTED_DAYS)
        hours_ago = rng.randint(0, 23)
        last_contacted = created_at - timedelta(days=days_ago, hours=hours_ago)
        result.append(
            {
                "carrier_name": name,
                "times_contacted": times_contacted,
                "times_responded": times_responded,
                "response_rate": response_rate,
                "avg_response_time_minutes": avg_rt,
                "preferred_channel": channel,
                "last_contacted_at": last_contacted,
            }
        )
    return result
