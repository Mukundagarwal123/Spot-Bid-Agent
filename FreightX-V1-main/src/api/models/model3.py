"""
Model 3 — Pure entropy sorting + lane-specific tail filters.

Sort by county entropy on the route, with INSP_COUNT and TOTAL_INSP_COUNT
as secondary keys. Applies the full lane-mile bucket filters at the end.

Sort keys: ['COUNTY_ENTROPY', 'INSP_COUNT', 'TOTAL_INSP_COUNT']

Filters:
    - All basic global filters
    - >=350 miles: route-county restriction
    - Lane-specific tail filters (same as model 5)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from itertools import combinations

from models.helpers import haversine, scale_to_5, apply_equipment_filter


# --------------------------------------------------
# LOAD PRECOMPUTED DATA
# --------------------------------------------------
def load_precomputed(precompute_dir="precomputed_model3"):
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
    print(f"Model 3: loaded precomputed data, {len(data['valid_dots']):,} valid carriers")
    return data


# --------------------------------------------------
# LANE-SPECIFIC TAIL FILTERS (shared with models 4, 5)
# --------------------------------------------------
def apply_lane_tail_filters(df, lane_miles, sort_keys, sort_ascending):
    """
    Apply lane-mile bucket filters and sorting.
    Returns filtered + sorted DataFrame.
    """
    # if lane_miles <= 100:
    #     df = df[
    #         (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 19)
    #         & (df["TOTAL_INSP_COUNT"] <= 1500)
    #     ]
    #     df = df.sort_values(sort_keys, ascending=sort_ascending)

    # elif lane_miles <= 200:
    #     df = df[
    #         (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 13)
    #         & (df["TOTAL_STATES_WITH_INSPECTIONS"] >= 3)
    #         & (df["MAX_DIST"] >= 50)
    #     ]
    #     df = df.sort_values(sort_keys, ascending=sort_ascending)

    # elif lane_miles <= 400:
    #     df = df[
    #         (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 19)
    #         & (df["TOTAL_INSP_COUNT"] <= 1500)
    #     ]
    #     df = df.sort_values(sort_keys, ascending=sort_ascending)

    # elif lane_miles <= 800:
    #     df = df[
    #         (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 19)
    #         & (df["TOTAL_INSP_COUNT"] <= 1500)
    #     ]
    #     df = df.sort_values(sort_keys, ascending=sort_ascending)

    # else:
    #     df = df[
    #         (df["TOTAL_INSP_COUNT"] < 1000)
    #         & (df["COUNTIES_WITH_INSP_ON_ROUTE"] > 3)
    #         & (df["LANE_STATES_WITH_INSPECTIONS"] > 1)
    #         & (df["TOTAL_COUNTIES_WITH_INSPECTIONS"] >= 25)
    #         & (df["TOTAL_STATES_WITH_INSPECTIONS"] >= 20)
    #     ]
    #     df = df.sort_values(sort_keys, ascending=sort_ascending)
    df = df.sort_values(sort_keys, ascending=sort_ascending)
    return df.reset_index(drop=True)


# --------------------------------------------------
# MAX_DIST computation for 101-200 mile lanes
# --------------------------------------------------
def compute_max_dist(carrier_base_route, lane_miles, county_centroids):
    if 100 < lane_miles <= 200:
        def get_max_pair(x):
            counties = x["STATE_COUNTY_CODE"].unique().tolist()
            if len(counties) < 2:
                return pd.Series({"MAX_DIST": 0.0})
            max_dist = -1
            for c1, c2 in combinations(counties, 2):
                if c1 not in county_centroids or c2 not in county_centroids:
                    continue
                lat1 = county_centroids[c1]["centroid_lat"]
                lon1 = county_centroids[c1]["centroid_lon"]
                lat2 = county_centroids[c2]["centroid_lat"]
                lon2 = county_centroids[c2]["centroid_lon"]
                dist = haversine(lat1, lon1, lat2, lon2)
                if dist > max_dist:
                    max_dist = dist
            return pd.Series({"MAX_DIST": round(max_dist, 1)})

        return (
            carrier_base_route.groupby("DOT_NUMBER")
            .apply(get_max_pair)
            .reset_index()
        )
    else:
        return pd.DataFrame({
            "DOT_NUMBER": carrier_base_route["DOT_NUMBER"].unique(),
            "MAX_DIST": 0,
        })


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
        uszips = pd.read_parquet(models_dir / "precomputed_model3" / "uszips.parquet")
        lane_ctx = build_lane_context(source_zip, dest_zip, uszips)

    print("=" * 40)
    print("MODEL 3: Pure Entropy + Lane Tail Filters")
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
    # COUNTY INSPECTION SHARE
    # --------------------------------------------------
    county_total_insp = (
        route_carrier_base.groupby("STATE_COUNTY_CODE")["INSP_COUNT"]
        .sum().reset_index()
        .rename(columns={"INSP_COUNT": "COUNTY_TOTAL_INSP"})
    )
    route_carrier_base = route_carrier_base.merge(county_total_insp, on="STATE_COUNTY_CODE", how="left")
    route_carrier_base["COUNTY_INSP_SHARE"] = (
        route_carrier_base["INSP_COUNT"] / route_carrier_base["COUNTY_TOTAL_INSP"]
    )

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
    score_df["SRC_TO_HQ_DIST"] = score_df["SRC_TO_HQ_DIST"].fillna(99999)

    # --------------------------------------------------
    # ENTROPY (COUNTY_ENTROPY)
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
    score_df = score_df.merge(entropy_df, on="DOT_NUMBER", how="left")

    score_df["INSP_COUNT"] = pd.to_numeric(score_df["INSP_COUNT"], errors="coerce").fillna(0)
    score_df["TOTAL_INSP_COUNT"] = pd.to_numeric(score_df["TOTAL_INSP_COUNT"], errors="coerce")

    # --------------------------------------------------
    # LANE-SPECIFIC TAIL FILTERS + SORT
    # Sort: COUNTY_ENTROPY desc, INSP_COUNT desc, TOTAL_INSP_COUNT desc
    # --------------------------------------------------
    score_df = apply_lane_tail_filters(
        score_df,
        lane_ctx.lane_miles,
        sort_keys=["COUNTY_ENTROPY", "INSP_COUNT", "TOTAL_INSP_COUNT"],
        sort_ascending=[False, False, False],
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
        "COUNTY_ENTROPY": "LANE_SPREAD",
    })

    score_df["HQ_PROXIMITY"] = scale_to_5(score_df["HQ_PROXIMITY"].max() - score_df["HQ_PROXIMITY"])
    score_df["LANE_SPREAD"] = scale_to_5(score_df["LANE_SPREAD"])
    score_df["LANE_INSP"] = scale_to_5(score_df["LANE_INSP"])
    score_df["NATIONWIDE_INSP"] = scale_to_5(score_df["NATIONWIDE_INSP"])

    final_cols = ["DOT_NUMBER", "HQ_PROXIMITY", "LANE_SPREAD", "LANE_INSP", "NATIONWIDE_INSP"]
    score_df = score_df[final_cols]

    print(f"  Model 3 complete: {len(score_df):,} carriers")
    return score_df
