"""
Precompute enrichment parquet from df_output_with_inspections1.csv.

Reads the CSV, cleans DOT_NUMBER, keeps only the required enrichment
columns (EMAIL_ADDRESS, PHONE, DOCKET_NUMBER, etc.), deduplicates by
DOT_NUMBER, and saves a fast-loading parquet inside models/precomputed_shared/.
"""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import clean_dot


MODELS_DIR = Path(__file__).resolve().parent           # src/api/models/
API_DIR = MODELS_DIR.parent                            # src/api/
DATA_DIR = API_DIR.parent.parent / "data"              # repo root / data/
PRECOMPUTE_DIR = MODELS_DIR / "precomputed_shared"
PRECOMPUTE_DIR.mkdir(parents=True, exist_ok=True)

ENRICHMENT_COLUMNS = [
    "DOT_NUMBER",
    "EMAIL_ADDRESS",
    "DOCKET_NUMBER",
    "PHONE",
    "CSA_PERCENTILE",
    "DF_PERCENTILE",
    "HOS_PERCENTILE",
    "UD_PERCENTILE",
    "VM_PERCENTILE"
]


def run(csv_filename="df_output_with_inspections1.csv", columns=None):
    if columns is None:
        columns = ENRICHMENT_COLUMNS

    print("=" * 60)
    print("PRECOMPUTE ENRICHMENT: df_output_with_inspections -> parquet")
    print("=" * 60)

    # --------------------------------------------------
    # FIND THE CSV (data/ is canonical; fall back to legacy locations)
    # --------------------------------------------------
    csv_path = DATA_DIR / csv_filename
    if not csv_path.exists():
        for alt in (API_DIR / csv_filename, MODELS_DIR / csv_filename):
            if alt.exists():
                csv_path = alt
                break
        else:
            print(f"ERROR: CSV not found in {DATA_DIR}, {API_DIR}, or {MODELS_DIR}")
            return

    print(f"Loading {csv_path} ...")
    df = pd.read_csv(csv_path, dtype={"DOT_NUMBER": str}, low_memory=False)
    print(f"  Raw rows: {len(df):,}")

    # --------------------------------------------------
    # CLEAN DOT
    # --------------------------------------------------
    df["DOT_NUMBER"] = df["DOT_NUMBER"].apply(clean_dot)
    print("  DOT cleaning done")

    # --------------------------------------------------
    # KEEP REQUIRED COLUMNS
    # --------------------------------------------------
    available_cols = [c for c in columns if c in df.columns]
    missing_cols = [c for c in columns if c not in df.columns]
    if missing_cols:
        print(f"  WARNING: columns not found in CSV: {missing_cols}")

    df = df[available_cols]

    # --------------------------------------------------
    # REMOVE NULL DOTS
    # --------------------------------------------------
    df = df[df["DOT_NUMBER"].notna()]
    print(f"  After null DOT removal: {len(df):,}")

    # --------------------------------------------------
    # REMOVE ROWS WITH NULL EMAIL
    # --------------------------------------------------
    if "EMAIL_ADDRESS" in df.columns:
        df = df.dropna(subset=["EMAIL_ADDRESS"])
        print(f"  After null email removal: {len(df):,}")

    # --------------------------------------------------
    # DEDUP: keep first row per DOT
    # --------------------------------------------------
    df = df.drop_duplicates(subset="DOT_NUMBER", keep="first")
    print(f"  After dedup: {len(df):,}")

    # --------------------------------------------------
    # SAVE PARQUET
    # --------------------------------------------------
    out_path = PRECOMPUTE_DIR / "output_enrichment.parquet"
    df.to_parquet(out_path, index=False)

    print(f"\nSaved: {out_path}")
    print(f"  {len(df):,} rows, columns: {list(df.columns)}")
    print("=" * 60)
    print("ENRICHMENT PRECOMPUTE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run()
