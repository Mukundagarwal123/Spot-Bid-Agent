"""
Model 2 — Pure HQ proximity (no lane-specific tail filters).

Rank carriers primarily by HQ proximity to origin, with INSP_COUNT
and TOTAL_INSP_COUNT as tie-breakers.

Sort keys: ['HQ_PROXIMITY_FROM_SRC', 'INSP_COUNT', 'TOTAL_INSP_COUNT']

Filters:
    - All basic global filters (via precomputed valid_dots)
    - >=350 miles: route-county restriction
    - <350 miles: keep full carrier universe
    - NO lane-specific tail filters (unlike models 3-5)
"""

import pandas as pd
import numpy as np
from pathlib import Path

from models.helpers import haversine, scale_to_5, apply_equipment_filter


# --------------------------------------------------
# LOAD PRECOMPUTED DATA
# --------------------------------------------------
def load_precomputed(precompute_dir="precomputed_model2"):
    models_dir = Path(__file__).resolve().parent  # src/api/models/
    pdir = models_dir / precompute_dir
    data = {
        "carrier_base": pd.read_parquet(pdir / "carrier_base.parquet"),
        "valid_dots": set(pd.read_parquet(pdir / "valid_dots.parquet")["DOT_NUMBER"]),
        "hq_lookup": pd.read_parquet(pdir / "hq_lookup.parquet"),
        "insp_per_dot": pd.read_parquet(pdir / "insp_per_dot.parquet"),
        "county_count_per_dot": pd.read_parquet(pdir / "county_count_per_dot.parquet"),
        "total_states_per_dot": pd.read_parquet(pdir / "total_states_per_dot.parquet"),
        "equipment_df": pd.read_parquet(pdir / "equipment.parquet"),
    }
    print(f"Model 2: loaded precomputed data, {len(data['valid_dots']):,} valid carriers")
    return data


# --------------------------------------------------
# MAIN MODEL RUNNER
# --------------------------------------------------
def run_my_model(source_zip, dest_zip, equipment_list=None,
                 lane_ctx=None, precomputed=None):
    """
    Args:
        source_zip, dest_zip: zip codes
        equipment_list: UI equipment filter
        lane_ctx: LaneContext object (injected by combiner)
        precomputed: dict of preloaded DataFrames (injected by combiner)
    """
    if precomputed is None:
        precomputed = load_precomputed()

    if lane_ctx is None:
        from models.lane_context import build_lane_context
        models_dir = Path(__file__).resolve().parent
        uszips = pd.read_parquet(models_dir / "precomputed_model2" / "uszips.parquet")
        lane_ctx = build_lane_context(source_zip, dest_zip, uszips)

    print("=" * 40)
    print("MODEL 2: Pure HQ Proximity")
    print("=" * 40)

    carrier_base = precomputed["carrier_base"][
        precomputed["carrier_base"]["DOT_NUMBER"].isin(precomputed["valid_dots"])
    ].copy()

    # --------------------------------------------------
    # ROUTE COUNTY FILTERING (conditional on >=350 miles)
    # --------------------------------------------------
    route_carrier_base = carrier_base[
        carrier_base["STATE_COUNTY_CODE"].isin(lane_ctx.route_codes)
    ].copy()

    if lane_ctx.lane_miles >= 350:
        carrier_base = route_carrier_base.copy()
        print(f"  Lane >=350mi → restricted to route counties")
    else:
        print(f"  Lane <350mi → all valid carriers kept: {carrier_base['DOT_NUMBER'].nunique():,}")

    # --------------------------------------------------
    # COUNTY ENTROPY (global filter: entropy >= 2.5)
    # --------------------------------------------------
    county_dist = route_carrier_base.copy()
    county_dist["CARRIER_TOTAL_ROUTE_INSP"] = (
        county_dist.groupby("DOT_NUMBER")["INSP_COUNT"].transform("sum")
    )
    county_dist["COUNTY_INSP_FRACTION"] = (
        county_dist["INSP_COUNT"] / county_dist["CARRIER_TOTAL_ROUTE_INSP"]
    )
    entropy_df = (
        county_dist.groupby("DOT_NUMBER")["COUNTY_INSP_FRACTION"]
        .apply(lambda x: -(x * np.log(x)).sum())
        .reset_index()
        .rename(columns={"COUNTY_INSP_FRACTION": "COUNTY_ENTROPY"})
    )

    # --------------------------------------------------
    # SCORE AGGREGATION
    # --------------------------------------------------
    score_df = (
        route_carrier_base.groupby("DOT_NUMBER")
        .agg({"INSP_COUNT": "sum", "STATE_COUNTY_CODE": "nunique"})
        .reset_index()
        .rename(columns={"STATE_COUNTY_CODE": "COUNTIES_WITH_INSP_ON_ROUTE"})
    )

    score_df = score_df.merge(entropy_df, on="DOT_NUMBER", how="left")
    score_df = score_df[score_df["COUNTY_ENTROPY"] >= 1].copy()
    print(f"  Entropy filter (>=1): {len(score_df):,} carriers remain")

    score_df = score_df.merge(
        precomputed["insp_per_dot"][["DOT_NUMBER", "TOTAL_INSP_COUNT"]],
        on="DOT_NUMBER", how="left",
    )
    score_df = score_df.merge(precomputed["county_count_per_dot"], on="DOT_NUMBER", how="left")
    score_df = score_df.merge(precomputed["total_states_per_dot"], on="DOT_NUMBER", how="left")

    # --------------------------------------------------
    # HQ DISTANCE
    # --------------------------------------------------
    score_df = score_df.merge(
        precomputed["hq_lookup"][["DOT_NUMBER", "HQ_LAT", "HQ_LON"]],
        on="DOT_NUMBER", how="left",
    )
    score_df["SRC_TO_HQ_DIST"] = haversine(
        score_df["HQ_LAT"].values, score_df["HQ_LON"].values,
        lane_ctx.src_lat, lane_ctx.src_lon,
    )
    score_df["HQ_TO_DEST_DIST"] = haversine(
        score_df["HQ_LAT"].values, score_df["HQ_LON"].values,
        lane_ctx.dst_lat, lane_ctx.dst_lon,
    )
    score_df["SRC_TO_HQ_DIST"] = score_df["SRC_TO_HQ_DIST"].fillna(99999)
    score_df["HQ_TO_DEST_DIST"] = score_df["HQ_TO_DEST_DIST"].fillna(99999)

    score_df["INSP_COUNT"] = pd.to_numeric(score_df["INSP_COUNT"], errors="coerce").fillna(0)
    score_df["TOTAL_INSP_COUNT"] = pd.to_numeric(score_df["TOTAL_INSP_COUNT"], errors="coerce")

    # --------------------------------------------------
    # SORT: Pure HQ proximity, no tail filters
    # --------------------------------------------------
    score_df = score_df.sort_values(
        ["SRC_TO_HQ_DIST", "INSP_COUNT", "TOTAL_INSP_COUNT"],
        ascending=[True, False, False],
    ).reset_index(drop=True)

    numeric_cols = score_df.select_dtypes(include="number").columns
    score_df[numeric_cols] = score_df[numeric_cols].fillna(0)

    # --------------------------------------------------
    # EQUIPMENT MERGE + FILTER
    # --------------------------------------------------
    score_df["DOT_NUMBER"] = score_df["DOT_NUMBER"].astype(str)
    score_df = score_df.merge(precomputed["equipment_df"], on="DOT_NUMBER", how="left")
    score_df = apply_equipment_filter(score_df, equipment_list)

    # --------------------------------------------------
    # RENAME + SCALE
    # --------------------------------------------------
    score_df = score_df.rename(columns={
        "SRC_TO_HQ_DIST": "HQ_PROXIMITY",
        "INSP_COUNT": "LANE_INSP",
        "TOTAL_INSP_COUNT": "NATIONWIDE_INSP",
    })

    score_df["HQ_PROXIMITY"] = scale_to_5(score_df["HQ_PROXIMITY"].max() - score_df["HQ_PROXIMITY"])
    score_df["LANE_INSP"] = scale_to_5(score_df["LANE_INSP"])
    score_df["NATIONWIDE_INSP"] = scale_to_5(score_df["NATIONWIDE_INSP"])

    final_cols = ["DOT_NUMBER", "HQ_PROXIMITY", "LANE_INSP", "NATIONWIDE_INSP"]
    score_df = score_df[final_cols]

    print(f"  Model 2 complete: {len(score_df):,} carriers")
    return score_df
