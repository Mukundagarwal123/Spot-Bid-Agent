import pandas as pd
import numpy as np
from scipy.stats import rankdata

import warnings
warnings.filterwarnings("ignore")
import os

from functools import reduce
from pathlib import Path
import re

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BASICS_CSV_NAMES = ("df_ud.csv", "df_hos.csv", "df_vm.csv", "df_csa.csv", "df_df.csv")


def clean_dot(x):
    if pd.isna(x):
        return None
    x = str(x).strip()
    if x.endswith(".0"):
        x = x[:-2]
    x = x.lstrip("0")
    return x if x != "" else None

def clean_docket(x):
    if pd.isna(x):
        return None
    x = str(x).strip().upper()
    if not x.startswith("MC"):
        x = "MC" + x.replace("MC", "")
    return x

# --- STEP 1: CONSTANTS AND GROUPING RULES (From SMS Methodology) ---

# Intervention Thresholds for Driver Fitness BASIC (General Carrier = 80%) [3, 4]
INTERVENTION_THRESHOLD_GENERAL = 80.0 

# Driver Fitness Safety Event Groups (Based on Number of Relevant Inspections) [2]
# Relevant Inspection count must be >= 5 for sufficiency.
DF_GROUPS = {
    'D1': (5, 10),
    'D2': (11, 20),
    'D3': (21, 100),
    'D4': (101, 500),
    'D5': (501, np.inf) # 501+ relevant inspections
}


# print(os.getcwd())

# os.chdir('/Users/siddhantmalhotra/Documents/cursor/mvp-scoring')

# Read CSV file
df_census = pd.read_csv(DATA_DIR / "Company_Census_File.csv")

# Filter rows where column 'Status' == 'Active'
rows = []

for _, row in df_census.iterrows():

    if pd.notna(row.get('DOCKET1')) and str(row.get('DOCKET1PREFIX')).strip() == 'MC':
        rows.append({**row, 'DOCKET_NUMBER': f"MC{int(float(row['DOCKET1']))}"})

    if pd.notna(row.get('DOCKET2')) and str(row.get('DOCKET2PREFIX')).strip() == 'MC':
        rows.append({**row, 'DOCKET_NUMBER': f"MC{int(float(row['DOCKET2']))}"})

    if pd.notna(row.get('DOCKET3')) and str(row.get('DOCKET3PREFIX')).strip() == 'MC':
        rows.append({**row, 'DOCKET_NUMBER': f"MC{int(float(row['DOCKET3']))}"})

df_census = pd.DataFrame(rows)

df_census['DOT_NUMBER'] = df_census['DOT_NUMBER'].apply(clean_dot).astype('string')
df_census['DOCKET_NUMBER'] = df_census['DOCKET_NUMBER'].apply(clean_docket).astype('string')

df_sms_raw = pd.read_csv(DATA_DIR / "SMS_AB_PassProperty.csv")
df_sms_raw['DOT_NUMBER'] = df_sms_raw['DOT_NUMBER'].apply(clean_dot).astype('string')

dot_docket_map = (
    df_census[['DOT_NUMBER','DOCKET_NUMBER']]
    .dropna()
    .drop_duplicates()
)

df_sms_raw = df_sms_raw.merge(
    dot_docket_map,
    on='DOT_NUMBER',
    how='left'
)


# 3.1 Merge Dataframes
df_combined = df_sms_raw.merge(df_census, on=['DOT_NUMBER','DOCKET_NUMBER'], how='left')

print(df_combined.shape)

df_df_cohort = df_combined[df_combined['CARRIER_OPERATION'].isin(['A', 'B'])].copy()


# Ensure count fields are numeric and handle potential NaNs
df_df_cohort['DRIVER_INSP_TOTAL'] = pd.to_numeric(df_df_cohort['DRIVER_INSP_TOTAL'], errors='coerce').fillna(0)
df_df_cohort['DRIV_FIT_INSP_W_VIOL'] = pd.to_numeric(df_df_cohort['DRIV_FIT_INSP_W_VIOL'], errors='coerce').fillna(0)


# --- STAGE 3 & 4: GROUPING AND DATA SUFFICIENCY ---

def assign_df_event_group(row):
    """
    Assigns the Driver Fitness Safety Event Group based on total relevant inspections, 
    and checks for data sufficiency (min 5 relevant inspections AND min 1 inspection with violation).
    """
    relevant_insp_count = row['DRIVER_INSP_TOTAL']
    viol_insp_count = row['DRIV_FIT_INSP_W_VIOL']
    
    # DF Data Sufficiency Check: Remove carriers with (1) less than five relevant driver inspections [10]
    # OR (2) no inspections resulting in at least one BASIC violation [10].
    if relevant_insp_count < 5 or viol_insp_count == 0:
        return 'INSUFFICIENT DATA'
    
    # Assign the carrier to one of the 5 safety event groups (tiers) based on inspection count [2]
    for group, (low, high) in DF_GROUPS.items():
        if low <= relevant_insp_count <= high:
            return group
        
    # Handle cases above the highest defined group (D5: 501+)
    if relevant_insp_count > DF_GROUPS['D5']:
        return 'D5'

    return 'INSUFFICIENT DATA'

df_df_cohort['DF_GROUP'] = df_df_cohort.apply(assign_df_event_group, axis=1)

# --- STEP 5.1: PERCENTILE CALCULATION (Ranking the Measure within the Group) ---

def calculate_percentile(group):
    """
    Ranks BASIC Measures within a specific Safety Event Group (peer group).
    Ranks are ascending (0=best performance, 100=worst performance).
    """
    
    # Exclude groups that are too small for ranking (N<=1)
    if len(group) <= 1:
        return pd.Series(np.nan, index=group.index)

    # Use the raw Measure Value for ranking
    measures = group['DRIV_FIT_MEASURE']
    
    # 1. Rank measures in ascending order (higher measure = worse performance = higher percentile)
    ranks = rankdata(measures, method='min')
    N = len(ranks)
    
    # 2. Transform rank to percentile (0 to 100 scale)
    percentiles = (ranks - 1) / (N - 1) * 100
    
    return pd.Series(percentiles, index=group.index)

# Group the population by the derived peer group and apply the ranking function
df_df_cohort['DF_PERCENTILE'] = df_df_cohort.groupby('DF_GROUP').apply(calculate_percentile).reset_index(level=0, drop=True)


print("\n#####################################################################")
print("## FINAL RESULTS: DRIVER FITNESS BASIC PERCENTILE AND STATUS ##")
print("#####################################################################")
print(df_df_cohort[['DOCKET_NUMBER', 'DRIVER_INSP_TOTAL', 'DRIV_FIT_INSP_W_VIOL', 'DF_GROUP', 
                   'DRIV_FIT_MEASURE', 'DF_PERCENTILE', 'DRIV_FIT_AC', 
                   ]].sort_values(by='DOCKET_NUMBER'))


df_df_cohort[['DOT_NUMBER','DOCKET_NUMBER', 'DRIVER_INSP_TOTAL', 'DRIV_FIT_INSP_W_VIOL', 'DF_GROUP', 
                   'DRIV_FIT_MEASURE', 'DF_PERCENTILE', 'DRIV_FIT_AC', 
                   ]].sort_values(by='DOCKET_NUMBER').to_csv(DATA_DIR / "df_df.csv")



# os.chdir('/Users/siddhantmalhotra/Documents/cursor/mvp-scoring')

DATA_DIR.mkdir(parents=True, exist_ok=True)
csv_files = [str(DATA_DIR / name) for name in BASICS_CSV_NAMES if (DATA_DIR / name).is_file()]

if len(csv_files) == 0:
    raise SystemExit("No CSV files found in folder_path")

dfs = []
for fp in csv_files:
    p = Path(fp)
    stem = p.stem  # filename without extension, used as prefix
    df = pd.read_csv(fp, dtype=object)   # read as object to avoid type surprises

    df['DOT_NUMBER'] = df['DOT_NUMBER'].apply(clean_dot).astype('string')
    df['DOCKET_NUMBER'] = df['DOCKET_NUMBER'].apply(clean_docket).astype('string')

    # 🔥 ENSURE REQUIRED KEYS EXIST
    if "DOT_NUMBER" not in df.columns:
        raise KeyError(f"DOT_NUMBER missing in file: {fp}")

    if "DOCKET_NUMBER" not in df.columns:
        raise KeyError(f"DOCKET_NUMBER missing in file: {fp}")



    # 1) drop index-like columns created by pandas such as "Unnamed: 0", "Unnamed: 0.1", etc.
    unnamed_cols = [c for c in df.columns if re.match(r"^Unnamed", str(c))]
    if unnamed_cols:
        df = df.drop(columns=unnamed_cols)

    # 2) Normalize/strip column names (optional but helpful)
    df.columns = [str(c).strip() for c in df.columns]

    # 3) Ensure DOT_NUMBER column exists (case-sensitive). If it's named slightly differently, try a tolerant match.
    if "DOCKET_NUMBER" not in df.columns:
        # try case-insensitive matching:
        matches = [c for c in df.columns if c.strip().lower() == "docket_number".lower()]
        if matches:
            df = df.rename(columns={matches[0]: "DOCKET_NUMBER"})
        else:
            raise KeyError(f"'DOCKET_NUMBER' column not found in file: {fp}. Columns: {list(df.columns)}")

    # # 4) Prefix all columns except DOT_NUMBER with filename stem to avoid duplicate column names
    # new_cols = {}
    # for c in df.columns:
    #     if c == "DOCKET_NUMBER":
    #         new_cols[c] = c
    #     else:
    #         new_cols[c] = f"{stem}__{c}"
    # df = df.rename(columns=new_cols)

    # 5) Optionally drop duplicate DOT_NUMBER rows inside a file (if any)
    df = df.drop_duplicates(subset=["DOT_NUMBER","DOCKET_NUMBER"], keep="first")

    dfs.append(df)

# 6) Merge all dataframes on DOT_NUMBER using outer join
merged = reduce(
    lambda left, right: pd.merge(
        left,
        right,
        on=["DOT_NUMBER","DOCKET_NUMBER"],
        how="outer",
        validate="one_to_one"
    ),
    dfs
)

# 7) Save result
out_path = DATA_DIR / "merged_data.csv"
merged.to_csv(out_path, index=False)
print("Merged saved to:", out_path)
print("Merged shape:", merged.shape)
