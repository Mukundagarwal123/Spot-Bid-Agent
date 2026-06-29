"""
Bypass-LLM DAT injector.
Parsed manually from DAT Trucks.txt + lanemakerdat.txt (2026-06-24).
Priority: Comments email/phone > Post Details > FMCSA > listing header.

Usage:
    python scripts/inject_dat_manual.py               # creates new lane + injects
    python scripts/inject_dat_manual.py <lane_id>     # injects into existing lane
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.base import session_scope
from app.db.models import PortalLane, PortalLaneCarrierRecord, PortalLaneCarrierSource, PortalLaneStop
from app.portal import service as portal_service
from app.portal.schemas import LaneCreateRequest, EquipmentType

# ── Lane details (from email screenshot) ─────────────────────────────────────
LANE = dict(
    origin_city="Ripon",
    origin_state="CA",
    origin_zip="95366",
    destination_city="Reno",
    destination_state="NV",
    destination_zip="89502",
    equipment_type=EquipmentType.dry_van,
    pickup_date=date(2026, 6, 23),
    notes="We have 3 loads scheduled for today: 7:00 PM Pickup, 10:00 PM Pickup, 11:00 PM Pickup,",
    include_internal=False,
    include_dat=True,
    include_crr_model=False,
)

# ── Parsed rows: (carrier_name, email, phone, mc_number, source_notes) ───────
# Priority applied: Comments > Post Details > FMCSA > listing header
# Comments email/phone = highest priority even if Post Details differs
#
# DAT Trucks.txt
TRUCK_POSTINGS_ROWS = [
    # Sabr Cargo Inc (1h Sparks NV) — Comments: blank, PostDetails: (224) 335-9023 phone, FMCSA email: dispatch@sabrcargo.com
    ("Sabr Cargo Inc",
     "dispatch@sabrcargo.com", "(224) 335-9023", "1176151",
     "email:FMCSA; phone:PostDetails; no Comments contact"),

    # Orest Express Inc — Comments: dispatch@orestexpress.com → first priority
    ("Orest Express Inc/Orest Logistics Inc",
     "dispatch@orestexpress.com", "(630) 376-6373", "",
     "email:Comments; phone:PostDetails; no FMCSA block"),

    # ALPHA GEARS LLC — Comments: blank, PostDetails: phone, FMCSA email+phone
    ("ALPHA GEARS LLC",
     "alphagearsllc1@gmail.com", "(559) 705-8713", "1693636",
     "email:FMCSA; phone:PostDetails; no Comments contact"),

    # GREAT PACIFIC LOGISTICS — Comments: blank, PostDetails: email 6813700@gmail.com, FMCSA phone
    ("GREAT PACIFIC LOGISTICS INC",
     "6813700@gmail.com", "(916) 681-3700", "807812",
     "email:PostDetails; phone:FMCSA; no Comments contact"),

    # Max Freight Inc — Comments: "email only: s.prykhodko@maxfreight.us" → first priority
    ("Max Freight Inc",
     "s.prykhodko@maxfreight.us", "", "619736",
     "email:Comments; no FMCSA phone; no Comments phone"),

    # Raptors Line Haul — Comments: "TEAM EMPTY NOW..." (no contact), PostDetails: email
    ("Raptors Line Haul Inc",
     "info@raptorslh.com", "", "978615",
     "email:PostDetails; no Comments contact; no FMCSA phone"),

    # Usko Express Inc — merged: email posting (msydorenko, Sacramento) wins over phone-only (Sparks)
    # Comments on email posting: "$1m cargo..." (no contact), PostDetails: email
    ("Usko Express Inc",
     "msydorenko@uskoinc.com", "", "563453",
     "email:PostDetails; no Comments contact; no FMCSA phone"),

    # Dnm Transport Llc — Comments: "Email:dnmtransport08@gmail.com" → first priority
    ("Dnm Transport Llc",
     "dnmtransport08@gmail.com", "(626) 376-1777", "76401",
     "email:Comments; phone:PostDetails; no FMCSA"),

    # Hills Freight LLC — Comments: "MIDWEST" (no contact), PostDetails: phone, no FMCSA
    ("Hills Freight LLC",
     "", "(775) 344-9888 x331", "375557",
     "phone:PostDetails; no Comments contact; no FMCSA"),

    # Harminder Pal Singh — Comments: blank, PostDetails: phone, no FMCSA
    ("Harminder Pal Singh",
     "", "(510) 715-6799", "835494",
     "phone:PostDetails; no Comments contact; no FMCSA"),

    # T ORTEGA TRUCKING — Comments: blank, PostDetails: phone, FMCSA email (from 22h Fresno posting)
    ("T ORTEGA TRUCKING",
     "tortegatrucking@gmail.com", "(559) 217-4401", "1233497",
     "email:FMCSA; phone:PostDetails; no Comments contact"),

    # Punia Freight Line Inc — Comments: blank, PostDetails: phone, FMCSA email+phone
    ("Punia Freight Line Inc",
     "puniafreight@gmail.com", "(209) 707-5758", "1049986",
     "email:FMCSA; phone:PostDetails; no Comments contact"),

    # Ssl Trucking — Comments: blank, PostDetails: phone, no FMCSA
    ("Ssl Trucking",
     "", "(916) 410-7803", "995033",
     "phone:PostDetails; no Comments contact; no FMCSA"),

    # United Transportation Inc — Comments: blank, PostDetails: phone, no FMCSA
    ("United Transportation Inc",
     "", "(209) 817-2124", "869360",
     "phone:PostDetails; no Comments contact; no FMCSA"),

    # JET FREIGHT SERVICES INC — Comments: blank, PostDetails: email, no FMCSA
    ("JET FREIGHT SERVICES INC",
     "emma@jetfreightservices.com", "", "950611",
     "email:PostDetails; no Comments contact; no FMCSA"),

    # Allen Distribution — Comments: blank, PostDetails: email, no FMCSA records
    ("Allen Distribution",
     "tsooy@allendistribution.com", "", "",
     "email:PostDetails; no Comments contact; no DAT/FMCSA records"),

    # Mander Trucking Inc — Comments: blank, PostDetails: phone, no FMCSA
    ("Mander Trucking Inc",
     "", "(559) 442-0500", "314204",
     "phone:PostDetails; no Comments contact; no FMCSA"),

    # MIM EXPRESS INC — Comments: blank, PostDetails: phone, no FMCSA
    ("MIM EXPRESS INC",
     "", "(847) 984-0100", "768103",
     "phone:PostDetails; no Comments contact; no FMCSA"),

    # Sunset Pacific — Comments: blank, PostDetails: phone, FMCSA email
    ("Sunset Pacific Transport/Sunset Pacific Logistics",
     "maria@sunsetpacific.com", "(909) 464-1677 x1016", "230428",
     "email:FMCSA; phone:PostDetails; no Comments contact"),

    # Cheema Bros Express — Comments: blank, PostDetails: phone, no FMCSA
    ("Cheema Bros Express",
     "", "(209) 941-0481", "819841",
     "phone:PostDetails; no Comments contact; no FMCSA"),

    # DC Transport — Comments: "Email: dispatch@dctransport.biz" → first priority
    ("DC Transport",
     "dispatch@dctransport.biz", "(682) 310-7330", "427093",
     "email:Comments; phone:PostDetails; no FMCSA on truck posting"),

    # JBC Logistics — Comments: "...email- liz@jbclogisitcsinc.com" → first priority
    ("JBC Logistics Inc/JBC Trucking LLC",
     "liz@jbclogisitcsinc.com", "(775) 460-2197", "855362",
     "email:Comments; phone:PostDetails; no FMCSA on truck posting"),

    # Plus Tranz Inc — Comments: blank, PostDetails: phone, no FMCSA
    ("Plus Tranz Inc",
     "", "(512) 645-9274", "891549",
     "phone:PostDetails; no Comments contact; no FMCSA"),

    # T3RA FREIGHTWAYS — Comments: blank, PostDetails: phone, no FMCSA
    ("T3RA FREIGHTWAYS",
     "", "(916) 345-4200", "1362237",
     "phone:PostDetails; no Comments contact; no FMCSA"),
]

# lanemakerdat.txt — no Comments section in LaneMakers format
# Priority: FMCSA email (line 2 after Safety Rating) > FMCSA phone (line 1) else listing phone
LANEMAKERS_ROWS = [
    ("JBC Logistics Inc/JBC Trucking LLC", "jbctruckingllc@hotmail.com",      "(775) 830-1675",  "855362",  "email:FMCSA; phone:FMCSA"),
    ("Sg Trans Inc",                       "sgtransinc@yahoo.com",            "(916) 437-9069",  "678078",  "email:FMCSA; phone:listing (FMCSA absent)"),
    ("Laser Freight Inc",                  "whitecap1369@yahoo.com",          "(209) 740-1575",  "985801",  "email:FMCSA; phone:FMCSA"),
    ("Star Freight Services/Star Logistics","erenshaw@starfs.com",            "(775) 335-0199",  "405789",  "email:FMCSA; phone:FMCSA"),
    ("River City Transport Inc",           "admin@rivercitytrans.com",        "(916) 899-5515",  "579975",  "email:FMCSA; phone:FMCSA"),
    ("Virk Transport",                     "virktransport@yahoo.com",         "(510) 295-7009",  "728844",  "email:FMCSA; phone:FMCSA"),
    ("All The Way Transport",              "info@allthewaycorp.com",          "(916) 837-7626",  "931554",  "email:FMCSA; phone:listing (FMCSA absent)"),
    ("Altex Transportation Inc",           "safety@altextransportation.com",  "(916) 372-8402",  "498498",  "email:FMCSA; phone:FMCSA"),
    ("Seymon Trucking Inc",                "saimond1612@yahoo.com",           "(209) 204-4398",  "530780",  "email:FMCSA; phone:FMCSA"),
    ("Dulai Pride Inc",                    "info@dulaipride.com",             "(209) 451-0678",  "359527",  "email:FMCSA; phone:FMCSA"),
    ("DC Transport",                       "admin@dctransport.biz",           "(682) 310-7300",  "427093",  "email:FMCSA; phone:FMCSA"),
    ("MAXFREIGHT LOGISTICS LLC",           "info@maxfreightlogistics.us",     "(414) 530-1676",  "1558158", "email:FMCSA; phone:FMCSA"),
    ("Mack Truck Lines Llc",               "mackvirk@gmail.com",              "(916) 996-5573",  "717073",  "email:FMCSA; phone:FMCSA"),
    ("Love Transport Inc",                 "lticalifornia@gmail.com",         "(209) 612-3738",  "1015829", "email:FMCSA; phone:FMCSA"),
    ("Alfa Transport Inc",                 "alfaontime@gmail.com",            "(916) 717-5261",  "751664",  "email:FMCSA; phone:FMCSA"),
    ("IM TRANZ INC",                       "i_m_trucking@hotmail.com",        "(916) 586-5043",  "922411",  "email:FMCSA; phone:FMCSA"),
    ("GOLDEN GLOBE TRANSPORT CORP",        "goldengtc20@gmail.com",           "(916) 496-5998",  "1124062", "email:FMCSA; phone:FMCSA"),
    ("Bal Trans",                          "bal.trans@yahoo.com",             "(209) 331-3307",  "572664",  "email:FMCSA; phone:FMCSA"),
    ("SJS Logistics Inc",                  "sjstrucking2006@yahoo.com",       "(209) 665-5988",  "650812",  "email:FMCSA; phone:listing (FMCSA absent)"),
    ("DM Express Inc",                     "davyd@dmexpress.org",             "(916) 300-7448",  "1343273", "email:FMCSA; phone:FMCSA"),
    ("RAMAN SINGH",                        "info@cargoxtransport.com",        "(415) 909-9174",  "1011517", "email:FMCSA; phone:FMCSA"),
    ("DELTA ROADWAY LLC",                  "rbsf27@yahoo.com",                "(415) 699-0042",  "839862",  "email:FMCSA; phone:listing (FMCSA absent)"),
    ("PEARL VALLEY TRANSPORT LLC",         "pearlvalleytransport786@gmail.com","(916) 879-9669", "1387955", "email:FMCSA; phone:FMCSA"),
    ("RTS Express Inc",                    "dispatch@rtsexpressinc.com",      "(209) 757-4040",  "918464",  "email:FMCSA; phone:FMCSA"),
    ("TNT FREIGHT TRANSPORT LLC",          "mstangie8325@gmail.com",          "(314) 504-9728",  "1242908", "email:FMCSA; phone:FMCSA"),
    ("FERRAGUT",                           "yoandypc@hotmail.com",            "(956) 404-9163",  "1326415", "email:FMCSA; phone:FMCSA"),
    ("Sunview Logistics Inc",              "manpreet@sunviewlogistics.com",   "(209) 636-9031",  "76218",   "email:FMCSA; phone:FMCSA"),
    ("Toor Express Inc",                   "suki_toor@yahoo.com",             "(916) 333-9713",  "590874",  "email:FMCSA; phone:FMCSA"),
    ("FASTWAY TRUCKING LLC",               "fwaytruck@gmail.com",             "(865) 210-9084",  "1643130", "email:FMCSA; phone:FMCSA"),
]


def _dedup(rows: list[tuple]) -> list[tuple]:
    """Collapse by MC# (prefer row with email). No MC# → key by carrier_name."""
    best: dict[str, tuple] = {}
    for row in rows:
        carrier_name, email, phone, mc_number, source_notes = row
        key = mc_number.strip() if mc_number.strip() else carrier_name.strip().lower()
        if not key:
            continue
        existing = best.get(key)
        if existing is None:
            best[key] = row
        elif email and not existing[1]:
            best[key] = row
    return list(best.values())


def main() -> None:
    lane_id: uuid.UUID | None = None
    if len(sys.argv) > 1:
        lane_id = uuid.UUID(sys.argv[1])

    all_rows = _dedup(TRUCK_POSTINGS_ROWS + LANEMAKERS_ROWS)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with session_scope() as db:
        if lane_id is None:
            req = LaneCreateRequest.model_validate(LANE)
            lane = portal_service.create_lane(db, req)
            lane_id = lane.id
            print(f"Created lane: {lane_id}")
        else:
            lane = db.query(PortalLane).filter_by(id=lane_id).first()
            if lane is None:
                print(f"ERROR: lane {lane_id} not found")
                sys.exit(1)
            print(f"Using existing lane: {lane_id}")

        source_id = uuid.uuid4()
        db.add(PortalLaneCarrierSource(
            id=source_id,
            lane_id=lane_id,
            source_type="dat",
            raw_payload='{"note":"manually injected — LLM API down 2026-06-24"}',
            parsed_count=len(all_rows),
            status="ok",
            created_at=now,
        ))
        db.flush()

        emails = 0
        for carrier_name, email, phone, mc_number, source_notes in all_rows:
            db.add(PortalLaneCarrierRecord(
                id=uuid.uuid4(),
                lane_id=lane_id,
                source_id=source_id,
                source_type="dat",
                carrier_name=carrier_name,
                email=email,
                phone=phone,
                mc_number=mc_number,
                source_notes=source_notes,
                created_at=now,
            ))
            if email:
                emails += 1

        db.commit()

    print(f"Injected {len(all_rows)} DAT carriers ({emails} with email) into lane {lane_id}")
    print(f"\nLane ID: {lane_id}")


if __name__ == "__main__":
    main()
