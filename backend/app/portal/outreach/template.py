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

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width,initial-scale=1" /></head>
<body style="margin:0;padding:0;background:#f0f4f9;font-family:'Segoe UI',Arial,sans-serif;-webkit-font-smoothing:antialiased">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f0f4f9;padding:32px 16px">
<tr><td align="center">
  <table width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.10);max-width:600px">

    <!-- Header -->
    <tr><td style="background:#0f2f47;padding:28px 36px 24px">
      <div style="font-size:22px;font-weight:800;color:#ffffff;letter-spacing:-.3px">T3RA Logistics</div>
      <div style="font-size:14px;color:#abc3d9;margin-top:4px;font-weight:600">{origin} &rarr; {destination}</div>
      <div style="display:inline-block;margin-top:10px;background:#1d4ed8;border-radius:6px;padding:4px 12px;font-size:11px;font-weight:700;color:#fff;letter-spacing:.04em;text-transform:uppercase">Spot Bid Opportunity</div>
    </td></tr>

    <!-- Body -->
    <tr><td style="padding:32px 36px">

      <p style="margin:0 0 14px;font-size:16px;font-weight:700;color:#12263a">Hi {carrier_name},</p>
      <p style="margin:0 0 22px;font-size:14px;color:#344054;line-height:1.65">
        We have an active spot freight opportunity that matches your operating area.
        We're moving quickly to cover this load and would appreciate your best rate.
      </p>

      <!-- Lane detail box -->
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="background:#f0f7ff;border-left:4px solid #1d4ed8;border-radius:0 10px 10px 0;margin-bottom:22px">
        <tr><td style="padding:18px 20px">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#5e748a;font-weight:700;margin-bottom:12px">Lane Details</div>
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="font-size:13px;color:#5e748a;padding:3px 0;width:110px;font-weight:600">Origin</td>
              <td style="font-size:13px;color:#12263a;padding:3px 0;font-weight:700">{origin}</td>
            </tr>
            <tr>
              <td style="font-size:13px;color:#5e748a;padding:3px 0;font-weight:600">Destination</td>
              <td style="font-size:13px;color:#12263a;padding:3px 0;font-weight:700">{destination}</td>
            </tr>
            <tr>
              <td style="font-size:13px;color:#5e748a;padding:3px 0;font-weight:600">Equipment</td>
              <td style="font-size:13px;color:#12263a;padding:3px 0">{equipment}</td>
            </tr>
            <tr>
              <td style="font-size:13px;color:#5e748a;padding:3px 0;font-weight:600">Pickup</td>
              <td style="font-size:13px;color:#12263a;padding:3px 0">{pickup}</td>
            </tr>
          </table>
        </td></tr>
      </table>

      {notes_block}

      <p style="margin:0 0 26px;font-size:14px;color:#344054;line-height:1.65">
        Reply with your available capacity and all-in rate and we'll follow up within the hour.
      </p>

      <!-- CTA -->
      <table cellpadding="0" cellspacing="0" border="0">
        <tr><td style="background:#1d4ed8;border-radius:9px">
          <a href="mailto:dispatch@t3ralogistics.com?subject=Re: Spot Bid {origin} to {destination}"
             style="display:inline-block;padding:13px 30px;font-size:14px;font-weight:700;color:#ffffff;text-decoration:none;letter-spacing:.01em">
            Reply to Bid &rarr;
          </a>
        </td></tr>
      </table>
    </td></tr>

    <!-- Footer -->
    <tr><td style="background:#f8fbff;padding:16px 36px;border-top:1px solid #e2e8f0">
      <p style="margin:0;font-size:11px;color:#94a3b8">T3RA Logistics &middot; Spot Bid Operations</p>
      <p style="margin:5px 0 0;font-size:11px;color:#94a3b8">
        You're receiving this email because your fleet was identified as a fit for this lane.
        To opt out, reply with "unsubscribe".
      </p>
    </td></tr>

  </table>
</td></tr>
</table>
</body>
</html>
"""

_NOTES_HTML_BLOCK = """\
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#fffbeb;border-left:4px solid #d97706;border-radius:0 10px 10px 0;margin-bottom:22px">
  <tr><td style="padding:14px 20px">
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#92400e;font-weight:700;margin-bottom:6px">Special Notes</div>
    <div style="font-size:13px;color:#78350f;line-height:1.55">{notes}</div>
  </td></tr>
</table>
"""


@dataclass
class EmailDraft:
    subject: str
    body: str
    html_body: str


def generate(lane: PortalLane, notes: str, carrier_name: str = "") -> EmailDraft:
    origin = f"{lane.origin_city}, {lane.origin_state}"
    if lane.origin_zip:
        origin += f" {lane.origin_zip}"

    destination = f"{lane.destination_city}, {lane.destination_state}"
    if lane.destination_zip:
        destination += f" {lane.destination_zip}"

    equipment = _EQUIPMENT_LABELS.get(lane.equipment_type, lane.equipment_type.replace("_", " ").title())
    pickup = lane.pickup_date.strftime("%B %d, %Y") if lane.pickup_date else "TBD"
    greeting_name = carrier_name.strip() or "there"

    subject = (
        f"Spot Bid: {lane.origin_city}, {lane.origin_state}"
        f" → {lane.destination_city}, {lane.destination_state}"
        f" | {equipment} | {pickup}"
    )

    notes_text_block = ""
    notes_html_block = ""
    if notes and notes.strip():
        notes_text_block = (
            "\nAdditional Notes\n"
            "----------------\n"
            f"{notes.strip()}\n\n"
        )
        notes_html_block = _NOTES_HTML_BLOCK.format(notes=notes.strip())

    body = (
        f"Hi {greeting_name},\n\n"
        "We have a spot freight opportunity and are reaching out to confirm your\n"
        "availability and best rate for the lane below.\n\n"
        "Lane Details\n"
        "------------\n"
        f"Origin:       {origin}\n"
        f"Destination:  {destination}\n"
        f"Equipment:    {equipment}\n"
        f"Pickup Date:  {pickup}\n\n"
        f"{notes_text_block}"
        "Please reply with your availability and best all-in rate.\n"
        "We are working to cover this load quickly and appreciate a fast response.\n\n"
        "Thank you,\n"
        "Spot Bid Operations\n"
        "T3RA Logistics\n"
    )

    html_body = _HTML_TEMPLATE.format(
        carrier_name=greeting_name,
        origin=origin,
        destination=destination,
        equipment=equipment,
        pickup=pickup,
        notes_block=notes_html_block,
    )

    return EmailDraft(subject=subject, body=body, html_body=html_body)
