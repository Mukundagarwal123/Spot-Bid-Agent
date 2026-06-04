"""
Shared utility functions used across all models and precompute scripts.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path


def _configure_stdio_utf8() -> None:
    """Avoid UnicodeEncodeError on Windows consoles (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


_configure_stdio_utf8()


# --------------------------------------------------
# REPO ROOT DISCOVERY
# --------------------------------------------------
def get_repo_root():
    repo_root = Path.cwd().resolve()
    while repo_root != repo_root.parent and not (repo_root / "config" / "config.py").exists():
        repo_root = repo_root.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


# --------------------------------------------------
# DATA CLEANING
# --------------------------------------------------
def clean_dot(x):
    if pd.isna(x):
        return None
    x = str(x).strip().replace(".0", "").lstrip("0")
    return x if x != "" else None


def clean_zip(x):
    if pd.isna(x):
        return None
    x = str(x).strip()
    if "-" in x:
        x = x.split("-")[0]
    x = x.replace(".0", "")
    x = "".join(ch for ch in x if ch.isdigit())
    if x == "":
        return None
    return x[:5].zfill(5)


# --------------------------------------------------
# MATH
# --------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lat2, lon2 = np.radians(lat2), np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def scale_to_5(series):
    """Min-max scale a pandas Series to [0, 5]."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(5.0, index=series.index)
    return (series - mn) / (mx - mn) * 5


# --------------------------------------------------
# STATE FIPS -> STATE ABBR
# --------------------------------------------------
FIPS_TO_STATE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}

# --------------------------------------------------
# EQUIPMENT
# --------------------------------------------------
EQUIPMENT_MAP = {
    "dryvan": "DRY_VAN",
    "reefer": "REEFER",
    "flatbed": "FLATBED",
}


def apply_equipment_filter(df, equipment_list):
    """Filter DataFrame rows to carriers matching at least one selected equipment type."""
    if not equipment_list:
        return df
    # Guard: only keep cols that are both in the map AND present in df
    selected_cols = [
        EQUIPMENT_MAP[eq]
        for eq in equipment_list
        if eq in EQUIPMENT_MAP and EQUIPMENT_MAP[eq] in df.columns
    ]
    if not selected_cols:
        return df
    condition = False
    for col in selected_cols:
        condition = condition | (df[col] == 1)
    return df[condition].copy()


# --------------------------------------------------
# FMCSA PRECOMPUTE (shared logic for models 2-8)
# --------------------------------------------------
def _resolve_paths(output_dir):
    """Resolve data dir and output dir relative to the models/ directory."""
    models_dir = Path(__file__).resolve().parent      # src/api/models/
    data_dir = models_dir.parent.parent.parent / "data"  # FreightX/data/
    out = models_dir / output_dir                     # src/api/models/precomputed_modelN/
    out.mkdir(parents=True, exist_ok=True)
    return data_dir, out


def run_last_insp_precompute(output_dir: str):
    """Create last_insp.parquet with:
      - DOT_NUMBER
      - DAYS_SINCE_LAST_INSP

    Source: data/SMS_Input_-_Inspection.csv
    Output: src/api/models/<output_dir>/last_insp.parquet
    """
    models_dir = Path(__file__).resolve().parent  # src/api/models/
    data_dir = models_dir.parent.parent.parent / "data"  # FreightX/data/
    out = models_dir / output_dir
    out.mkdir(parents=True, exist_ok=True)

    today = pd.Timestamp.today().normalize()

    insp_path = data_dir / "SMS_Input_-_Inspection.csv"
    if not insp_path.exists():
        raise FileNotFoundError(f"Missing inspection source CSV: {insp_path}")

    inspection_df = pd.read_csv(
        insp_path,
        dtype=str,
        low_memory=False,
    )

    # Step 1: normalize header whitespace
    inspection_df.columns = [str(c).strip() for c in inspection_df.columns]

    # Step 2: normalize casing variants BEFORE selecting columns
    col_map = {c: c for c in inspection_df.columns}

    # DOT_Number / DOT_number / dot_number → DOT_NUMBER
    for c in list(inspection_df.columns):
        if c.lower() == "dot_number" and c != "DOT_NUMBER":
            inspection_df = inspection_df.rename(columns={c: "DOT_NUMBER"})
            break

    # Insp_date / INSP_DATE / insp_date → Insp_Date
    for c in list(inspection_df.columns):
        if c.strip().lower() == "insp_date" and c != "Insp_Date":
            inspection_df = inspection_df.rename(columns={c: "Insp_Date"})
            break

    # Step 3: validate required columns are present
    needed = ["DOT_NUMBER", "Insp_Date"]
    missing = set(needed) - set(inspection_df.columns)
    if missing:
        raise KeyError(
            f"Missing required columns {sorted(missing)} in {insp_path}. "
            f"Found: {list(inspection_df.columns)[:50]}"
        )

    # Step 4: select only the columns we need
    inspection_df = inspection_df[needed].copy()

    inspection_df["DOT_NUMBER"] = inspection_df["DOT_NUMBER"].apply(clean_dot)
    inspection_df = inspection_df.dropna(subset=["DOT_NUMBER"])

    inspection_df["Insp_Date"] = pd.to_datetime(inspection_df["Insp_Date"], errors="coerce", format="mixed")
    inspection_df = inspection_df.dropna(subset=["Insp_Date"])

    last_insp = (
        inspection_df.groupby("DOT_NUMBER", as_index=False)["Insp_Date"]
        .max()
        .rename(columns={"Insp_Date": "LAST_INSP_DATE"})
    )

    last_insp["DAYS_SINCE_LAST_INSP"] = (today - last_insp["LAST_INSP_DATE"]).dt.days
    last_insp = last_insp[["DOT_NUMBER", "DAYS_SINCE_LAST_INSP"]]

    last_insp.to_parquet(out / "last_insp.parquet", index=False)
    print(f"  last_insp.parquet: {len(last_insp):,} rows → saved")


def run_fmcsa_precompute(output_dir, include_centroids=False):
    """
    Run the standard FMCSA precomputation pipeline used by models 2-8.
    Produces parquets: carrier_counts, uszips, hq_lookup, valid_dots,
    carrier_base, insp_per_dot, county_count_per_dot, total_states_per_dot,
    equipment. Optionally county_centroids.
    """
    import geopandas as gpd

    get_repo_root()

    data_dir, out = _resolve_paths(output_dir)

    print("=" * 60)
    print(f"FMCSA PRECOMPUTE → {out}")
    print("=" * 60)

    carrier_counts = pd.read_csv(data_dir / "carrier_county_insp_counts.csv", dtype=str)
    uszips = pd.read_csv(data_dir / "uszips.csv", dtype={"zip": str})

    # Normalize carrier_counts headers to handle casing/whitespace variants
    carrier_counts.columns = [str(c).strip().upper() for c in carrier_counts.columns]

    census = pd.read_csv(
        data_dir / "Company_Census_File.csv",
        usecols=["DOT_NUMBER", "PHY_ZIP", "STATUS_CODE", "MCS150_DATE", "POWER_UNITS"],
        dtype={"DOT_NUMBER": "string", "PHY_ZIP": "string", "STATUS_CODE": "category"},
        parse_dates=["MCS150_DATE"],
    )

    carrier_hist = pd.read_csv(
        data_dir / "Carrier_-_All_With_History.csv",
        usecols=["DOT_NUMBER", "COMMON_STAT", "CONTRACT_STAT"],
        dtype="string",
    )

    auth = pd.read_csv(
        data_dir / "AuthHist_-_All_With_History.csv",
        usecols=["DOT_NUMBER", "ORIG_SERVED_DATE", "ORIGINAL_ACTION_DESC", "DISP_ACTION_DESC"],
        dtype="string",
    )

    equipment_df = pd.read_csv(
        data_dir / "carrier_equipment_active_new.csv",
        dtype={"DOT_NUMBER": str},
    )

    # ------- COUNTY CENTROIDS (optional) -------
    if include_centroids:
        counties_gdf = gpd.read_file(data_dir / "tl_2023_us_county.shp")

        geo = counties_gdf.to_crs(epsg=4326).copy()
        geo["STATEFP"] = geo["STATEFP"].astype(str).str.zfill(2)
        geo["COUNTYFP"] = geo["COUNTYFP"].astype(str).str.zfill(3)
        geo["STATE_ABBR"] = geo["STATEFP"].map(FIPS_TO_STATE)
        geo["STATE_COUNTY_CODE"] = geo["STATE_ABBR"] + geo["COUNTYFP"]

        geo = geo.to_crs(epsg=3857)
        geo["centroid"] = geo.geometry.centroid
        geo = geo.set_geometry("centroid").to_crs(epsg=4326)
        geo["centroid_lat"] = geo.geometry.y
        geo["centroid_lon"] = geo.geometry.x

        centroids = (
            geo[["STATE_COUNTY_CODE", "centroid_lat", "centroid_lon"]]
            .drop_duplicates(subset="STATE_COUNTY_CODE")
        )
        centroids.to_parquet(out / "county_centroids.parquet", index=False)
        print(f"  county_centroids: {len(centroids):,} rows → saved")

    # ------- CLEAN DOT NUMBERS -------
    for df in [carrier_counts, census, carrier_hist, auth]:
        df["DOT_NUMBER"] = df["DOT_NUMBER"].apply(clean_dot)

    census["PHY_ZIP"] = census["PHY_ZIP"].apply(clean_zip)
    census["POWER_UNITS"] = pd.to_numeric(census["POWER_UNITS"], errors="coerce").fillna(0)

    # ------- hq_lookup -------
    print("[1/7] hq_lookup...")
    hq_lookup = census[["DOT_NUMBER", "PHY_ZIP"]].dropna().drop_duplicates(subset="DOT_NUMBER")
    hq_lookup = hq_lookup.merge(uszips[["zip", "lat", "lng"]], left_on="PHY_ZIP", right_on="zip", how="left")
    hq_lookup = hq_lookup.rename(columns={"lat": "HQ_LAT", "lng": "HQ_LON"})
    hq_lookup = hq_lookup[["DOT_NUMBER", "PHY_ZIP", "HQ_LAT", "HQ_LON"]]
    hq_lookup.to_parquet(out / "hq_lookup.parquet", index=False)
    print(f"  {len(hq_lookup):,} rows")

    # ------- carrier_counts (normalised) -------
    print("[2/7] carrier_counts...")
    carrier_counts["INSP_COUNT"] = pd.to_numeric(carrier_counts["INSP_COUNT"], errors="coerce")
    carrier_counts["COUNTY_CODE_STATE"] = carrier_counts["COUNTY_CODE_STATE"].astype(str).str.strip().str.upper()
    carrier_counts["COUNTY_CODE"] = carrier_counts["COUNTY_CODE"].astype(str).str.zfill(3)
    carrier_counts["STATE_COUNTY_CODE"] = carrier_counts["COUNTY_CODE_STATE"] + carrier_counts["COUNTY_CODE"]
    carrier_counts.to_parquet(out / "carrier_counts.parquet", index=False)
    print(f"  {len(carrier_counts):,} rows")

    # ------- uszips -------
    print("[3/7] uszips...")
    uszips["zip"] = uszips["zip"].astype(str).str.zfill(5)
    uszips.to_parquet(out / "uszips.parquet", index=False)

    # ------- valid_dots -------
    print("[4/7] valid_dots...")
    census_active = census[census["STATUS_CODE"].str.strip().str.upper() == "A"].copy()
    census_active["MCS150_DATE"] = pd.to_datetime(census_active["MCS150_DATE"], errors="coerce")
    today = pd.Timestamp.today()
    census_active = census_active[(today - census_active["MCS150_DATE"]).dt.days <= 1000]
    census_dots = set(census_active["DOT_NUMBER"])

    carrier_hist["is_operational"] = (carrier_hist["COMMON_STAT"] == "A") | (carrier_hist["CONTRACT_STAT"] == "A")
    hist_dots = set(carrier_hist[carrier_hist["is_operational"]]["DOT_NUMBER"])

    auth["ORIG_SERVED_DATE"] = pd.to_datetime(auth["ORIG_SERVED_DATE"], errors="coerce", format="mixed")
    auth_valid = auth[
        (auth["ORIGINAL_ACTION_DESC"].isin(["GRANTED", "REINSTATED"]))
        & (auth["DISP_ACTION_DESC"].isna())
    ]
    latest_auth = auth_valid.groupby("DOT_NUMBER")["ORIG_SERVED_DATE"].max().reset_index()
    latest_auth["months_old"] = (today - latest_auth["ORIG_SERVED_DATE"]).dt.days / 30
    auth_dots = set(latest_auth[latest_auth["months_old"] >= 12]["DOT_NUMBER"])

    valid_dots = census_dots & hist_dots & auth_dots

    small_fleet_dots = set(
        census.loc[census["POWER_UNITS"] <= 50, "DOT_NUMBER"].dropna()
    )
    valid_dots = valid_dots & small_fleet_dots

    valid_dots_df = pd.DataFrame({"DOT_NUMBER": list(valid_dots)})
    valid_dots_df.to_parquet(out / "valid_dots.parquet", index=False)
    print(f"  {len(valid_dots_df):,} valid carriers")

    # ------- carrier_base -------
    print("[5/7] carrier_base...")
    carrier_base = carrier_counts[carrier_counts["DOT_NUMBER"].isin(valid_dots)].copy()
    carrier_base.to_parquet(out / "carrier_base.parquet", index=False)
    print(f"  {len(carrier_base):,} rows, {carrier_base['DOT_NUMBER'].nunique():,} DOTs")

    # ------- per-dot aggregates -------
    print("[6/7] per-dot aggregates...")
    insp_per_dot = (
        carrier_counts.groupby("DOT_NUMBER", as_index=False)["INSP_COUNT"]
        .sum()
        .rename(columns={"INSP_COUNT": "TOTAL_INSP_COUNT"})
    )
    county_count_per_dot = (
        carrier_counts.groupby("DOT_NUMBER")["STATE_COUNTY_CODE"]
        .nunique()
        .reset_index(name="TOTAL_COUNTIES_WITH_INSPECTIONS")
    )
    total_states_per_dot = (
        carrier_counts.groupby("DOT_NUMBER")["COUNTY_CODE_STATE"]
        .nunique()
        .reset_index(name="TOTAL_STATES_WITH_INSPECTIONS")
    )
    insp_per_dot.to_parquet(out / "insp_per_dot.parquet", index=False)
    county_count_per_dot.to_parquet(out / "county_count_per_dot.parquet", index=False)
    total_states_per_dot.to_parquet(out / "total_states_per_dot.parquet", index=False)

    # ------- equipment -------
    print("[7/7] equipment...")
    equipment_df["DOT_NUMBER"] = equipment_df["DOT_NUMBER"].apply(clean_dot)
    equipment_df.to_parquet(out / "equipment.parquet", index=False)
    print(f"  {len(equipment_df):,} rows")

    print("=" * 60)
    print(f"PRECOMPUTE COMPLETE → {out.resolve()}")
    print("=" * 60)
