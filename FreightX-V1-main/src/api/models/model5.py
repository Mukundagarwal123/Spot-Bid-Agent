"""
Model 5 — "Best mix model so far" (direct copy of current full pipeline).

This is the current composite behavior: HQ + entropy + lane buckets + all
nuanced rules. Matches the existing full pipeline (longest_feature_modified.ipynb).

Key difference from models 2-4: ALWAYS applies route-county restriction
regardless of lane length (min_lane_insp=1 style).

Filters:
    - All basic global filters
    - Always route-county restriction (not conditional on >=350 miles)
    - Lane-specific tail filters (full end logic)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from itertools import combinations

from models.helpers import haversine, scale_to_5, apply_equipment_filter
from models.model3 import compute_max_dist


# --------------------------------------------------
# LOAD PRECOMPUTED DATA
# --------------------------------------------------
def load_precomputed(precompute_dir="precomputed_model5"):
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
    print(f"Model 5: loaded precomputed data, {len(data['valid_dots']):,} valid carriers")
    return data


# --------------------------------------------------
# LANE-SPECIFIC FILTERS + SORTING (model 5 specific sort order)
# --------------------------------------------------
def apply_model5_lane_filters(df, lane_miles):
    # """
    # Full mix model lane-based filters with HQ+entropy composite sorting.
    # This matches the existing full pipeline's sort/filter behavior.
    # """
    # if lane_miles <= 100:
    #     df = df[
    #         (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 19)
    #         & (df["TOTAL_INSP_COUNT"] <= 1500)
    #     ]
    #     df = df.sort_values(
    #         ["SRC_TO_HQ_DIST", "COUNTY_ENTROPY", "INSP_COUNT", "TOTAL_INSP_COUNT"],
    #         ascending=[True, False, False, False],
    #     )

    # elif lane_miles <= 200:
    #     df = df[
    #         (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 13)
    #         & (df["TOTAL_STATES_WITH_INSPECTIONS"] >= 3)
    #         & (df["MAX_DIST"] >= 50)
    #     ]
    #     df = df.sort_values(
    #         ["SRC_TO_HQ_DIST", "COUNTY_ENTROPY", "INSP_COUNT", "TOTAL_INSP_COUNT"],
    #         ascending=[True, False, False, False],
    #     )

    # elif lane_miles <= 400:
    #     df = df[
    #         (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 19)
    #         & (df["TOTAL_INSP_COUNT"] <= 1500)
    #     ]
    #     df = df.sort_values(
    #         ["SRC_TO_HQ_DIST", "COUNTY_ENTROPY", "INSP_COUNT", "TOTAL_INSP_COUNT"],
    #         ascending=[True, False, False, False],
    #     )

    # elif lane_miles <= 800:
    #     df = df[
    #         (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 19)
    #         & (df["TOTAL_INSP_COUNT"] <= 1500)
    #     ]
    #     df = df.sort_values(
    #         ["COUNTY_ENTROPY", "SRC_TO_HQ_DIST", "INSP_COUNT", "TOTAL_INSP_COUNT"],
    #         ascending=[False, True, False, False],
    #     )

    # else:
    #     df = df[
    #         (df["TOTAL_INSP_COUNT"] < 1000)
    #         & (df["COUNTIES_WITH_INSP_ON_ROUTE"] > 3)
    #         & (df["LANE_STATES_WITH_INSPECTIONS"] > 1)
    #         & (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 25)
    #         & (df["TOTAL_STATES_WITH_INSPECTIONS"] >= 20)
    #     ]
    #     df = df.sort_values(
    #         ["COUNTY_ENTROPY", "SRC_TO_HQ_DIST", "INSP_COUNT", "TOTAL_INSP_COUNT"],
    #         ascending=[False, True, False, False],
    #     )

    df = df.sort_values(
            ["SRC_TO_HQ_DIST","COUNTY_ENTROPY", "INSP_COUNT", "TOTAL_INSP_COUNT"],
            ascending=[True, False, False, False],
        )

    return df.reset_index(drop=True)


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
        uszips = pd.read_parquet(models_dir / "precomputed_model5" / "uszips.parquet")
        lane_ctx = build_lane_context(source_zip, dest_zip, uszips)

    print("=" * 40)
    print("MODEL 5: Full Mix (Best Model So Far)")
    print("=" * 40)

    carrier_base = precomputed["carrier_base"][
        precomputed["carrier_base"]["DOT_NUMBER"].isin(precomputed["valid_dots"])
    ].copy()

    # --------------------------------------------------
    # ALWAYS restrict to route counties (unlike models 2-4)
    # --------------------------------------------------
    carrier_base = carrier_base[
        carrier_base["STATE_COUNTY_CODE"].isin(lane_ctx.route_codes)
    ].copy()
    print(f"  Route-county restricted: {carrier_base['DOT_NUMBER'].nunique():,} carriers")

    # --------------------------------------------------
    # COUNTY INSPECTION SHARE
    # --------------------------------------------------
    county_total_insp = (
        carrier_base.groupby("STATE_COUNTY_CODE")["INSP_COUNT"]
        .sum().reset_index()
        .rename(columns={"INSP_COUNT": "COUNTY_TOTAL_INSP"})
    )
    carrier_base = carrier_base.merge(county_total_insp, on="STATE_COUNTY_CODE", how="left")
    carrier_base["COUNTY_INSP_SHARE"] = (
        carrier_base["INSP_COUNT"] / carrier_base["COUNTY_TOTAL_INSP"]
    )

    # --------------------------------------------------
    # MAX_DIST
    # --------------------------------------------------
    dist_df = compute_max_dist(carrier_base, lane_ctx.lane_miles, precomputed["county_centroids"])

    # --------------------------------------------------
    # SCORE AGGREGATION
    # --------------------------------------------------
    score_df = (
        carrier_base.groupby("DOT_NUMBER")
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
        carrier_base.groupby("DOT_NUMBER")["COUNTY_CODE_STATE"]
        .nunique().reset_index(name="LANE_STATES_WITH_INSPECTIONS")
    )
    score_df = score_df.merge(lane_states_per_dot, on="DOT_NUMBER", how="left")

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

    # --------------------------------------------------
    # SUM COUNTY INSPECTION SHARE
    # --------------------------------------------------
    county_share_df = (
        carrier_base.groupby("DOT_NUMBER")["COUNTY_INSP_SHARE"]
        .sum().reset_index()
        .rename(columns={"COUNTY_INSP_SHARE": "SUM_COUNTY_INSP_SHARE"})
    )
    score_df = score_df.merge(county_share_df, on="DOT_NUMBER", how="left")

    # --------------------------------------------------
    # ENTROPY
    # --------------------------------------------------
    county_dist = carrier_base.copy()
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
    score_df = score_df.merge(entropy_df, on="DOT_NUMBER", how="left")

    score_df["INSP_COUNT"] = pd.to_numeric(score_df["INSP_COUNT"], errors="coerce").fillna(0)
    score_df["TOTAL_INSP_COUNT"] = pd.to_numeric(score_df["TOTAL_INSP_COUNT"], errors="coerce")

    # --------------------------------------------------
    # LANE-SPECIFIC FILTERS + SORT (full mix model sorting)
    # --------------------------------------------------
    score_df = apply_model5_lane_filters(score_df, lane_ctx.lane_miles)

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
        "COUNTY_ENTROPY": "LANE_SPREAD",
    })

    score_df["HQ_PROXIMITY"] = scale_to_5(score_df["HQ_PROXIMITY"].max() - score_df["HQ_PROXIMITY"])
    score_df["LANE_SPREAD"] = scale_to_5(score_df["LANE_SPREAD"])
    score_df["LANE_INSP"] = scale_to_5(score_df["LANE_INSP"])
    score_df["NATIONWIDE_INSP"] = scale_to_5(score_df["NATIONWIDE_INSP"])

    final_cols = ["DOT_NUMBER", "HQ_PROXIMITY", "LANE_SPREAD", "LANE_INSP", "NATIONWIDE_INSP"]
    score_df = score_df[final_cols]

    print(f"  Model 5 complete: {len(score_df):,} carriers")
    return score_df
