import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

# =========================================================
# CLEAN DOT
# =========================================================
def clean_dot(x):

    if pd.isna(x):
        return None

    x = str(x).strip().replace(".0", "").lstrip("0")

    return x if x != "" else None


# =========================================================
# LOAD MANUAL DESCRIPTION MAPPING FILE
# =========================================================
mapping_df = pd.read_excel(DATA_DIR / "final_equipment_mapping.xlsx")

# clean
mapping_df["DESCRIPTION"] = (
    mapping_df["DESCRIPTION"]
    .astype(str)
    .str.lower()
    .str.strip()
)

mapping_df["CATEGORY"] = (
    mapping_df["CATEGORY"]
    .astype(str)
    .str.lower()
    .str.strip()
)

# create lookup dictionary
desc_to_equipment = dict(
    zip(
        mapping_df["DESCRIPTION"],
        mapping_df["CATEGORY"]
    )
)


# =========================================================
# CARGO → EQUIPMENT MAPPING
# =========================================================
CARGO_EQUIPMENT_MAP = {

    # Reefer
    "CRGO_COLDFOOD": "reefer",
    "CRGO_MEAT": "reefer",
    "CRGO_PRODUCE": "reefer",
    "CRGO_BEVERAGES": "reefer",

    # Tanker
    "CRGO_LIQGAS": "tanker",
    "CRGO_CHEM": "tanker",
    "CRGO_OILFIELD": "tanker",

    # Flatbed
    "CRGO_METALSHEET": "flatbed",
    "CRGO_LOGPOLE": "flatbed",
    "CRGO_BLDGMAT": "flatbed",
    "CRGO_MACHLRG": "flatbed",
    "CRGO_CONSTRUCT": "flatbed",

    # Dry Van
    "CRGO_GENFREIGHT": "dry_van",
    "CRGO_PAPERPROD": "dry_van",
    "CRGO_INTERMODAL": "dry_van",

    # Added Dry Van
    "CRGO_HOUSEHOLD": "dry_van",
    "CRGO_USMAIL": "dry_van",
    "CRGO_FARMSUPP": "dry_van",

    # Bulk
    "CRGO_GRAINFEED": "bulk",
    "CRGO_DRYBULK": "bulk",
    "CRGO_COALCOKE": "bulk",

    # Specialized
    "CRGO_MOTOVEH": "car_hauler",
    "CRGO_DRIVETOW": "car_hauler",
    "CRGO_LIVESTOCK": "livestock",
    "CRGO_GARBAGE": "refuse"
}


# =========================================================
# COLUMNS NEEDED
# =========================================================
usecols = [
    "DOT_NUMBER",
    "LEGAL_NAME",
    "STATUS_CODE",
    "CRGO_CARGOOTHR_DESC"
] + list(CARGO_EQUIPMENT_MAP.keys())


# =========================================================
# SETTINGS
# =========================================================
chunksize = 100000

output_file = DATA_DIR / "carrier_equipment_active_new.csv"

chunk_count = 0
total_rows = 0
total_active = 0

writer_started = False


# =========================================================
# EQUIPMENT FUNCTION
# =========================================================
def get_equipment(row):

    equipment = set()

    # -------------------------------------
    # 1. STRUCTURED CARGO COLUMNS
    # -------------------------------------
    for col, eq in CARGO_EQUIPMENT_MAP.items():

        if str(row[col]).strip().upper() == "X":
            equipment.add(eq)

    # -------------------------------------
    # 2. DESCRIPTION COLUMN
    # -------------------------------------
    desc = str(
        row.get("CRGO_CARGOOTHR_DESC", "")
    ).lower().strip()

    if desc in desc_to_equipment:

        mapped_eq = desc_to_equipment[desc]

        # ignore noisy categories
        if mapped_eq not in ["ignore", "specialized"]:

            equipment.add(mapped_eq)

    # -------------------------------------
    # FINAL
    # -------------------------------------
    return ", ".join(sorted(equipment)) if equipment else "unknown"


# =========================================================
# READ IN CHUNKS
# =========================================================
for chunk in pd.read_csv(
    DATA_DIR / "Company_Census_File.csv",
    usecols=usecols,
    chunksize=chunksize,
    on_bad_lines="skip",
    engine="python"
):

    chunk_count += 1
    total_rows += len(chunk)

    # -------------------------------------
    # CLEAN DOT
    # -------------------------------------
    chunk["DOT_NUMBER"] = chunk["DOT_NUMBER"].apply(clean_dot)

    chunk = chunk[
        chunk["DOT_NUMBER"].notna()
    ]

    # -------------------------------------
    # FILTER ACTIVE
    # -------------------------------------
    chunk = chunk[
        chunk["STATUS_CODE"] == "A"
    ]

    total_active += len(chunk)

    # -------------------------------------
    # APPLY EQUIPMENT LOGIC
    # -------------------------------------
    chunk["EQUIPMENT_TYPES"] = chunk.apply(
        get_equipment,
        axis=1
    )

    # -------------------------------------
    # FLAG COLUMNS
    # -------------------------------------
    chunk["EQUIPMENT_TYPES"] = (
        chunk["EQUIPMENT_TYPES"]
        .str.lower()
        .fillna("")
    )

    chunk["DRY_VAN"] = (
        chunk["EQUIPMENT_TYPES"]
        .str.contains(r"\bdry_van\b")
        .astype(int)
    )

    chunk["REEFER"] = (
        chunk["EQUIPMENT_TYPES"]
        .str.contains(r"\breefer\b")
        .astype(int)
    )

    chunk["FLATBED"] = (
        chunk["EQUIPMENT_TYPES"]
        .str.contains(r"\bflatbed\b")
        .astype(int)
    )

    # -------------------------------------
    # FINAL OUTPUT
    # -------------------------------------
    final_chunk = chunk[
        [
            "DOT_NUMBER",
            "LEGAL_NAME",
            "CRGO_CARGOOTHR_DESC",
            "EQUIPMENT_TYPES",
            "DRY_VAN",
            "REEFER",
            "FLATBED"
        ]
    ]

    # -------------------------------------
    # WRITE CSV
    # -------------------------------------
    if not writer_started:

        final_chunk.to_csv(
            output_file,
            index=False,
            mode="w"
        )

        writer_started = True

    else:

        final_chunk.to_csv(
            output_file,
            index=False,
            mode="a",
            header=False
        )

    # -------------------------------------
    # PROGRESS
    # -------------------------------------
    # print(
    #     f"✅ Chunk {chunk_count} | "
    #     f"Rows: {total_rows:,} | "
    #     f"Active: {total_active:,}"
    # )


# =========================================================
# FINAL SUMMARY
# =========================================================
# print("\n🎯 DONE!")

# print(f"📊 Total Rows Processed : {total_rows:,}")
# print(f"✅ Total Active Rows    : {total_active:,}")
# print(f"💾 File Saved As        : {output_file}")