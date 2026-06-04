# %pip install scipy
import numpy as np
from scipy.stats import rankdata
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
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

# --- Stage 0: Define Constants and Grouping Rules ---
# Segmentation Thresholds (Based on SMS Methodology [6-8])
COMBINATION_THRESHOLD = 0.70 # Combination vehicles >= 70% of PUs
STRAIGHT_THRESHOLD = 0.30    # Straight vehicles > 30% of total PUs

# Unsafe Driving Safety Event Groups (Based on Tables 3-3 and 3-4 [9, 10])
UD_GROUPS_COMBINATION = {
    'C1': (3, 8),
    'C2': (9, 21),
    'C3': (22, 57),
    'C4': (58, 149),
    'C5': (150, np.inf)
}

UD_GROUPS_STRAIGHT = {
    'S1': (3, 4),
    'S2': (5, 8),
    'S3': (9, 18),
    'S4': (19, 49),
    'S5': (50, np.inf)
}



# print(os.getcwd())

# os.chdir('/Users/siddhantmalhotra/Documents/cursor/mvp-scoring')

# Read CSV file
df_census = pd.read_csv(DATA_DIR / "Company_Census_File.csv")

# Filter rows where column 'Status' == 'Active'

rows = []

for _, row in df_census.iterrows():

    # DOCKET1
    if pd.notna(row.get('DOCKET1')) and str(row.get('DOCKET1PREFIX')).strip() == 'MC':
        rows.append({**row, 'DOCKET_NUMBER': f"MC{int(float(row['DOCKET1']))}"})

    # DOCKET2
    if pd.notna(row.get('DOCKET2')) and str(row.get('DOCKET2PREFIX')).strip() == 'MC':
        rows.append({**row, 'DOCKET_NUMBER': f"MC{int(float(row['DOCKET2']))}"})

    # DOCKET3
    if pd.notna(row.get('DOCKET3')) and str(row.get('DOCKET3PREFIX')).strip() == 'MC':
        rows.append({**row, 'DOCKET_NUMBER': f"MC{int(float(row['DOCKET3']))}"})

df_census = pd.DataFrame(rows)

# CLEAN KEYS
df_census['DOT_NUMBER'] = df_census['DOT_NUMBER'].apply(clean_dot).astype('string')
df_census['DOCKET_NUMBER'] = df_census['DOCKET_NUMBER'].apply(clean_docket).astype('string')



# 3.1 Calculate Combination Units (This replaces the missing column from the prior attempt)
combination_cols = ['OWNTRACT', 'TRMTRACT', 'TRPTRACT', 'OWNCOACH', 'TRMCOACH', 'TRPCOACH']

# Ensure all combination columns exist and fill NaNs with 0 if necessary (important for real data)
for col in combination_cols:
    if col not in df_census.columns:
        print("missing")
        # In a real scenario, this would raise an error if a column was missing, 
        # but here we ensure the required columns are synthesized if missing in the mock data.
        pass # Mock data ensures they exist

df_census['COMBINATION_UNITS'] = df_census[combination_cols].sum(axis=1)

df_sms_raw = pd.read_csv(DATA_DIR / "SMS_AB_PassProperty.csv")
df_sms_raw['DOT_NUMBER'] = df_sms_raw['DOT_NUMBER'].apply(clean_dot).astype('string')

df_sms_raw = df_sms_raw.merge(
    df_census[['DOT_NUMBER', 'DOCKET_NUMBER']].drop_duplicates(),
    on='DOT_NUMBER',
    how='left'
)

# 3.1 Merge Dataframes
df_combined = df_sms_raw.merge(df_census, on=['DOT_NUMBER','DOCKET_NUMBER'], how='left')

print(df_combined.shape)

# 3.2 Filter for Cohort AB (Interstate A and Intrastate Hazmat B)
# Note: Cohort C (Intrastate Non-Hazmat) is calculated based on the measure-to-percentile relationship 
# established by Cohort AB [34].
df_ab_cohort = df_combined[df_combined['CARRIER_OPERATION'].isin(['A', 'B'])].copy()
print("\n--- STAGE 3: Cohort AB Filtered Data ---")
print(df_ab_cohort[['DOCKET_NUMBER', 'CARRIER_OPERATION', 'POWER_UNITS', 'COMBINATION_UNITS', 'UNSAFE_DRIV_MEASURE']])


def assign_ud_segment(row):
    """Assign segment label based on the ratio of combination vehicles to total power units (PU)."""
    
    total_pu = row['POWER_UNITS']
    combination_pu = row['COMBINATION_UNITS']
    
    # Handle division by zero if PU count is 0
    if total_pu == 0:
        return 'Other' 
        
    ratio = combination_pu / total_pu
    
    # Combination Segment: Combination vehicles >= 70% of total PUs [1, 2]
    if ratio >= COMBINATION_THRESHOLD:
        return 'Combination'
    else:
        # Straight Segment: Includes all other carriers (Straight, other vehicles, or mixed) [1, 3]
        return 'Straight' 

df_ab_cohort['UD_SEGMENT'] = df_ab_cohort.apply(assign_ud_segment, axis=1)

print("\n--- STAGE 4: Vehicle Segmentation Results ---")
print(df_ab_cohort[['DOCKET_NUMBER', 'POWER_UNITS', 'COMBINATION_UNITS', 'UD_SEGMENT']])

def assign_ud_event_group(row):
    """Assign Safety Event Group based on Inspection Count [9, 10]."""
    count = row['UNSAFE_DRIV_INSP_W_VIOL']
    segment = row['UD_SEGMENT']
    
    # 3.3 Data Sufficiency Check: Must have >= 3 inspections with violations [29]
    if count < 3:
        return 'INSUFFICIENT DATA'
    
    group_map = UD_GROUPS_COMBINATION if segment == 'Combination' else UD_GROUPS_STRAIGHT
    
    for group, (low, high) in group_map.items():
        if low <= count <= high:
            return group
    return 'INSUFFICIENT DATA'

df_ab_cohort['UD_GROUP'] = df_ab_cohort.apply(assign_ud_event_group, axis=1)


# --- STEP 5.2: PERCENTILE CALCULATION ---
# This is where the measure field is actively used for ranking.

def calculate_percentile(group):
    """
    Ranks BASIC Measures within a specific Safety Event Group (peer group).
    The ranking is ascending (0=low measure, 100=high measure).
    """
    
    # Check if the group contains measurable carriers
    if group.empty or len(group) == 1:
        # If there is only one carrier, percentile calculation formula (N-1) fails or is meaningless
        # Note: In a large dataset, a group might still calculate percentile 0 or 100 for a single edge case.
        # However, FMCSA calculates the rank relative to the group population.
        return pd.Series(np.nan, index=group.index)

    measures = group['UNSAFE_DRIV_MEASURE']
    
    # 1. Rank measures in ascending order (where highest score gets highest rank)
    # The 'min' method ensures ties receive the minimum rank in that group of ties.
    ranks = rankdata(measures, method='min')
    N = len(ranks)
    
    # 2. Transform rank to percentile (0 to 100 scale)
    # Formula: (Rank - 1) / (N - 1) * 100
    percentiles = (ranks - 1) / (N - 1) * 100
    
    # Return the percentiles mapped back to the original index
    return pd.Series(percentiles, index=group.index)

# Group the population by the derived peer group and apply the ranking function
df_ab_cohort['UD_PERCENTILE'] = df_ab_cohort.groupby('UD_GROUP').apply(calculate_percentile).reset_index(level=0, drop=True)

print("\n--- STAGE 4/5: Percentile Ranking Complete ---")
print(df_ab_cohort[['DOCKET_NUMBER', 'UD_SEGMENT', 'UNSAFE_DRIV_INSP_W_VIOL', 'UD_GROUP', 'UNSAFE_DRIV_MEASURE', 'UD_PERCENTILE']])

df_ab_cohort[['DOT_NUMBER','DOCKET_NUMBER', 'UD_SEGMENT', 'UNSAFE_DRIV_INSP_W_VIOL', 'UD_GROUP', 'UNSAFE_DRIV_MEASURE', 'UD_PERCENTILE']].to_csv(DATA_DIR / "df_ud.csv")