"""
Precompute for Model 1 — FreightX historical lane dataset.

Reads shipment_level_clean.csv and builds an indexed parquet
grouped by (SRC_ZIP, DEST_ZIP, EQUIPMENT) for O(1) lookup at request time.
"""

import pandas as pd
from pathlib import Path

import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import clean_dot, clean_zip


MODELS_DIR = Path(__file__).resolve().parent       # src/api/models/
PRECOMPUTE_DIR = MODELS_DIR / "precomputed_model1"
PRECOMPUTE_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = MODELS_DIR.parent.parent.parent / "data"  # FreightX/data/


def run():
    print("=" * 60)
    print("PRECOMPUTE MODEL 1: FreightX Historical Lane Index")
    print("=" * 60)

    csv_path = DATA_DIR / "shipment_level_clean.csv"
    print(f"Loading {csv_path} ...")

    df = pd.read_csv(csv_path, dtype=str)
    print(f"  Raw rows: {len(df):,}")

    # --------------------------------------------------
    # CLEAN KEY COLUMNS
    # --------------------------------------------------
    df["DOT"] = df["DOT"].apply(clean_dot)
    df["SRC_ZIP"] = df["SRC_ZIP"].apply(clean_zip)
    df["DEST_ZIP"] = df["DEST_ZIP"].apply(clean_zip)

    # Normalize equipment strings for consistent matching
    df["EQUIPMENT"] = df["EQUIPMENT"].str.strip().str.upper()

    df = df.dropna(subset=["DOT", "SRC_ZIP", "DEST_ZIP", "EQUIPMENT"])
    print(f"  After cleaning: {len(df):,}")

    # --------------------------------------------------
    # SAVE INDEXED PARQUET
    # --------------------------------------------------
    # Sort by the lookup keys for efficient filtering
    df = df.sort_values(["SRC_ZIP", "DEST_ZIP", "EQUIPMENT", "DOT"]).reset_index(drop=True)
    df.to_parquet(PRECOMPUTE_DIR / "freightx_shipments.parquet", index=False)
    print(f"  Saved freightx_shipments.parquet: {len(df):,} rows")

    # --------------------------------------------------
    # BUILD FAST LOOKUP INDEX
    # Group unique DOTs by (SRC_ZIP, DEST_ZIP, EQUIPMENT)
    # --------------------------------------------------
    lookup = (
        df.groupby(["SRC_ZIP", "DEST_ZIP", "EQUIPMENT"])["DOT"]
        .apply(lambda x: list(x.unique()))
        .reset_index()
        .rename(columns={"DOT": "DOT_LIST"})
    )
    lookup.to_parquet(PRECOMPUTE_DIR / "freightx_lookup.parquet", index=False)
    print(f"  Saved freightx_lookup.parquet: {len(lookup):,} groups")

    print("=" * 60)
    print("MODEL 1 PRECOMPUTE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run()
