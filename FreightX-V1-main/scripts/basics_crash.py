import pandas as pd
import numpy as np
from scipy.stats import rankdata
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")
import os
# --- CONSTANTS DEFINED BY SMS METHODOLOGY ---

# Time Window (24 months)
MEASUREMENT_WINDOW_DAYS = 730 

# Segmentation Thresholds (Section 2.6 / 3.1) [5, 6]
COMBINATION_THRESHOLD = 0.70 

# Crash Indicator Intervention Threshold (General Carrier = 65%) [7, 8]
INTERVENTION_THRESHOLD_GENERAL = 65.0 

# Data Sufficiency: Must have >= 2 applicable crashes [9]
CRASH_SUFFICIENCY_THRESHOLD = 2

# Crash Indicator Safety Event Groups (Tables 3-9, 3-10) [9, 10]
CRASH_GROUPS_COMBINATION = {
    'C1': (2, 3),
    'C2': (4, 6),
    'C3': (7, 16),
    'C4': (17, 45),
    'C5': (46, np.inf)
}

CRASH_GROUPS_STRAIGHT = {
    'S1': (2, 2),
    'S2': (3, 4),
    'S3': (5, 8),
    'S4': (9, 26),
    'S5': (27, np.inf)
}

# Utilization Factor Lookups (Tables 3-7, 3-8) [3, 4]
def calculate_utilization_factor(vmt_per_pu, segment):
    """Determines the Utilization Factor based on VMT per Average PU and carrier segment."""
    if pd.isna(vmt_per_pu) or vmt_per_pu <= 0:
        return 1.0 # No Recent VMT Information [1, 2, 4]

    if segment == 'Combination':
        if vmt_per_pu < 80000:
            return 1.0
        elif 80000 <= vmt_per_pu <= 160000:
            # Formula: 1 + (VMT per Average PU - 80,000) / 133,333 [1, 3]
            return 1.0 + (vmt_per_pu - 80000) / 133333.0
        elif 160000 < vmt_per_pu <= 200000:
            return 1.6
        elif vmt_per_pu > 200000:
            return 1.0
        
    elif segment == 'Straight':
        if vmt_per_pu < 20000:
            return 1.0
        elif 20000 <= vmt_per_pu <= 60000:
            # Formula: VMT per Average PU / 20,000 [2, 4]
            return vmt_per_pu / 20000.0
        elif 60000 < vmt_per_pu <= 200000:
            return 3.0
        elif vmt_per_pu > 200000:
            return 1.0
            
    return 1.0 # Default if segment logic fails or VMT is missing


def assign_crash_segment(row):
    """Assign segment label ('Combination' or 'Straight') based on vehicle mix (70% threshold)."""
    total_pu = row['POWER_UNITS']
    combination_pu = row['COMBINATION_UNITS']
    
    if total_pu == 0 or pd.isna(total_pu):
        return 'Other' 
        
    ratio = combination_pu / total_pu
    
    # Combination Segment: Combination vehicles >= 70% of total PUs [5, 6]
    if ratio >= COMBINATION_THRESHOLD:
        return 'Combination'
    else:
        # Straight Segment: All other carriers [5, 6]
        return 'Straight' 


df_census = pd.read_csv("C:/Users/HKans/OneDrive/Desktop/FreightX/codes/FreightX/data/Company_Census_File.csv")

# Filter rows where column 'Status' == 'Active'
df_census = df_census[df_census['DOCKET1PREFIX'] == 'MC']
df_census['DOCKET1'] = df_census['DOCKET1'].apply(lambda x: str(int(x)) if x.is_integer() else str(x))
df_census['DOCKET_NUMBER'] = df_census['DOCKET1PREFIX'] + df_census['DOCKET1']

df_sms_raw = pd.read_csv("C:/Users/HKans/OneDrive/Desktop/FreightX/codes/FreightX/data/SMS_AB_PassProperty.csv")

# 3.1 Merge Dataframes
df_combined = df_sms_raw.merge(df_census, on='DOT_NUMBER', how='left')

print(df_combined.shape)

df_csa_cohort = df_combined[df_combined['CARRIER_OPERATION'].isin(['A', 'B'])].copy()





# Mock the measurement date (This should be the date the SMS snapshot was taken)
MEASUREMENT_DATE = datetime(2024, 6, 30)

df_crash_raw = pd.read_csv("C:/Users/HKans/OneDrive/Desktop/FreightX/codes/FreightX/data/SMS_Input_-_Crash.csv")
# Convert dates and handle data types
df_crash_raw['REPORT_DATE'] = pd.to_datetime(df_crash_raw['Report_Date'], format='%Y%m%d', errors='coerce')
df_crash_raw['Time_Weight'] = pd.to_numeric(df_crash_raw['Time_Weight'], errors='coerce').fillna(0)
df_crash_raw['Severity_Weight'] = pd.to_numeric(df_crash_raw['Severity_Weight'], errors='coerce').fillna(0)

# --- Numerator Calculation (Weighted Crashes) ---

# 2.1 Filter Crashes by Time Window (24 months)
df_crash = df_crash_raw[
    (MEASUREMENT_DATE - df_crash_raw['REPORT_DATE']).dt.days <= MEASUREMENT_WINDOW_DAYS
].copy()

# 2.2 Exclude Not Preventable Crashes [12, 24, 25]
df_crash = df_crash[df_crash['Not_Preventable'] != 'TRUE'].copy()

# 2.3 Calculate Time and Severity Weighted Applicable Crashes [13]
df_crash['WEIGHTED_CRASH_SCORE'] = df_crash['Severity_Weight'] * df_crash['Time_Weight']

# 2.4 Sum Weighted Scores by DOT Number
df_numerator = df_crash.groupby('DOT_Number')['WEIGHTED_CRASH_SCORE'].sum().reset_index(name='CRASH_NUMERATOR')

# 2.5 Count Applicable Crashes for Grouping and Sufficiency
df_crash_counts = df_crash.groupby('DOT_Number').size().reset_index(name='CRASH_COUNT')
df_numerator = df_numerator.merge(df_crash_counts, on='DOT_Number', how='left')



# --- Merge Crash Numerator with Census Data ---
# 3.1 Calculate total Combination Units from Census input fields
combination_cols = ['OWNTRACT', 'TRMTRACT', 'TRPTRACT', 'OWNCOACH', 'TRMCOACH', 'TRPCOACH']
# Assuming census PU fields are handled as numeric, similar to prior BASICs
df_census['COMBINATION_UNITS'] = df_census[combination_cols].sum(axis=1)

df_census["DOT_Number"] = df_census["DOT_NUMBER"]
df_crash_cohort = df_numerator.merge(df_census, on='DOT_Number', how='left')

# Filter for Cohort AB (Interstate A and Intrastate Hazmat B)
df_crash_cohort = df_crash_cohort[df_crash_cohort['CARRIER_OPERATION'].isin(['A', 'B'])].copy()

# 3.2 Calculate Average PUs (Equation 3-4) [14]
# NOTE: This relies on assumed historical PU columns (PU_6_MONTHS_AGO, PU_18_MONTHS_AGO)
df_crash_cohort['AVERAGE_PUs'] =df_crash_cohort['POWER_UNITS']
#  (
#     df_crash_cohort['POWER_UNITS'] + 
#     df_crash_cohort['PU_6_MONTHS_AGO'] + 
#     df_crash_cohort['PU_18_MONTHS_AGO']
# ) / 3.0

# 3.3 Determine Carrier Segment [6]
df_crash_cohort['CRASH_SEGMENT'] = df_crash_cohort.apply(assign_crash_segment, axis=1)

# 3.4 Calculate VMT per Average PU [3]
# Handle potential division by zero
df_crash_cohort['VMT_PER_PU'] = np.where(
    df_crash_cohort['AVERAGE_PUs'] > 0,
    pd.to_numeric(df_crash_cohort['MCS150_MILEAGE'], errors='coerce') / df_crash_cohort['AVERAGE_PUs'],
    np.nan
)

# 3.5 Determine Utilization Factor [3, 4]
df_crash_cohort['UTILIZATION_FACTOR'] = df_crash_cohort.apply(
    lambda row: calculate_utilization_factor(row['VMT_PER_PU'], row['CRASH_SEGMENT']),
    axis=1
)

# 3.6 Calculate Exposure Factor (Denominator) [26]
df_crash_cohort['EXPOSURE_FACTOR'] = df_crash_cohort['AVERAGE_PUs'] * df_crash_cohort['UTILIZATION_FACTOR']


# 4.1 Calculate Crash Indicator Measure (Raw Score) [26]
df_crash_cohort['CRASH_MEASURE'] = np.where(
    df_crash_cohort['EXPOSURE_FACTOR'] > 0,
    df_crash_cohort['CRASH_NUMERATOR'] / df_crash_cohort['EXPOSURE_FACTOR'],
    np.nan
)

# --- Data Sufficiency and Group Assignment ---

def assign_crash_event_group(row):
    """Assign Safety Event Group based on Crash Count and Segment."""
    count = row['CRASH_COUNT']
    segment = row['CRASH_SEGMENT']
    
    # Data Sufficiency Check: Must have >= 2 applicable crashes [9]
    if count < CRASH_SUFFICIENCY_THRESHOLD:
        return 'INSUFFICIENT DATA'
    
    group_map = CRASH_GROUPS_COMBINATION if segment == 'Combination' else CRASH_GROUPS_STRAIGHT
    
    # Assign to group tier
    for group, (low, high) in group_map.items():
        if low <= count and (high == np.inf or count <= high):
            return group
    return 'INSUFFICIENT DATA'

df_crash_cohort['CRASH_GROUP'] = df_crash_cohort.apply(assign_crash_event_group, axis=1)


# 4.2 Percentile Calculation Function (same logic as prior BASICs)
def calculate_percentile(group):
    """Ranks BASIC Measures within a specific Safety Event Group (peer group)."""
    if len(group) <= 1 or (group['CRASH_GROUP'] == 'INSUFFICIENT DATA').any():
        return pd.Series(np.nan, index=group.index)

    # Use the raw Measure Value for ranking [10]
    measures = group['CRASH_MEASURE']
    
    ranks = rankdata(measures, method='min')
    N = len(ranks)
    
    # Transform rank to percentile (0 to 100 scale)
    percentiles = (ranks - 1) / (N - 1) * 100
    
    return pd.Series(percentiles, index=group.index)

# Clean measure
df_crash_cohort['CRASH_MEASURE'] = pd.to_numeric(df_crash_cohort['CRASH_MEASURE'], errors='coerce')
# Ensure group labels are strings; fill missing
df_crash_cohort['CRASH_GROUP'] = df_crash_cohort['CRASH_GROUP'].fillna('INSUFFICIENT DATA')

# Compute percentiles only for sufficient groups
valid = df_crash_cohort['CRASH_GROUP'] != 'INSUFFICIENT DATA'

def to_percentile(s):
    N = s.size
    if N <= 1:
        return pd.Series(np.nan, index=s.index)
    r = s.rank(method='min')  # 1..N
    return (r - 1) / (N - 1) * 100

df_crash_cohort['CRASH_PERCENTILE'] = np.nan
df_crash_cohort.loc[valid, 'CRASH_PERCENTILE'] = (
    df_crash_cohort.loc[valid]
      .groupby('CRASH_GROUP')['CRASH_MEASURE']
      .transform(to_percentile)
)

print(df_crash_cohort.head(100))