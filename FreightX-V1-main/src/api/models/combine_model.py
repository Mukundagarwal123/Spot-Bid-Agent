"""
Combined multi-model carrier ranking pipeline.

Orchestrates all 6 models with:
    - Single shared Trimble/county/lane-miles pass
    - Parallel model execution
    - Column union + null fill
    - Dedup by DOT_NUMBER (keep='first', priority order: model 1→2→3→4→5→6)
    - LABEL column (e.g. "1_4_5"): concat overlap of SOURCE_MODELs for that DOT;
      model ids always joined in ascending numeric order (never e.g. "1_5_4")
    - Enrichment merge from df_output_with_inspections
    - Row budget MODEL_POOL_SIZE for initial pooled ranked pulls (with model 1’s x);
      recursive top-up stops once combined rows with valid EMAIL_ADDRESS reach
      DEDUP_RECURSION_STOP_AT (after enrichment merge on all models 1–6).
      Top-up uses the same lane ratios from ranks after previously consumed rows.
    - Configurable enrichment_columns
"""

from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import time as _time
from pathlib import Path

from models.helpers import clean_zip
from models.lane_context import build_lane_context

from models.model1 import run_my_model as _run_model1, load_precomputed as _load_m1
from models.model2 import run_my_model as _run_model2, load_precomputed as _load_m2
from models.model3 import run_my_model as _run_model3, load_precomputed as _load_m3
from models.model4 import run_my_model as _run_model4, load_precomputed as _load_m4
from models.model5 import run_my_model as _run_model5, load_precomputed as _load_m5
from models.model6 import run_my_model as _run_model6, load_precomputed as _load_m6


# --------------------------------------------------
# MODEL REGISTRY (ordered by priority for dedup)
# --------------------------------------------------
MODEL_RUNNERS = [
    {"id": "1", "name": "FreightX History",          "runner": _run_model1, "loader": _load_m1, "needs_lane_ctx": False},
    {"id": "2", "name": "Pure HQ Proximity",         "runner": _run_model2, "loader": _load_m2, "needs_lane_ctx": True},
    {"id": "3", "name": "Entropy + Tail",            "runner": _run_model3, "loader": _load_m3, "needs_lane_ctx": True},
    {"id": "4", "name": "Insp Count + Tail",         "runner": _run_model4, "loader": _load_m4, "needs_lane_ctx": True},
    {"id": "5", "name": "Full Mix (Best)",           "runner": _run_model5, "loader": _load_m5, "needs_lane_ctx": True},
    {"id": "6", "name": "Recent Insp Window",        "runner": _run_model6, "loader": _load_m6, "needs_lane_ctx": True},
]

# --------------------------------------------------
# POOLED-MODEL CONTRIBUTION CONFIG (models 2-6)
# --------------------------------------------------
# MODEL_POOL_SIZE: models 2–6 initially consume (MODEL_POOL_SIZE - x) ranked slots
# (by lane bucket ratios). Top-up rounds stop when deduped rows >= DEDUP_RECURSION_STOP_AT.
#
# Lane-length buckets:
#   short  → lane_miles <  200
#   medium → 200 ≤ lane_miles ≤ 700
#   long   → lane_miles  >  700
#
# Fractions are per model [2, 3, 4, 5, 6] and should sum to 1.0.

MODEL_POOL_SIZE = 1500              # initial pooled ranked-slot budget uses (1500 - x)
DEDUP_RECURSION_STOP_AT = 1450      # stop top-up once email-valid combined rows reach this
POOLED_MODELS   = {"2", "3", "4", "5", "6"}
MAX_POOL_TOPUP_ROUNDS = 250         # safety cap on recursive bandwidth fills

LANE_SHORT_MAX  = 200           # miles
LANE_MEDIUM_MAX = 700           # miles

CONTRIBUTION_VECTORS = {
    "short": {          # lane < 200 mi
        "2": 0.30,
        "3": 0.10,
        "4": 0.30,
        "5": 0.20,
        "6": 0.10,
    },
    "medium": {         # 200 ≤ lane ≤ 700 mi
        "2": 0.15,
        "3": 0.20,
        "4": 0.25,
        "5": 0.30,
        "6": 0.10,
    },
    "long": {           # lane > 700 mi
        "2": 0.10,
        "3": 0.30,
        "4": 0.20,
        "5": 0.30,
        "6": 0.10,
    },
}


def _dot_label_key(dot):
    """
    Canonical DOT string for LABEL membership checks (consistent across int/float/str).
    Invalid / missing DOT → None (excluded from label sets).
    """
    if dot is None:
        return None
    try:
        if pd.isna(dot):
            return None
    except TypeError:
        pass
    s = str(dot).strip()
    if not s or s.lower() in ("nan", "<na>", "nat", "none"):
        return None
    try:
        f = float(s.replace(",", ""))
        if f.is_integer():
            return str(int(f))
    except ValueError:
        pass
    return s


def _mid_from_source_model(val):
    """SOURCE_MODEL like 'MODEL4' → '4'; invalid → None."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except TypeError:
        pass
    s = str(val).strip().upper()
    if s.startswith("MODEL"):
        rest = s[len("MODEL") :].strip()
        return rest if rest else None
    return None


def _normalize_contribution_for_active(contribution, active_mids):
    """Restrict contribution keys to active pooled models and renormalize to sum 1."""
    sub = {k: float(contribution[k]) for k in active_mids if k in contribution}
    s = sum(sub.values())
    if not sub:
        return {}
    if s <= 0:
        u = 1.0 / len(sub)
        return {k: u for k in sub}
    return {k: v / s for k, v in sub.items()}


def _has_valid_email(val):
    """True if enrichment/email field is present and non-empty."""
    if val is None:
        return False
    try:
        if pd.isna(val):
            return False
    except TypeError:
        pass
    s = str(val).strip()
    if not s or s.lower() in ("nan", "<na>", "nat", "none"):
        return False
    return True


def _merge_enrichment_and_filter_email(combined_df, enrichment_df):
    """
    Left-merge enrichment on DOT_NUMBER, then drop rows without a usable EMAIL_ADDRESS.
    Applied to the full combined set (models 1–6) after dedup.
    """
    if combined_df.empty:
        return combined_df

    out = combined_df.copy()
    if not enrichment_df.empty:
        out["DOT_NUMBER"] = out["DOT_NUMBER"].astype(str)
        enrich = enrichment_df.copy()
        enrich["DOT_NUMBER"] = enrich["DOT_NUMBER"].astype(str)
        out = out.merge(enrich, on="DOT_NUMBER", how="left")

    before = len(out)
    if "EMAIL_ADDRESS" not in out.columns:
        print("  WARNING: EMAIL_ADDRESS missing after enrichment — no rows kept")
        return out.iloc[0:0].copy()

    em_ok = out["EMAIL_ADDRESS"].apply(_has_valid_email)
    out = out.loc[em_ok].copy()
    dropped = before - len(out)
    print(
        f"  After enrichment + email filter: {len(out):,} rows kept"
        + (f" ({dropped:,} dropped, no usable email)" if dropped else "")
    )
    return out


def _allocate_pooled_row_counts(contribution, budget):
    """
    Split integer budget across pooled models using contribution ratios (sum ≈ 1).
    Largest remainder so assigned counts sum exactly to budget.
    """
    if budget <= 0:
        return {mid: 0 for mid in contribution}
    if not contribution:
        return {}
    mids = sorted(contribution.keys(), key=lambda k: int(k))
    weights = [float(contribution[m]) for m in mids]
    s = sum(weights)
    if s <= 0:
        return {mid: 0 for mid in contribution}
    weights = [w / s for w in weights]
    exact = [weights[i] * budget for i in range(len(mids))]
    base = [int(e) for e in exact]
    rem = budget - sum(base)
    frac_order = sorted(
        range(len(mids)),
        key=lambda i: (exact[i] - base[i]),
        reverse=True,
    )
    for i in range(rem):
        base[frac_order[i]] += 1
    return dict(zip(mids, base))


# --------------------------------------------------
# DEFAULT ENRICHMENT COLUMNS (configurable)
# --------------------------------------------------
DEFAULT_ENRICHMENT_COLUMNS = [
    "DOT_NUMBER",
    "EMAIL_ADDRESS",
    "DOCKET_NUMBER",
    "PHONE",
    "CSA_PERCENTILE",
    "DF_PERCENTILE",
    "HOS_PERCENTILE",
    "UD_PERCENTILE",
    "VM_PERCENTILE",
]


# --------------------------------------------------
# LOAD ENRICHMENT DATA (from precomputed parquet)
# --------------------------------------------------
def load_enrichment(columns=None):
    """
    Load enrichment from precomputed parquet (built by precompute_enrichment.py).
    Join key: DOT_NUMBER. Provides contact fields and CSA/DF/HOS/UD/VM percentiles.
    """
    if columns is None:
        columns = DEFAULT_ENRICHMENT_COLUMNS

    models_dir = Path(__file__).resolve().parent  # src/api/models/
    parquet_path = models_dir / "precomputed_shared" / "output_enrichment.parquet"

    if not parquet_path.exists():
        print(f"WARNING: Enrichment parquet not found at {parquet_path}")
        print("  Run precompute_enrichment.py first to build it.")
        return pd.DataFrame(columns=columns)

    print(f"Loading enrichment from {parquet_path} ...")
    df = pd.read_parquet(parquet_path)

    available_cols = [c for c in columns if c in df.columns]
    df = df[available_cols]
    df = df.drop_duplicates(subset=["DOT_NUMBER"], keep="first")

    print(f"  Enrichment loaded: {len(df):,} unique DOTs")
    return df


# --------------------------------------------------
# MAIN COMBINED FUNCTION
# --------------------------------------------------
def _record_successful_run() -> None:
    from model_run_tracker import record_combined_model_run

    record_combined_model_run()


def run_my_model(
    source_zip,
    dest_zip,
    equipment_list=None,
    enrichment_columns=None,
    model_ids=None,
):
    """
    Run all (or selected) models, combine results.

    Args:
        source_zip: origin zip code (string, int, or float; normalized to 5-digit str)
        dest_zip: destination zip code (string, int, or float; normalized to 5-digit str)
        equipment_list: list of equipment types (e.g. ["dryvan", "reefer"])
        enrichment_columns: list of columns from enrichment parquet to merge
        model_ids: list of model IDs to run (default: all ["1","2","3","4","5","6"])

    Returns:
        DataFrame with combined, deduped, labeled, enriched results

    Raises:
        ValueError: if source_zip or dest_zip cannot be normalized to a valid US ZIP
    """
    src = clean_zip(source_zip)
    if src is None:
        raise ValueError(
            f"Invalid source_zip: {source_zip!r}. "
            "Expected a US ZIP (5 digits, string or number)."
        )
    dst = clean_zip(dest_zip)
    if dst is None:
        raise ValueError(
            f"Invalid dest_zip: {dest_zip!r}. "
            "Expected a US ZIP (5 digits, string or number)."
        )
    source_zip, dest_zip = src, dst

    t_start = _time.time()

    if model_ids is None:
        model_ids = [m["id"] for m in MODEL_RUNNERS]

    active_models = [m for m in MODEL_RUNNERS if m["id"] in model_ids]

    print("=" * 60)
    print(f"COMBINED MODEL RUN: models {', '.join(model_ids)}")
    print(f"Lane: {source_zip} → {dest_zip}")
    print(f"Equipment: {equipment_list or 'all'}")
    print(
        f"Pooled slot budget: {MODEL_POOL_SIZE}, top-up stops at {DEDUP_RECURSION_STOP_AT} deduped rows | "
        f"Model 1: all rows (x) | Pooled (2-6): initial ({MODEL_POOL_SIZE} - x) rank slots by ratios; "
        f"top-up until ≥ {DEDUP_RECURSION_STOP_AT} rows with valid email (all models, post-enrichment)"
    )
    print("=" * 60)

    # =============================================
    # 1. LOAD PRECOMPUTED DATA FOR EACH MODEL
    # =============================================
    print("\n[1/5] Loading precomputed data...")
    precomputed_data = {}
    for m in active_models:
        try:
            precomputed_data[m["id"]] = m["loader"]()
        except Exception as e:
            print(f"  WARNING: Failed to load precomputed data for model {m['id']}: {e}")

    # =============================================
    # 2. COMPUTE SHARED LANE CONTEXT ONCE
    # =============================================
    print("\n[2/5] Computing shared lane context...")
    needs_lane = any(m["needs_lane_ctx"] for m in active_models if m["id"] in precomputed_data)

    models_dir = Path(__file__).resolve().parent  # src/api/models/
    lane_ctx = None
    if needs_lane:
        for mid in ["2", "3", "4", "5", "6"]:
            if mid in precomputed_data:
                pdir = models_dir / f"precomputed_model{mid}"
                uszips = pd.read_parquet(pdir / "uszips.parquet")
                break
        lane_ctx = build_lane_context(source_zip, dest_zip, uszips)

    # =============================================
    # 3. RUN MODELS IN PARALLEL
    # =============================================
    print("\n[3/5] Running models in parallel...")

    def _run_single_model(model_info):
        mid = model_info["id"]
        if mid not in precomputed_data:
            print(f"  Model {mid} skipped (no precomputed data)")
            return mid, pd.DataFrame()

        try:
            kwargs = {
                "source_zip": source_zip,
                "dest_zip": dest_zip,
                "equipment_list": equipment_list,
            }

            if model_info["needs_lane_ctx"]:
                kwargs["lane_ctx"] = lane_ctx
                kwargs["precomputed"] = precomputed_data[mid]
            else:
                # Model 1 (FreightX) uses shipments_df
                kwargs["shipments_df"] = precomputed_data[mid]

            result = model_info["runner"](**kwargs)
            print(f"  model {mid} complete: {len(result):,} rows")
            return mid, result

        except Exception as e:
            print(f"  ERROR in model {mid}: {e}")
            return mid, pd.DataFrame()

    model_results = {}
    with ThreadPoolExecutor(max_workers=len(active_models)) as executor:
        futures = {
            executor.submit(_run_single_model, m): m["id"]
            for m in active_models
        }
        for future in futures:
            mid, result_df = future.result()
            model_results[mid] = result_df

    # --- Per-model count summary ---
    print("\n  --- PER-MODEL COUNTS ---")
    for mid in sorted(model_results.keys()):
        count = len(model_results[mid])
        print(f"  Model {mid}: {count:,} carriers")
    print("  -------------------------")

    # =============================================
    # 4. COMBINE: concat, dedup, label; enrich + email filter on full set
    # =============================================
    print("\n[4/5] Combining results...")

    enrichment_df = load_enrichment(enrichment_columns)
    lane_miles = lane_ctx.lane_miles if lane_ctx is not None else 0
    if lane_miles < LANE_SHORT_MAX:
        lane_bucket = "short"
    elif lane_miles <= LANE_MEDIUM_MAX:
        lane_bucket = "medium"
    else:
        lane_bucket = "long"

    contribution = CONTRIBUTION_VECTORS[lane_bucket]
    print(f"  Lane miles: {lane_miles:.0f} mi → bucket: '{lane_bucket}'")
    print(f"  Contribution vector (of pooled budget): { {mid: f'{v:.0%}' for mid, v in contribution.items()} }")

    active_pooled_mids = sorted(POOLED_MODELS.intersection(set(model_ids)), key=int)
    contrib_norm = _normalize_contribution_for_active(contribution, active_pooled_mids)
    print(
        f"  Active pooled models: {active_pooled_mids} | "
        f"Normalized shares: { {k: f'{v:.0%}' for k, v in sorted(contrib_norm.items(), key=lambda kv: int(kv[0]))} }"
    )

    df1 = model_results.get("1", pd.DataFrame())
    if df1 is not None and not df1.empty:
        x_rows = len(df1)
    else:
        x_rows = 0
    pooled_budget = max(0, MODEL_POOL_SIZE - x_rows)

    chunks_by_mid = {mid: [] for mid in active_pooled_mids}
    offsets = {mid: 0 for mid in active_pooled_mids}

    def _consume_pooled_alloc(alloc):
        """Take ranked slices from models 2–6 and advance offsets."""
        moved = False
        for mid in sorted(alloc.keys(), key=lambda x: int(x)):
            n_take = alloc[mid]
            if n_take <= 0:
                continue
            src = model_results.get(mid)
            if src is None or src.empty:
                continue
            start = offsets[mid]
            avail = len(src) - start
            take = min(n_take, avail)
            if take <= 0:
                continue
            moved = True
            raw = src.iloc[start : start + take]
            offsets[mid] += take
            print(f"  Model {mid}: ranked slice {take:,} rows")
            chunks_by_mid[mid].append(raw.copy())
        return moved

    def _assemble_dedup_label():
        dfs_to_concat = []
        if df1 is not None and not df1.empty:
            d = df1.copy()
            d["SOURCE_MODEL"] = "MODEL1"
            dfs_to_concat.append(d)
        for mid in sorted(chunks_by_mid.keys(), key=int):
            for chunk in chunks_by_mid[mid]:
                if chunk.empty:
                    continue
                c = chunk.copy()
                c["SOURCE_MODEL"] = f"MODEL{mid}"
                dfs_to_concat.append(c)

        if not dfs_to_concat:
            return pd.DataFrame()

        all_columns = set()
        for df in dfs_to_concat:
            all_columns.update(df.columns)

        for i, df in enumerate(dfs_to_concat):
            for col in all_columns:
                if col not in df.columns:
                    df[col] = pd.NA
            dfs_to_concat[i] = df[sorted(all_columns)]

        out = pd.concat(dfs_to_concat, ignore_index=True)
        print(f"  Combined rows before dedup: {len(out):,}")

        _lk = out["DOT_NUMBER"].apply(_dot_label_key)
        _mid = out["SOURCE_MODEL"].apply(_mid_from_source_model)
        label_by_dot = {}
        mask = _lk.notna()
        if mask.any():
            _tmp = pd.DataFrame({"_lk": _lk[mask], "_mid": _mid[mask]})
            for dot_key, grp in _tmp.groupby("_lk", sort=False):
                mids_sorted = sorted(
                    {str(m) for m in grp["_mid"] if m is not None and str(m).strip()},
                    key=int,
                )
                label_by_dot[dot_key] = "_".join(mids_sorted) if mids_sorted else pd.NA
        out["LABEL"] = _lk.map(label_by_dot)

        out = out.drop_duplicates(subset=["DOT_NUMBER"], keep="first")
        print(f"  Rows after dedup: {len(out):,}")
        return out

    print(
        f"  Model 1 rows (x): {x_rows:,} | "
        f"Initial pooled ranked-slot budget ({MODEL_POOL_SIZE} - x): {pooled_budget:,}"
    )
    alloc0 = _allocate_pooled_row_counts(contrib_norm, pooled_budget)
    print(f"  Initial pooled targets (rank slots): { {k: alloc0.get(k, 0) for k in sorted(active_pooled_mids, key=int)} }")
    _consume_pooled_alloc(alloc0)

    combined_df = _assemble_dedup_label()
    if combined_df.empty:
        print("  WARNING: No model returned results")
        _record_successful_run()
        return pd.DataFrame()

    print("\n[5/5] Merging enrichment + email filter (all models)...")
    combined_df = _merge_enrichment_and_filter_email(combined_df, enrichment_df)

    top_up_round = 0
    while len(combined_df) < DEDUP_RECURSION_STOP_AT and top_up_round < MAX_POOL_TOPUP_ROUNDS:
        prev_len = len(combined_df)
        shortfall = DEDUP_RECURSION_STOP_AT - prev_len
        alloc_extra = _allocate_pooled_row_counts(contrib_norm, shortfall)
        print(
            f"  Top-up round {top_up_round + 1}: need {shortfall:,} more email-valid rows "
            f"(target {DEDUP_RECURSION_STOP_AT:,}; alloc "
            f"{ {k: alloc_extra.get(k, 0) for k in sorted(active_pooled_mids, key=int)} })"
        )
        moved = _consume_pooled_alloc(alloc_extra)
        combined_df = _assemble_dedup_label()
        combined_df = _merge_enrichment_and_filter_email(combined_df, enrichment_df)
        top_up_round += 1
        if len(combined_df) <= prev_len:
            print(
                "  Top-up stopped: no gain in email-valid rows "
                "(duplicates or no usable email in new ranks)"
            )
            break
        if not moved:
            print("  Top-up stopped: no ranked rows left to take from pooled models")
            break

    # --- FINAL RANK ---
    combined_df = combined_df.reset_index(drop=True)
    combined_df["FINAL_RANK"] = combined_df.index + 1

    elapsed = _time.time() - t_start
    print("\n" + "=" * 60)
    print(f"COMBINED RUN COMPLETE: {len(combined_df):,} rows in {elapsed:.1f}s")
    print(f"Label distribution:")
    if "LABEL" in combined_df.columns:
        print(combined_df["LABEL"].value_counts().to_string())
    print("=" * 60)

    _record_successful_run()
    return combined_df
