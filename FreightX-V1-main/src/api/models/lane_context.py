"""
Shared per-lane context computation.

Computes Trimble route, intersecting counties, lane miles ONCE per lane
so that individual models never duplicate this expensive work.
"""

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString
import requests
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Set, List, Tuple

from models.helpers import haversine, FIPS_TO_STATE, get_repo_root

get_repo_root()
from config.config import TRIMBLE_API_KEY


# --------------------------------------------------
# DATACLASS: holds all shared per-lane results
# --------------------------------------------------
@dataclass
class LaneContext:
    route_points: List[Tuple[float, float]]
    route_counties_df: pd.DataFrame
    route_codes: Set[str]
    lane_miles: float
    src_lat: float
    src_lon: float
    dst_lat: float
    dst_lon: float


# --------------------------------------------------
# COUNTY GEOMETRY (loaded once, cached at module level)
# --------------------------------------------------
_counties_gdf_4326 = None
_counties_sindex = None


def _load_county_geometry():
    global _counties_gdf_4326, _counties_sindex
    if _counties_gdf_4326 is not None:
        return _counties_gdf_4326, _counties_sindex

    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"
    counties_gdf = gpd.read_file(str(data_dir / "tl_2023_us_county.shp"))
    _counties_gdf_4326 = counties_gdf.to_crs(epsg=4326)
    _counties_sindex = _counties_gdf_4326.sindex
    print(f"County geometry loaded: {len(_counties_gdf_4326):,} rows")
    return _counties_gdf_4326, _counties_sindex


# --------------------------------------------------
# TRIMBLE ROUTE API
# --------------------------------------------------
def get_truck_route_from_zips(source_zip, dest_zip, uszips_df, api_key=None):
    if api_key is None:
        api_key = TRIMBLE_API_KEY

    source_zip = str(source_zip).zfill(5)
    dest_zip = str(dest_zip).zfill(5)

    src_row = uszips_df.loc[uszips_df["zip"] == source_zip].iloc[0]
    dst_row = uszips_df.loc[uszips_df["zip"] == dest_zip].iloc[0]

    src_lat, src_lon = float(src_row["lat"]), float(src_row["lng"])
    dst_lat, dst_lon = float(dst_row["lat"]), float(dst_row["lng"])

    headers = {"Authorization": api_key}
    url = (
        "https://pcmiler.alk.com/apis/rest/v1.0/Service.svc/route/routePath"
        f"?stops={src_lon},{src_lat};{dst_lon},{dst_lat}"
        "&dataset=Current&routeType=Practical&vehType=0&reduceResponsePoints=false"
    )

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise ValueError(f"Route API failed:\n{response.text}")

    data = json.loads(response.content.decode("utf-8-sig"))
    coords = data["geometry"]["coordinates"]
    if isinstance(coords[0][0], list):
        coords = coords[0]

    return [(lat, lon) for lon, lat in coords]


# --------------------------------------------------
# COUNTY INTERSECTION
# --------------------------------------------------
def get_counties_for_lane(route_points):
    counties, sindex = _load_county_geometry()

    coords_lonlat = [(lon, lat) for lat, lon in route_points]
    lane_line = LineString(coords_lonlat)

    possible = counties.iloc[list(sindex.intersection(lane_line.bounds))]
    intersecting = possible[possible.intersects(lane_line)].copy()

    intersecting["STATEFP"] = intersecting["STATEFP"].astype(str).str.zfill(2)
    intersecting["COUNTYFP"] = intersecting["COUNTYFP"].astype(str).str.zfill(3)
    intersecting["STATE_ABBR"] = intersecting["STATEFP"].map(FIPS_TO_STATE)
    intersecting["STATE_COUNTY_CODE"] = intersecting["STATE_ABBR"] + intersecting["COUNTYFP"]

    return intersecting[
        ["NAME", "STATE_ABBR", "COUNTYFP", "STATE_COUNTY_CODE"]
    ].drop_duplicates().reset_index(drop=True)


# --------------------------------------------------
# LANE MILES
# --------------------------------------------------
def compute_lane_miles(route_points):
    route_df = pd.DataFrame(route_points, columns=["lat", "lon"])
    route_df["next_lat"] = route_df["lat"].shift(-1)
    route_df["next_lon"] = route_df["lon"].shift(-1)
    route_df["seg_dist"] = haversine(
        route_df["lat"], route_df["lon"],
        route_df["next_lat"], route_df["next_lon"],
    ).fillna(0)
    return route_df["seg_dist"].cumsum().iloc[-1]


# --------------------------------------------------
# BUILD FULL LANE CONTEXT (called once per lane)
# --------------------------------------------------
def build_lane_context(source_zip, dest_zip, uszips_df) -> LaneContext:
    """
    Single entry point that performs ALL expensive per-lane work:
    Trimble route, county intersection, lane miles.
    """
    print("=" * 40)
    print("BUILDING SHARED LANE CONTEXT")
    print("=" * 40)

    route_points = get_truck_route_from_zips(source_zip, dest_zip, uszips_df)
    print(f"  Route points: {len(route_points)}")

    route_counties_df = get_counties_for_lane(route_points)
    route_codes = set(route_counties_df["STATE_COUNTY_CODE"])
    print(f"  Counties on route: {len(route_codes)}")

    lane_miles = compute_lane_miles(route_points)
    print(f"  Lane miles: {round(lane_miles, 2)}")

    src_lat, src_lon = route_points[0]
    dst_lat, dst_lon = route_points[-1]

    ctx = LaneContext(
        route_points=route_points,
        route_counties_df=route_counties_df,
        route_codes=route_codes,
        lane_miles=lane_miles,
        src_lat=src_lat,
        src_lon=src_lon,
        dst_lat=dst_lat,
        dst_lon=dst_lon,
    )

    print("  Lane context ready.")
    return ctx
