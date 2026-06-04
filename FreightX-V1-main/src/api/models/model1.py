"""
Model 1 — FreightX historical lane dataset ("T3ra" / lane memory).

If this lane already exists in FreightX historical shipment data,
return the DOTs that actually hauled it via exact match on
(source_zip, dest_zip, equipment).

This model does NOT depend on FMCSA inspection data or Trimble route
geometry — it's a pure historical lookup.
"""

import pandas as pd
from pathlib import Path

from models.helpers import clean_zip, EQUIPMENT_MAP


# --------------------------------------------------
# EQUIPMENT NORMALIZATION
# FreightX EQUIPMENT strings → standard names used in matching
# --------------------------------------------------
FX_EQUIPMENT_NORMALIZE = {
    "DRY VAN": "DRY_VAN",
    "DRY_VAN": "DRY_VAN",
    "DRYVAN": "DRY_VAN",
    "REEFER": "REEFER",
    "FLATBED": "FLATBED",
    "FLAT BED": "FLATBED",
    "VAN": "DRY_VAN",
}

UI_TO_FX = {
    "dryvan": "DRY_VAN",
    "reefer": "REEFER",
    "flatbed": "FLATBED",
}


# --------------------------------------------------
# LOAD PRECOMPUTED DATA
# --------------------------------------------------
def load_precomputed(precompute_dir="precomputed_model1"):
    models_dir = Path(__file__).resolve().parent  # src/api/models/
    pdir = models_dir / precompute_dir
    shipments = pd.read_parquet(pdir / "freightx_shipments.parquet")
    print(f"Model 1: loaded {len(shipments):,} shipment rows")
    return shipments


# --------------------------------------------------
# MAIN MODEL RUNNER
# --------------------------------------------------
def run_my_model(source_zip, dest_zip, equipment_list=None, shipments_df=None):
    """
    Exact match on (SRC_ZIP, DEST_ZIP, EQUIPMENT).

    Args:
        source_zip: origin zip code
        dest_zip: destination zip code
        equipment_list: list of equipment types from UI (e.g. ["dryvan", "reefer"])
        shipments_df: preloaded FreightX shipments DataFrame (injected by combiner)

    Returns:
        DataFrame with DOT_NUMBER column (+ any available metadata)
    """
    if shipments_df is None:
        shipments_df = load_precomputed()

    src = clean_zip(source_zip)
    dst = clean_zip(dest_zip)

    print(f"Model 1: searching FreightX for {src} → {dst}")

    # Filter by exact zip match
    matches = shipments_df[
        (shipments_df["SRC_ZIP"] == src) & (shipments_df["DEST_ZIP"] == dst)
    ].copy()

    # Filter by equipment if specified
    if equipment_list:
        fx_equip = [UI_TO_FX[eq] for eq in equipment_list if eq in UI_TO_FX]
        if fx_equip:
            # Normalize FreightX equipment column for matching
            matches["_NORM_EQUIP"] = matches["EQUIPMENT"].map(FX_EQUIPMENT_NORMALIZE).fillna(matches["EQUIPMENT"])
            matches = matches[matches["_NORM_EQUIP"].isin(fx_equip)]
            matches = matches.drop(columns=["_NORM_EQUIP"])

    if len(matches) == 0:
        print("Model 1: no historical matches found")
        return pd.DataFrame(columns=["DOT_NUMBER"])

    # Deduplicate by DOT
    result = matches.drop_duplicates(subset=["DOT"]).copy()
    result = result.rename(columns={"DOT": "DOT_NUMBER"})

    # Keep relevant columns
    keep_cols = ["DOT_NUMBER"]
    for col in ["MC", "HQ_CITY", "HQ_STATE", "HQ_ZIP"]:
        if col in result.columns:
            keep_cols.append(col)

    result = result[keep_cols].reset_index(drop=True)

    print(f"Model 1: {len(result):,} carriers from FreightX history")
    return result
