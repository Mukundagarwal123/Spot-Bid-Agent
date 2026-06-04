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

# Intervention Thresholds for HOS Compliance BASIC (General Carrier = 65%) [3]
INTERVENTION_THRESHOLD_GENERAL = 65.0 

# HOS Compliance Safety Event Groups (Based on Number of Relevant Inspections) [567, Table 3–12]
HOS_GROUPS = {
    'H1': (3, 10),
    'H2': (11, 20),
    'H3': (21, 100),
    'H4': (101, 500),
    'H5': (501, np.inf)
}



# print(os.getcwd())

# os.chdir('/Users/siddhantmalhotra/Documents/cursor/mvp-scoring')

# Read CSV file
df_sms_raw = pd.read_csv(DATA_DIR / "SMS_AB_PassProperty.csv")

# Filter rows where column 'Status' == 'Active'

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

# DOCKET1
df1 = df_census[
    (df_census['DOCKET1PREFIX'].astype(str).str.strip() == 'MC') &
    (df_census['DOCKET1'].notna())
][['DOT_NUMBER','DOCKET1','CARRIER_OPERATION']].copy()

df1['DOCKET1'] = pd.to_numeric(df1['DOCKET1'], errors='coerce')
df1 = df1.dropna(subset=['DOCKET1'])

df1['DOCKET_NUMBER'] = 'MC' + df1['DOCKET1'].astype(int).astype(str)

# DOCKET2


df2 = df_census[
    (df_census['DOCKET2PREFIX'].astype(str).str.strip() == 'MC') &
    (df_census['DOCKET2'].notna())
][['DOT_NUMBER','DOCKET2','CARRIER_OPERATION']].copy()

df2['DOCKET2'] = pd.to_numeric(df2['DOCKET2'], errors='coerce')
df2 = df2.dropna(subset=['DOCKET2'])

df2['DOCKET_NUMBER'] = 'MC' + df2['DOCKET2'].astype(int).astype(str)


# DOCKET3
df3 = df_census[
    (df_census['DOCKET3PREFIX'].astype(str).str.strip() == 'MC') &
    (df_census['DOCKET3'].notna())
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
df_hos_cohort = df_combined[df_combined['CARRIER_OPERATION'].isin(['A', 'B'])].copy()



def assign_hos_event_group(row):
    """
    Assigns the HOS Safety Event Group based on the total relevant inspections, 
    and checks for data sufficiency requirements.
    """
    relevant_insp_count = row['DRIVER_INSP_TOTAL']
    # Meaning: Number of driver inspections on that carrier 

    viol_insp_count = row['HOS_DRIV_INSP_W_VIOL']
    # Meaning: Number of driver inspections that resulted in an HOS violation
    
    # HOS Data Sufficiency Check: Remove carriers with (1) less than three relevant driver inspections, 
    # OR (2) no inspections resulting in at least one BASIC violation [7]
    if relevant_insp_count < 3 or viol_insp_count == 0:
        return 'INSUFFICIENT DATA'
    
    # Assign the carrier to one of the 5 safety event groups (tiers)
    for group, (low, high) in HOS_GROUPS.items():
        if low <= relevant_insp_count <= high:
            return group
        
    # Catch cases above the highest defined group (501+)
    if relevant_insp_count > HOS_GROUPS['H5']:
        return 'H5'

    return 'INSUFFICIENT DATA'

df_hos_cohort['HOS_GROUP'] = df_hos_cohort.apply(assign_hos_event_group, axis=1)

# --- STEP 5: PERCENTILE CALCULATION (Ranking the Measure within the Group) ---

def calculate_percentile(group):
    """
    Ranks BASIC Measures within a specific Safety Event Group (peer group).
    Ranks are ascending (0=best performance, 100=worst performance).
    """
    # Exclude non-calculable rows (e.g., single row group)
    if len(group) <= 1:
        return pd.Series(np.nan, index=group.index)

    measures = group['HOS_DRIV_MEASURE']
    
    # 1. Rank measures in ascending order (where higher score indicates worse performance)
    ranks = rankdata(measures, method='min')
    N = len(ranks)
    
    # 2. Transform rank to percentile (0 to 100 scale)
    percentiles = (ranks - 1) / (N - 1) * 100
    
    return pd.Series(percentiles, index=group.index)

# Group the population by the derived peer group and apply the ranking function
df_hos_cohort['HOS_PERCENTILE'] = df_hos_cohort.groupby('HOS_GROUP').apply(calculate_percentile).reset_index(level=0, drop=True)


print("\n#####################################################################")
print("## FINAL RESULTS: HOS COMPLIANCE BASIC PERCENTILE AND STATUS ##")
print("#####################################################################")
print(df_hos_cohort[['DOT_NUMBER','DOCKET_NUMBER', 'DRIVER_INSP_TOTAL', 'HOS_DRIV_INSP_W_VIOL', 'HOS_GROUP', 
                   'HOS_DRIV_MEASURE', 'HOS_PERCENTILE', 'HOS_DRIV_AC', 
                   ]].sort_values(by='DOCKET_NUMBER'))

df_hos_cohort[['DOT_NUMBER','DOCKET_NUMBER', 'DRIVER_INSP_TOTAL', 'HOS_DRIV_INSP_W_VIOL', 'HOS_GROUP', 
                   'HOS_DRIV_MEASURE', 'HOS_PERCENTILE', 'HOS_DRIV_AC', 
                   ]].sort_values(by='DOCKET_NUMBER').to_csv(DATA_DIR / "df_hos.csv")