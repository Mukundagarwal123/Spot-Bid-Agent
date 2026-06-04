"""
Model 4 — Pure inspection count sorting + lane-specific tail filters.

Sort only by lane inspection count and total inspection count (nationwide),
with the same lane-specific tail as model 3.

Sort keys: ['INSP_COUNT', 'TOTAL_INSP_COUNT']

Filters:
    - All basic global filters
    - >=350 miles: route-county restriction
    - Lane-specific tail filters (same block as model 3)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from itertools import combinations

from models.helpers import haversine, scale_to_5, apply_equipment_filter
from models.model3 import apply_lane_tail_filters, compute_max_dist


# --------------------------------------------------
# LOAD PRECOMPUTED DATA
# --------------------------------------------------
def load_precomputed(precompute_dir="precomputed_model4"):
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
        "county_centroids": (
            pd.read_parquet(pdir / "county_centroids.parquet")
            .set_index("STATE_COUNTY_CODE")
            .to_dict("index")
        ),
    }
    print(f"Model 4: loaded precomputed data, {len(data['valid_dots']):,} valid carriers")
    return data


# --------------------------------------------------
# MAIN MODEL RUNNER
# --------------------------------------------------
def run_my_model(source_zip, dest_zip, equipment_list=None,
                 lane_ctx=None, precomputed=None):
    if precomputed is None:
        precomputed = load_precomputed()

    if lane_ctx is None:
        from models.lane_context import build_lane_context
        models_dir = Path(__file__).resolve().parent
        uszips = pd.read_parquet(models_dir / "precomputed_model4" / "uszips.parquet")
        lane_ctx = build_lane_context(source_zip, dest_zip, uszips)

    print("=" * 40)
    print("MODEL 4: Pure Inspection Count + Lane Tail Filters")
    print("=" * 40)

    carrier_base = precomputed["carrier_base"][
        precomputed["carrier_base"]["DOT_NUMBER"].isin(precomputed["valid_dots"])
    ].copy()

    # --------------------------------------------------
    # ROUTE COUNTY FILTERING (>=350 miles)
    # --------------------------------------------------
    route_carrier_base = carrier_base[
        carrier_base["STATE_COUNTY_CODE"].isin(lane_ctx.route_codes)
    ].copy()

    if lane_ctx.lane_miles >= 350:
        carrier_base = route_carrier_base.copy()
        print(f"  Lane >=350mi → restricted to route counties")
    else:
        print(f"  Lane <350mi → all carriers kept: {carrier_base['DOT_NUMBER'].nunique():,}")

    # --------------------------------------------------
    # MAX_DIST
    # --------------------------------------------------
    dist_df = compute_max_dist(route_carrier_base, lane_ctx.lane_miles, precomputed["county_centroids"])

    # --------------------------------------------------
    # SCORE AGGREGATION
    # --------------------------------------------------
    score_df = (
        route_carrier_base.groupby("DOT_NUMBER")
        .agg({"INSP_COUNT": "sum", "STATE_COUNTY_CODE": "nunique"})
        .reset_index()
        .rename(columns={"STATE_COUNTY_CODE": "COUNTIES_WITH_INSP_ON_ROUTE"})
    )
    score_df["LANE_MILES"] = lane_ctx.lane_miles
    score_df = score_df.merge(dist_df, on="DOT_NUMBER", how="left")
    score_df = score_df.merge(
        precomputed["insp_per_dot"][["DOT_NUMBER", "TOTAL_INSP_COUNT"]],
        on="DOT_NUMBER", how="left",
    )
    score_df = score_df.merge(precomputed["county_count_per_dot"], on="DOT_NUMBER", how="left")
    score_df = score_df.merge(precomputed["total_states_per_dot"], on="DOT_NUMBER", how="left")

    lane_states_per_dot = (
        route_carrier_base.groupby("DOT_NUMBER")["COUNTY_CODE_STATE"]
        .nunique().reset_index(name="LANE_STATES_WITH_INSPECTIONS")
    )
    score_df = score_df.merge(lane_states_per_dot, on="DOT_NUMBER", how="left")

    # --------------------------------------------------
    # HQ DISTANCE (for output, not primary sort)
    # --------------------------------------------------
    score_df = score_df.merge(
        precomputed["hq_lookup"][["DOT_NUMBER", "HQ_LAT", "HQ_LON"]],
        on="DOT_NUMBER", how="left",
    )
    score_df["SRC_TO_HQ_DIST"] = haversine(
        score_df["HQ_LAT"].values, score_df["HQ_LON"].values,
        lane_ctx.src_lat, lane_ctx.src_lon,
    )
    score_df["SRC_TO_HQ_DIST"] = score_df["SRC_TO_HQ_DIST"].fillna(99999)

    score_df["INSP_COUNT"] = pd.to_numeric(score_df["INSP_COUNT"], errors="coerce").fillna(0)
    score_df["TOTAL_INSP_COUNT"] = pd.to_numeric(score_df["TOTAL_INSP_COUNT"], errors="coerce")

    # --------------------------------------------------
    # LANE-SPECIFIC TAIL FILTERS + SORT
    # Sort: INSP_COUNT desc, TOTAL_INSP_COUNT desc
    # --------------------------------------------------
    score_df = apply_lane_tail_filters(
        score_df,
        lane_ctx.lane_miles,
        sort_keys=["INSP_COUNT", "TOTAL_INSP_COUNT"],
        sort_ascending=[False, False],
    )

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

    print(f"  Model 4 complete: {len(score_df):,} carriers")
    return score_df
