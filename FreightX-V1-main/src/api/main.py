import base64
import streamlit as st
import streamlit.components.v1 as components
import duckdb
import os
import pandas as pd
from pathlib import Path

st.set_page_config(layout="wide", page_title="Carrier Search")

script_dir = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = Path(script_dir).parent.parent / "data"

# -----------------------------
# ✅ CACHE ZIP DATA
# -----------------------------
@st.cache_data
def load_zips():
    df = pd.read_csv(DATA_DIR / "uszips.csv", dtype={"zip": str})
    return set(df["zip"].str.strip())

valid_zips = load_zips()


def dataframe_to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

# -----------------------------
# FILE PATHS
# -----------------------------
CSV_FILE = str((DATA_DIR / "df_output_with_inspections1.csv").resolve())

DOT_SEARCH_FILE = str((DATA_DIR / "df_output_with_inspection1.csv").resolve())
if not os.path.exists(DOT_SEARCH_FILE):
    DOT_SEARCH_FILE = CSV_FILE

if CSV_FILE is None:
    st.error("No supported CSV file found.")
    st.stop()

# -----------------------------
# ✅ CACHE DUCKDB CONNECTION
# -----------------------------
@st.cache_resource
def load_duckdb(csv_file, dot_file):
    con = duckdb.connect("carrier.db")

    # ✅ Check if main table exists
    table_exists = con.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_name='df'
    """).fetchone()[0]

    if table_exists == 0:
        con.execute(f"""
            CREATE TABLE df AS 
            SELECT * FROM read_csv_auto('{csv_file}', IGNORE_ERRORS=TRUE)
        """)

    # ✅ Check if dot table exists
    dot_exists = con.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_name='df_dot_lookup'
    """).fetchone()[0]

    if dot_exists == 0 and os.path.exists(dot_file):
        con.execute(f"""
            CREATE TABLE df_dot_lookup AS 
            SELECT * FROM read_csv_auto('{dot_file}', IGNORE_ERRORS=TRUE)
        """)

    return con


con = load_duckdb(CSV_FILE, DOT_SEARCH_FILE)

# -----------------------------
# ✅ CACHE COLUMN METADATA
# -----------------------------
@st.cache_data
def get_table_columns_map(table_name):
    cols = [c[0] for c in con.execute(
        f"SELECT column_name FROM information_schema.columns WHERE table_name='{table_name}'"
    ).fetchall()]
    return {c.upper(): c for c in cols}


all_columns_upper = get_table_columns_map("df")
dot_lookup_columns_upper = (
    get_table_columns_map("df_dot_lookup") if os.path.exists(DOT_SEARCH_FILE) else {}
)

# -----------------------------
# HELPERS
# -----------------------------
def resolve_column(candidates, columns_map):
    for candidate in candidates:
        if candidate.upper() in columns_map:
            return columns_map[candidate.upper()]
    return None


def build_lane_output_filename(src, dest, equipment_list):
    if equipment_list:
        equip_part = "_".join(equipment_list)
        return f"{src}_{dest}_{equip_part}.csv"
    return f"{src}_{dest}.csv"


def trigger_auto_download(csv_bytes, filename):
    b64 = base64.b64encode(csv_bytes).decode()
    safe_filename = filename.replace("'", "\\'")
    components.html(
        f"""
        <script>
        (function() {{
            const link = document.createElement("a");
            link.href = "data:text/csv;base64,{b64}";
            link.download = "{safe_filename}";
            const target = window.parent.document.body;
            target.appendChild(link);
            link.click();
            target.removeChild(link);
        }})();
        </script>
        """,
        height=0,
    )


def normalize_dot_number(dot_value):
    cleaned = str(dot_value).strip()
    return int(cleaned) if cleaned else None


def normalize_docket_number(docket_value):
    cleaned = str(docket_value).strip().upper()
    if not cleaned:
        return None
    numeric_part = cleaned[2:] if cleaned.startswith("MC") else cleaned
    return f"MC{int(numeric_part)}"

# -----------------------------
# UI
# -----------------------------
st.title("Carrier Search")

if "carrier_results" not in st.session_state:
    st.session_state["carrier_results"] = None
if "lane_results" not in st.session_state:
    st.session_state["lane_results"] = None
if "lane_output_filename" not in st.session_state:
    st.session_state["lane_output_filename"] = None
if "lane_auto_download" not in st.session_state:
    st.session_state["lane_auto_download"] = False

search_option = st.radio(
    "Select search option:",
    [
        "Search carrier details (DOT/DOCKET)",
        "Search by lane (pickup/drop)",
    ],
    horizontal=True,
)

# =============================
# 🔍 CARRIER SEARCH
# =============================
if search_option == "Search carrier details (DOT/DOCKET)":
    st.subheader("Carrier details search")

    col1, col2 = st.columns(2)
    dot_number_input = col1.text_input("DOT_NUMBER")
    docket_number_input = col2.text_input("DOCKET_NUMBER")

    if st.button("Search carrier"):
        where_parts = []
        params = []

        search_table = "df_dot_lookup" if dot_number_input.strip() else "df"
        table_columns = dot_lookup_columns_upper if search_table == "df_dot_lookup" else all_columns_upper

        dot_col = resolve_column(["DOT_NUMBER"], table_columns)
        docket_col = resolve_column(["DOCKET_NUMBER"], table_columns)

        if dot_number_input.strip():
            if dot_col is None:
                st.error("DOT column missing")
                st.stop()

            normalized_dot = normalize_dot_number(dot_number_input)

            where_parts.append(
                f"TRY_CAST(NULLIF(regexp_replace(TRIM(CAST({dot_col} AS VARCHAR)), '^0+', ''), '') AS BIGINT) = ?"
            )
            params.append(normalized_dot)

        if docket_number_input.strip():
            if docket_col is None:
                st.error("DOCKET column missing")
                st.stop()

            normalized_docket = normalize_docket_number(docket_number_input)

            where_parts.append(
                "CASE "
                f"WHEN UPPER(TRIM(CAST({docket_col} AS VARCHAR))) LIKE 'MC%' THEN "
                f"'MC' || CAST(COALESCE(TRY_CAST(NULLIF(regexp_replace(substr(UPPER(TRIM(CAST({docket_col} AS VARCHAR))), 3), '^0+', ''), '') AS BIGINT), 0) AS VARCHAR) "
                f"ELSE UPPER(TRIM(CAST({docket_col} AS VARCHAR))) "
                "END = ?"
            )
            params.append(normalized_docket)

        if where_parts:
            query = f"SELECT * FROM {search_table} WHERE {' AND '.join(where_parts)}"
            st.session_state["carrier_results"] = con.execute(query, params).df()
        else:
            st.warning("Enter DOT or DOCKET")

    if st.session_state["carrier_results"] is not None:
        df = st.session_state["carrier_results"]
        st.write(f"Rows found: {len(df)}")
        st.dataframe(df, use_container_width=True)

        csv = dataframe_to_csv_bytes(df)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="carrier_search_results.csv",
            mime="text/csv",
        )

# =============================
# 🚚 LANE SEARCH
# =============================
else:
    st.subheader("Lane search")

    col1, col2 = st.columns(2)
    src_zip = col1.text_input("Source ZIP")
    dest_zip = col2.text_input("Destination ZIP")

    col1, col2, col3 = st.columns(3)
    dryvan = col1.checkbox("DryVan")
    reefer = col2.checkbox("Reefer")
    flatbed = col3.checkbox("Flatbed")

    equipment_list = []
    if dryvan: equipment_list.append("dryvan")
    if reefer: equipment_list.append("reefer")
    if flatbed: equipment_list.append("flatbed")

    if st.button("Search carriers for this lane"):
        if not src_zip or not dest_zip:
            st.warning("Enter both ZIPs")
        else:
            src = src_zip.zfill(5)
            dst = dest_zip.zfill(5)

            if src not in valid_zips or dst not in valid_zips:
                st.error("Invalid ZIP")
            else:
                with st.spinner("Running model..."):
                    from models.combine_model import run_my_model
                    from model_run_tracker import (
                        RUNS_BEFORE_KEY_REFRESH,
                        get_last_run_stats,
                    )
                    try:
                        lane_df = run_my_model(src, dst, equipment_list)
                        run_count, key_refreshed = get_last_run_stats()
                        st.session_state["lane_results"] = lane_df
                        st.session_state["lane_output_filename"] = build_lane_output_filename(
                            src, dst, equipment_list
                        )
                        st.session_state["lane_auto_download"] = True
                        st.session_state["combined_model_run_count"] = run_count
                        if run_count % RUNS_BEFORE_KEY_REFRESH == 0:
                            if key_refreshed:
                                st.success(
                                    f"Trimble API key refreshed after {run_count} model runs."
                                )
                            else:
                                st.warning(
                                    f"Run #{run_count}: API key refresh was attempted but failed. "
                                    "Run web_agent.py manually or retry the next lane search."
                                )
                    except Exception as e:
                        st.error(f"Model failed: {str(e)}")

    if st.session_state["lane_results"] is not None:
        df = st.session_state["lane_results"]
        output_filename = st.session_state.get("lane_output_filename") or "lane_search_results.csv"
        csv = dataframe_to_csv_bytes(df)

        st.write(f"Top {len(df)} rows")
        st.dataframe(df, use_container_width=True)

        if st.session_state.get("lane_auto_download"):
            trigger_auto_download(csv, output_filename)
            st.session_state["lane_auto_download"] = False

        st.download_button(
            label=f"Download {output_filename}",
            data=csv,
            file_name=output_filename,
            mime="text/csv",
        )

# -----------------------------
from model_run_tracker import RUNS_BEFORE_KEY_REFRESH, get_combined_model_run_count

_run_count = get_combined_model_run_count()
_runs_until_refresh = (
    RUNS_BEFORE_KEY_REFRESH - (_run_count % RUNS_BEFORE_KEY_REFRESH)
    if _run_count % RUNS_BEFORE_KEY_REFRESH != 0
    else RUNS_BEFORE_KEY_REFRESH
)
st.caption(
    f"Powered by DuckDB | Source: {os.path.basename(CSV_FILE)} | "
    f"Model runs: {_run_count} ({_runs_until_refresh} until API key refresh)"
)