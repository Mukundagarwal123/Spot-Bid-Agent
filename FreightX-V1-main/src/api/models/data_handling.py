import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

# ── LOAD ─────────────────────────────────────────────────────────────
print("Loading inspection file...")
df = pd.read_csv(DATA_DIR / "Vehicle_Inspection_File.csv", dtype=str)



print(f"Total rows loaded: {len(df):,}")

# ── CLEAN DOT_NUMBER ─────────────────────────────────────────────────
df["DOT_NUMBER"] = df["DOT_NUMBER"].astype(str).str.strip()

# remove garbage values
df = df[df["DOT_NUMBER"].notna()]
df = df[df["DOT_NUMBER"] != ""]
df = df[df["DOT_NUMBER"] != "nan"]

# ── CLEAN COUNTY COLUMNS (IMPORTANT) ─────────────────────────────────
df["COUNTY_CODE_STATE"] = df["COUNTY_CODE_STATE"].astype(str).str.strip()
df["COUNTY_CODE"] = df["COUNTY_CODE"].astype(str).str.strip().str.zfill(3)

df = df[df["COUNTY_CODE_STATE"].notna()]
df = df[df["COUNTY_CODE"].notna()]

# ── GROUP BY (CORE STEP) ─────────────────────────────────────────────
print("Grouping by DOT + COUNTY...")

insp_counts = (
    df.groupby(["DOT_NUMBER", "COUNTY_CODE_STATE", "COUNTY_CODE"])
      .size()
      .reset_index(name="INSP_COUNT")
)

print(f"Grouped rows (final): {len(insp_counts):,}")

# ── SANITY CHECK ─────────────────────────────────────────────────────
print("\nSample:")
print(insp_counts.head())

print("\nDistribution:")
print(insp_counts["INSP_COUNT"].describe())

# ── SAVE ─────────────────────────────────────────────────────────────
insp_counts.to_csv(DATA_DIR / "carrier_county_insp_counts.csv", index=False)

# print("\n✅ Saved → carrier_county_insp_counts.csv")
# print(f"Final shape: {insp_counts.shape}")