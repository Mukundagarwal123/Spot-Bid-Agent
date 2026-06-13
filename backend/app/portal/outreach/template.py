from __future__ import annotations

from dataclasses import dataclass

from app.db.models import PortalLane

_EQUIPMENT_LABELS = {
    "dry_van": "Dry Van",
    "reefer": "Reefer",
    "flatbed": "Flatbed",
    "power_only": "Power Only",
    "other": "Other",
}


@dataclass
class EmailDraft:
    subject: str
    body: str


def generate(lane: PortalLane, notes: str) -> EmailDraft:
    origin = f"{lane.origin_city}, {lane.origin_state}"
    if lane.origin_zip:
        origin += f" {lane.origin_zip}"

    destination = f"{lane.destination_city}, {lane.destination_state}"
    if lane.destination_zip:
        destination += f" {lane.destination_zip}"

    equipment = _EQUIPMENT_LABELS.get(lane.equipment_type, lane.equipment_type.replace("_", " ").title())
    pickup = lane.pickup_date.strftime("%B %d, %Y") if lane.pickup_date else "TBD"

    subject = (
        f"Spot Bid Opportunity: {lane.origin_city}, {lane.origin_state}"
        f" → {lane.destination_city}, {lane.destination_state}"
        f" | {equipment}"
    )

    notes_block = ""
    if notes and notes.strip():
        notes_block = (
            "\nAdditional Notes\n"
            "----------------\n"
            f"{notes.strip()}\n"
        )

    body = (
        "Hi,\n\n"
        "We have a spot freight opportunity and are reaching out to confirm your\n"
        "availability and best rate for the lane below.\n\n"
        "Lane Details\n"
        "------------\n"
        f"Origin:       {origin}\n"
        f"Destination:  {destination}\n"
        f"Equipment:    {equipment}\n"
        f"Pickup Date:  {pickup}\n"
        f"{notes_block}\n"
        "Please reply to this email with your availability and best rate.\n"
        "We are working to cover this load quickly and appreciate a fast response.\n\n"
        "Thank you,\n"
        "Spot Bid Operations\n"
        "T3RA Logistics\n"
    )

    return EmailDraft(subject=subject, body=body)
