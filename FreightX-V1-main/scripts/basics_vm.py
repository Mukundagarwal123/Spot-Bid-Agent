import pandas as pd
import numpy as np
from scipy.stats import rankdata
import warnings
warnings.filterwarnings("ignore")
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


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

# Intervention Thresholds for Vehicle Maintenance BASIC (General Carrier = 80%) [2, 3]
INTERVENTION_THRESHOLD_GENERAL = 80.0 

# Vehicle Maintenance Safety Event Groups (Based on Number of Relevant Inspections) [4]
# Relevant Inspection count must be >= 5 for sufficiency [5].
VM_GROUPS = {
    'V1': (5, 10),
    'V2': (11, 20),
    'V3': (21, 100),
    'V4': (101, 500),
    'V5': (501, np.inf) # 501+ relevant inspections
}


# print(os.getcwd())

# os.chdir('/Users/siddhantmalhotra/Documents/cursor/mvp-scoring')

# Read CSV file
df_census = pd.read_csv(DATA_DIR / "Company_Census_File.csv")

rows = []

for _, row in df_census.iterrows():

    if pd.notna(row.get('DOCKET1')) and str(row.get('DOCKET1PREFIX')).strip() == 'MC':
        rows.append({**row, 'DOCKET_NUMBER': f"MC{int(float(row['DOCKET1']))}"})

    if pd.notna(row.get('DOCKET2')) and str(row.get('DOCKET2PREFIX')).strip() == 'MC':
        rows.append({**row, 'DOCKET_NUMBER': f"MC{int(float(row['DOCKET2']))}"})

    if pd.notna(row.get('DOCKET3')) and str(row.get('DOCKET3PREFIX')).strip() == 'MC':
        rows.append({**row, 'DOCKET_NUMBER': f"MC{int(float(row['DOCKET3']))}"})

df_census = pd.DataFrame(rows)

# CLEAN KEYS
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
df_combined = df_sms_raw.merge(
    df_census,
    on=['DOT_NUMBER','DOCKET_NUMBER'],
    how='left'
)

print(df_combined.shape)

df_vm_cohort = df_combined[df_combined['CARRIER_OPERATION'].isin(['A', 'B'])].copy()


# Ensure count fields are numeric and handle potential NaNs
df_vm_cohort['VEHICLE_INSP_TOTAL'] = pd.to_numeric(df_vm_cohort['VEHICLE_INSP_TOTAL'], errors='coerce').fillna(0)
df_vm_cohort['VEH_MAINT_INSP_W_VIOL'] = pd.to_numeric(df_vm_cohort['VEH_MAINT_INSP_W_VIOL'], errors='coerce').fillna(0)


# --- STAGE 3 & 4: GROUPING AND DATA SUFFICIENCY ---

def assign_vm_event_group(row):
    """
    Assigns the Vehicle Maintenance Safety Event Group based on total relevant inspections, 
    and checks for data sufficiency (min 5 inspections AND min 1 inspection with violation).
    """
    relevant_insp_count = row['VEHICLE_INSP_TOTAL']
    viol_insp_count = row['VEH_MAINT_INSP_W_VIOL']
    
    # VM Data Sufficiency Check: Remove carriers with (1) less than five relevant inspections [5]
    # OR (2) no inspections resulting in at least one BASIC violation [5].
    if relevant_insp_count < 5 or viol_insp_count == 0:
        return 'INSUFFICIENT DATA'
    
    # Assign the carrier to one of the 5 safety event groups (tiers) [4]
    for group, (low, high) in VM_GROUPS.items():
        if low <= relevant_insp_count <= high:
            return group
        
    # Handle cases above the highest defined group (V5: 501+)
    if relevant_insp_count > VM_GROUPS['V5']:
        return 'V5'

    return 'INSUFFICIENT DATA'

df_vm_cohort['VM_GROUP'] = df_vm_cohort.apply(assign_vm_event_group, axis=1)

# --- STEP 5.1: PERCENTILE CALCULATION (Ranking the Measure within the Group) ---

def calculate_percentile(group):
    """
    Ranks BASIC Measures within a specific Safety Event Group (peer group).
    Ranks are ascending (0=best performance, 100=worst performance).
    """
    
    # Exclude groups that are too small for ranking (N<=1)
    if len(group) <= 1:
        return pd.Series(np.nan, index=group.index)

    # Use the raw Measure Value for ranking [4]
    measures = group['VEH_MAINT_MEASURE']
    
    # 1. Rank measures in ascending order (higher measure = worse performance = higher percentile)
    ranks = rankdata(measures, method='min')
    N = len(ranks)
    
    # 2. Transform rank to percentile (0 to 100 scale)
    percentiles = (ranks - 1) / (N - 1) * 100
    
    return pd.Series(percentiles, index=group.index)

# Group the population by the derived peer group and apply the ranking function
df_vm_cohort['VM_PERCENTILE'] = df_vm_cohort.groupby('VM_GROUP').apply(calculate_percentile).reset_index(level=0, drop=True)

print("\n#####################################################################")
print("## FINAL RESULTS: VEHICLE MAINTENANCE BASIC PERCENTILE AND STATUS ##")
print("#####################################################################")
print(df_vm_cohort[['DOT_NUMBER','DOCKET_NUMBER', 'VEHICLE_INSP_TOTAL', 'VEH_MAINT_INSP_W_VIOL', 'VM_GROUP', 
                   'VEH_MAINT_MEASURE', 'VM_PERCENTILE', 'VEH_MAINT_AC', 
                ]].sort_values(by='DOCKET_NUMBER'))

df_vm_cohort[['DOT_NUMBER','DOCKET_NUMBER', 'VEHICLE_INSP_TOTAL', 'VEH_MAINT_INSP_W_VIOL', 'VM_GROUP', 
                   'VEH_MAINT_MEASURE', 'VM_PERCENTILE', 'VEH_MAINT_AC', 
                ]].sort_values(by='DOCKET_NUMBER').to_csv(DATA_DIR / "df_vm.csv")