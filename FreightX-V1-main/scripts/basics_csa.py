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

# Intervention Thresholds for Controlled Substances/Alcohol BASIC (General Carrier = 80%) [1]
INTERVENTION_THRESHOLD_GENERAL = 80.0 

# Controlled Substances/Alcohol Safety Event Groups (Based on Inspections with Violations) [2]
# Data sufficiency requires at least one violation inspection (Count >= 1).
CSA_GROUPS = {
    'S1': (1, 1), # 1 inspection with violation
    'S2': (2, 2), # 2 inspections with violations
    'S3': (3, 3), # 3 inspections with violations
    'S4': (4, np.inf) # 4 or more inspections with violations
}

# print(os.getcwd())

# os.chdir('/Users/siddhantmalhotra/Documents/cursor/mvp-scoring')

# Read CSV file
df_census = pd.read_csv(
    DATA_DIR / "Company_Census_File.csv",
    usecols=[
        'DOT_NUMBER',
        'DOCKET1','DOCKET1PREFIX',
        'DOCKET2','DOCKET2PREFIX',
        'DOCKET3','DOCKET3PREFIX',
        'CARRIER_OPERATION'
    ]
)

# Filter rows where column 'Status' == 'Active'

df1 = df_census[
    (df_census['DOCKET1PREFIX'].astype(str).str.strip() == 'MC')
][['DOT_NUMBER','DOCKET1','CARRIER_OPERATION']].copy()

df1['DOCKET1'] = pd.to_numeric(df1['DOCKET1'], errors='coerce')
df1 = df1.dropna(subset=['DOCKET1'])

df1['DOCKET_NUMBER'] = 'MC' + df1['DOCKET1'].astype(int).astype(str)


# DOCKET2
df2 = df_census[
    (df_census['DOCKET2PREFIX'].astype(str).str.strip() == 'MC')
][['DOT_NUMBER','DOCKET2','CARRIER_OPERATION']].copy()

df2['DOCKET2'] = pd.to_numeric(df2['DOCKET2'], errors='coerce')
df2 = df2.dropna(subset=['DOCKET2'])

df2['DOCKET_NUMBER'] = 'MC' + df2['DOCKET2'].astype(int).astype(str)


# DOCKET3
df3 = df_census[
    (df_census['DOCKET3PREFIX'].astype(str).str.strip() == 'MC')
][['DOT_NUMBER','DOCKET3','CARRIER_OPERATION']].copy()

df3['DOCKET3'] = pd.to_numeric(df3['DOCKET3'], errors='coerce')
df3 = df3.dropna(subset=['DOCKET3'])

df3['DOCKET_NUMBER'] = 'MC' + df3['DOCKET3'].astype(int).astype(str)


# COMBINE
df_census = pd.concat([
    df1[['DOT_NUMBER','DOCKET_NUMBER','CARRIER_OPERATION']],
    df2[['DOT_NUMBER','DOCKET_NUMBER','CARRIER_OPERATION']],
    df3[['DOT_NUMBER','DOCKET_NUMBER','CARRIER_OPERATION']]
], ignore_index=True)

df_census = df_census.drop_duplicates(subset=['DOT_NUMBER','DOCKET_NUMBER'])

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

df_csa_cohort = df_combined[df_combined['CARRIER_OPERATION'].isin(['A', 'B'])].copy()


df_csa_cohort['CONTR_SUBST_INSP_W_VIOL'] = pd.to_numeric(df_csa_cohort['CONTR_SUBST_INSP_W_VIOL'], errors='coerce').fillna(0)


# --- STAGE 3 & 4: GROUPING AND DATA SUFFICIENCY ---

def assign_csa_event_group(row):
    """
    Assigns the Controlled Substances/Alcohol Safety Event Group based on the 
    count of inspections with applicable violations, and checks for sufficiency.
    """
    viol_insp_count = row['CONTR_SUBST_INSP_W_VIOL']
    
    # Data Sufficiency Check: Remove carriers with no violations in this BASIC [2].
    if viol_insp_count < 1:
        return 'INSUFFICIENT DATA'
    
    # Assign the carrier to one of the 4 safety event groups (tiers)
    for group, (low, high) in CSA_GROUPS.items():
        # Handle the 4+ case specifically for the upper boundary (np.inf)
        if low <= viol_insp_count and (high == np.inf or viol_insp_count <= high):
            return group

    return 'INSUFFICIENT DATA'

df_csa_cohort['CSA_GROUP'] = df_csa_cohort.apply(assign_csa_event_group, axis=1)

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
    measures = group['CONTR_SUBST_MEASURE']
    
    # 1. Rank measures in ascending order (higher measure = worse performance = higher percentile)
    ranks = rankdata(measures, method='min')
    N = len(ranks)
    
    # 2. Transform rank to percentile (0 to 100 scale)
    percentiles = (ranks - 1) / (N - 1) * 100
    
    return pd.Series(percentiles, index=group.index)

# Group the population by the derived peer group and apply the ranking function
df_csa_cohort['CSA_PERCENTILE'] = df_csa_cohort.groupby('CSA_GROUP').apply(calculate_percentile).reset_index(level=0, drop=True)


print("\n#####################################################################")
print("## FINAL RESULTS: CONTROLLED SUBSTANCES/ALCOHOL BASIC PERCENTILE ##")
print("#####################################################################")
print(df_csa_cohort[['DOT_NUMBER','DOCKET_NUMBER', 'CONTR_SUBST_INSP_W_VIOL', 'CSA_GROUP', 
                   'CONTR_SUBST_MEASURE', 'CSA_PERCENTILE', 'CONTR_SUBST_AC', 
                   ]].sort_values(by='DOCKET_NUMBER'))




df_csa_cohort[['DOT_NUMBER','DOCKET_NUMBER', 'DOT_NUMBER' ,'CONTR_SUBST_INSP_W_VIOL', 'CSA_GROUP', 
                   'CONTR_SUBST_MEASURE', 'CSA_PERCENTILE', 'CONTR_SUBST_AC' 
                   ]].sort_values(by='DOCKET_NUMBER').to_csv(DATA_DIR / "df_csa.csv")