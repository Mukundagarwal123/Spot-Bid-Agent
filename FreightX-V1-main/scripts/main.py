import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def clean_dot(x):
    if pd.isna(x):
        return None

    x = str(x).strip()

    # remove .0 safely
    if x.endswith(".0"):
        x = x[:-2]

    # remove leading zeros
    x = x.lstrip("0")

    return x if x != "" else None

def clean_docket(x):
    if pd.isna(x):
        return None
    x = str(x).strip().upper()
    if not x.startswith("MC"):
        x = "MC" + x.replace("MC", "")
    return x

# Read CSV file (Company Census File - base population)
df = pd.read_csv("../data/Company_Census_File.csv")

# Base filter: keep only MC docket carriers (must not change this logic)
rows = []

for _, row in df.iterrows():

    # DOCKET1
    if pd.notna(row.get('DOCKET1')) and str(row.get('DOCKET1PREFIX')).strip() == 'MC':
        rows.append({
            **row,
            'DOCKET_NUMBER': f"MC{int(row['DOCKET1'])}"
        })

    # DOCKET2
    if pd.notna(row.get('DOCKET2')) and str(row.get('DOCKET2PREFIX')).strip() == 'MC':
        rows.append({
            **row,
            'DOCKET_NUMBER': f"MC{int(row['DOCKET2'])}"
        })

    # DOCKET3
    if pd.notna(row.get('DOCKET3')) and str(row.get('DOCKET3PREFIX')).strip() == 'MC':
        rows.append({
            **row,
            'DOCKET_NUMBER': f"MC{int(row['DOCKET3'])}"
        })

df = pd.DataFrame(rows)

# df['DOCKET1'] = df['DOCKET1'].apply(lambda x: str(int(x)) if x.is_integer() else str(x))
# df['DOCKET_NUMBER'] = df['DOCKET1PREFIX'] + df['DOCKET1']
df['DOT_NUMBER'] = df['DOT_NUMBER'].apply(clean_dot).astype('string')
df['DOCKET_NUMBER'] = df['DOCKET_NUMBER'].apply(clean_docket).astype('string')


# docket_dot_map = (
#     df[['DOCKET_NUMBER', 'DOT_NUMBER']]
#     .dropna(subset=['DOCKET_NUMBER', 'DOT_NUMBER'])
#     .drop_duplicates(subset=['DOT_NUMBER'])
#     .copy()
# )
# dot_to_docket = docket_dot_map.set_index('DOT_NUMBER')['DOCKET_NUMBER']

# Standardized status column from Company Census File
if 'Status_code' in df.columns:
    df['Status_code'] = df['Status_code']
elif 'STATUS_CODE' in df.columns:
    df['Status_code'] = df['STATUS_CODE']

# Ensure requested census contact/officer columns exist even if absent in a given extract
for _col in ['COMPANY_OFFICER_1', 'COMPANY_OFFICER_2', 'PHONE', 'CELL_PHONE', 'FAX', 'EMAIL_ADDRESS']:
    if _col not in df.columns:
        df[_col] = pd.NA

# Ensure requested census mailing/physical address columns exist
for _col in [
    'CARRIER_MAILING_STREET',
    'CARRIER_MAILING_STATE',
    'CARRIER_MAILING_CITY',
    'CARRIER_MAILING_COUNTRY',
    'CARRIER_MAILING_ZIP',
    'CARRIER_MAILING_CNTY',
    'PHY_STREET',
    'PHY_CITY',
    'PHY_COUNTRY',
    'PHY_STATE',
    'PHY_ZIP',
    'PHY_CNTY',
    'FLEETSIZE',
    'MCSIPSTEP',
    'MCSIPDATE',
    'CARSHIP',
    'CRGO_GENFREIGHT',
    'CRGO_HOUSEHOLD',
    'CRGO_METALSHEET',
    'CRGO_MOTOVEH',
    'CRGO_DRIVETOW',
    'CRGO_LOGPOLE',
    'CRGO_BLDGMAT',
    'CRGO_MOBILEHOME',
    'CRGO_MACHLRG',
    'CRGO_PRODUCE',
    'CRGO_LIQGAS',
    'CRGO_INTERMODAL',
    'CRGO_PASSENGERS',
    'CRGO_OILFIELD',
    'CRGO_LIVESTOCK',
    'CRGO_GRAINFEED',
    'CRGO_COALCOKE',
    'CRGO_MEAT',
    'CRGO_GARBAGE',
    'CRGO_USMAIL',
    'CRGO_CHEM',
    'CRGO_DRYBULK',
    'CRGO_COLDFOOD',
    'CRGO_BEVERAGES',
    'CRGO_PAPERPROD',
    'CRGO_UTILITY',
    'CRGO_FARMSUPP',
    'CRGO_CONSTRUCT',
    'CRGO_WATERWELL',
    'CRGO_CARGOOTHR',
    'CRGO_CARGOOTHR_DESC',
    'CLASSDEF'
]:
    if _col not in df.columns:
        df[_col] = pd.NA

# print(df['DOCKET_NUMBER'].head())
# View filtered result

print(df.shape)


# ------------------------------------------------------------
# TRUST & COMPLIANCE
# ------------------------------------------------------------

# --------------------------------
# Authority & Status
# --------------------------------

df2 = pd.read_csv("../data/AuthHist_-_All_With_History.csv")
df2 = df2[df2['DOCKET_NUMBER'].astype(str).str.startswith('MC')]
df2['DOT_NUMBER'] = df2['DOT_NUMBER'].apply(clean_dot).astype('string')
df2['DOCKET_NUMBER'] = df2['DOCKET_NUMBER'].apply(clean_docket).astype('string')

# Calculate days since event
today = pd.Timestamp.today().normalize()
df2['DISP_SERVED_DATE'] = pd.to_datetime(df2['DISP_SERVED_DATE'], format='%m/%d/%Y', errors='coerce')
df2['Days_Since_Event'] = (today - df2['DISP_SERVED_DATE']).dt.days


severity_map = {
    'SAFETY REVOCATION': 10,
    'SAFETY SUSPENSION': 10,
    'REVOKED': 10,
    'OUT OF SERVICE': 10,
    'FAILURE TO REAPPLY': 6,
    'ADMINISTRATIVE INACTIVATION': 5,
    'EXPIRED ETA OR TA': 4,
    'TERM EXPIRED': 4,
    'TRANSFERRED': 3,
    'TRANSFER CONSUMMATED': 3,
    'SUPERSEDED': 2,
    'REPLACED BY PROVISIONAL AUTHORITY': 2,
    'RENUMBERED': 1,
    'CANCELLED AND REISSUED': 1,
    'DISCONTINUED REVOCATION': 0
}

df2['Severity_Score'] = df2['DISP_ACTION_DESC'].map(severity_map)
df2['Severity_Score'] = df2['Severity_Score'] / 10

# decay factor
lambda_ = 0.001  # ~ half-life ~ 700 days

# weight for each event
df2['Weight'] = np.exp(-lambda_ * df2['Days_Since_Event'])

# weighted severity
df2['Weighted_Severity'] = df2['Severity_Score'] * df2['Weight']

# aggregate per carrier (Carrier_Risk_Index)
carrier_scores = (
    df2.groupby(['DOT_NUMBER','DOCKET_NUMBER'], dropna=True)
      .apply(lambda x: np.sum(x['Weighted_Severity']) / np.sum(x['Weight']))
      .reset_index(name='Carrier_Risk_Index')
)
print(carrier_scores[['DOT_NUMBER','DOCKET_NUMBER']].nunique())
print(carrier_scores.shape)

# latest authority / disposition event per carrier
df2_latest = (
    df2.sort_values(['DOT_NUMBER','DOCKET_NUMBER', 'DISP_SERVED_DATE'])
       .drop_duplicates(subset=['DOT_NUMBER','DOCKET_NUMBER'], keep='last')
       [['DOT_NUMBER',
        'DOCKET_NUMBER',
         'OP_AUTH_TYPE',
         'ORIGINAL_ACTION_DESC',
         'ORIG_SERVED_DATE',
         'DISP_ACTION_DESC',
         'DISP_DECIDED_DATE',
         'DISP_SERVED_DATE']]
)

# ----------------------------------
# Insurance & Filing
# ----------------------------------

from datetime import date

df3 = pd.read_csv("../data/ActPendInsur_-_All_With_History.csv")
df3 = df3[df3['ins_type_desc'].astype(str).str.contains('BIPD', case=False, na=False)]
df3 = df3[df3['DOCKET_NUMBER'].astype(str).str.startswith('MC')]


df3['DOT_NUMBER'] = df3['DOT_NUMBER'].apply(clean_dot).astype('string')
df3['DOCKET_NUMBER'] = df3['DOCKET_NUMBER'].apply(clean_docket).astype('string')
# Assuming df_act is your ActPendInsur dataframe
df3['effective_date'] = pd.to_datetime(df3['effective_date'], errors='coerce')
df3['cancl_effective_date'] = pd.to_datetime(df3['cancl_effective_date'], errors='coerce')
df3['trans_date'] = pd.to_datetime(df3['trans_date'], errors='coerce')
today = pd.Timestamp(date.today())

# “Current” means:
# (1) Effective date is in the past (already started)
# (2) Cancel date is missing OR in the future
mask = (
    (df3['effective_date'] <= today) &
    ((df3['cancl_effective_date'].isna()) | (df3['cancl_effective_date'] > today))
)
df3 = df3[mask]

# Sort to pick the most recent filing per DOCKET_NUMBER and INS_TYPE
df_sorted = df3.sort_values(
    ['DOT_NUMBER','DOCKET_NUMBER','ins_type_desc','effective_date','trans_date'],
    ascending=[True, True, True, False, False]
)
# Keep latest per combination
df3 = df_sorted.drop_duplicates(subset=['DOT_NUMBER','DOCKET_NUMBER','ins_type_desc'], keep='first')

# ActPendInsur detail fields (latest row per DOCKET_NUMBER)
actpend_cols_needed = [
    'DOT_NUMBER',
    'DOCKET_NUMBER',
    'ins_form_code',
    'ins_type_desc',
    'name_company',
    'policy_no',
    'trans_date',
    'underl_lim_amount',
    'max_cov_amount',
    'effective_date',
    'cancl_effective_date',
]
actpend_cols_present = [c for c in actpend_cols_needed if c in df3.columns]
actpend_detail_df = (
    df3.sort_values(['DOT_NUMBER','DOCKET_NUMBER', 'effective_date', 'trans_date'])
       .drop_duplicates(subset=['DOT_NUMBER','DOCKET_NUMBER'], keep='last')[actpend_cols_present]
       .copy()
)

# if 'DOT_NUMBER' in actpend_detail_df.columns:
    # Keep base DOT_NUMBER intact for downstream DOT-level joins.
    # actpend_detail_df.rename(columns={'DOT_NUMBER': 'ACTPEND_DOT_NUMBER'}, inplace=True)

df_ins = pd.read_csv("../data/InsHist_-_All_With_History.csv")
df_ins = df_ins[df_ins['docket_number'].astype(str).str.startswith('MC')]
df_ins['dot_number'] = df_ins['dot_number'].apply(clean_dot).astype('string')
df_ins['docket_number'] = df_ins['docket_number'].apply(clean_docket).astype('string')

df_min_latest = (
    df_ins.sort_values(['dot_number','docket_number', 'effective_date'], ascending=[True, True, False])
    .drop_duplicates(subset=['dot_number','docket_number'], keep='first')
    [['dot_number', 'docket_number', 'min_cov_amount']]
)

df3["dot_number"] = df3["DOT_NUMBER"]
df3["docket_number"] = df3["DOCKET_NUMBER"]

df_merged = df3.merge(df_min_latest, on=['dot_number','docket_number'], how='outer')
df_merged = df_merged.dropna(subset=['min_cov_amount'])

coverage_df = (
    df_merged.groupby(['dot_number','docket_number'], as_index=False)
      .agg(
          total_insured=('max_cov_amount', 'sum'),
          required_ins=('min_cov_amount', 'max')
      )
)

coverage_df['coverage_ratio'] = coverage_df['total_insured'] / coverage_df['required_ins']
coverage_df['coverage_ratio_exp'] = 1 - np.exp(-coverage_df['coverage_ratio'])
print(coverage_df['docket_number'].nunique())
print(coverage_df.shape)


# ----------------------------------
# Carrier – All With History
# ----------------------------------

carrier_all = pd.read_csv("../data/Carrier_-_All_With_History.csv")
carrier_all = carrier_all[carrier_all['DOCKET_NUMBER'].astype(str).str.startswith('MC')]
carrier_all['DOT_NUMBER'] = carrier_all['DOT_NUMBER'].apply(clean_dot).astype('string')
carrier_all['DOCKET_NUMBER'] = carrier_all['DOCKET_NUMBER'].apply(clean_docket).astype('string')


carrier_cols_needed = [
    'DOT_NUMBER',
    'DOCKET_NUMBER',
    'COMMON_STAT',
    'CONTRACT_STAT',
    'BROKER_STAT',
    'PROPERTY_CHK',
    'PASSENGER_CHK',
    'HHG_CHK',
    'PRIVATE_AUTH_CHK',
    'ENTERPRISE_CHK',
]
carrier_cols_present = [c for c in carrier_cols_needed if c in carrier_all.columns]
df_carrier_flags = carrier_all[carrier_cols_present]
df_carrier_flags=df_carrier_flags[df_carrier_flags['COMMON_STAT']=='A'] # only want common_stat=ACTIVE carriers
df_carrier_flags=df_carrier_flags[df_carrier_flags['DOT_NUMBER']!=0]
df_carrier_flags=df_carrier_flags.drop_duplicates(subset=['DOT_NUMBER','DOCKET_NUMBER'], keep='last')


# ----------------------------------
# Vehicle Inspection + Inspection Per Unit
# ----------------------------------

vehicle_insp = pd.read_csv("../data/Vehicle_Inspection_File.csv")
insp_per_unit = pd.read_csv("../data/Inspection_Per_Unit.csv")

vehicle_cols_needed = ['INSPECTION_ID', 'INSP_DATE','DOT_NUMBER','DOCKET_NUMBER']
vehicle_insp_small = vehicle_insp[vehicle_cols_needed].copy()
vehicle_insp_small['INSP_DATE'] = pd.to_datetime(vehicle_insp_small['INSP_DATE'], errors='coerce')

if 'DOT_NUMBER' in vehicle_insp_small.columns:
    vehicle_insp_small['DOT_NUMBER'] = vehicle_insp_small['DOT_NUMBER'].apply(clean_dot).astype('string')

vehicle_insp_small['DOCKET_NUMBER'] = vehicle_insp_small['DOCKET_NUMBER'].apply(clean_docket).astype('string')

unit_cols_needed = [
    'INSPECTION_ID',
    'INSP_UNIT_TYPE_ID',
    'INSP_UNIT_NUMBER',
    'INSP_UNIT_VEHICLE_ID_NUMBER',
    'INSP_UNIT_MAKE',
]

unit_cols_present = [c for c in unit_cols_needed if c in insp_per_unit.columns]
insp_per_unit_small = insp_per_unit[unit_cols_present].copy()

# A & B join on INSPECTION_ID
inspection_joined = vehicle_insp_small.merge(insp_per_unit_small, on='INSPECTION_ID', how='left')

# Join key policy: use DOCKET_NUMBER first; fallback from DOT_NUMBER only where needed.
if 'DOCKET_NUMBER' not in inspection_joined.columns:
    inspection_joined['DOCKET_NUMBER'] = pd.NA

inspection_joined['DOCKET_NUMBER'] = inspection_joined['DOCKET_NUMBER'].astype('string').str.strip()
inspection_joined['DOCKET_NUMBER'] = inspection_joined['DOCKET_NUMBER'].replace(
    {'': pd.NA, 'nan': pd.NA, 'None': pd.NA, '<NA>': pd.NA}
)

# if 'DOT_NUMBER' in inspection_joined.columns:
#     inspection_joined['DOCKET_NUMBER'] = inspection_joined['DOCKET_NUMBER'].fillna(
#         inspection_joined['DOT_NUMBER'].map(dot_to_docket)
#     )

# Keep one row per DOCKET_NUMBER for carrier-level left join
inspection_joined = (
    inspection_joined.dropna(subset=['DOT_NUMBER'])
    .sort_values(['DOT_NUMBER', 'INSP_DATE'])
    .drop_duplicates(subset=['DOT_NUMBER','DOCKET_NUMBER'], keep='last')
)

# ----------------------------------
# SMS + OOS datasets (DOT-level)
# ----------------------------------

# A) SMS-AB-PassProperty
sms_ab = pd.read_csv("../data/SMS_AB_PassProperty.csv")
sms_ab_cols_needed = [
    'DOT_NUMBER',
    'DRIVER_OOS_INSP_TOTAL',
    'DRIVER_INSP_TOTAL',
    'VEHICLE_OOS_INSP_TOTAL',
    'VEHICLE_INSP_TOTAL',
    'UNSAFE_DRIV_MEASURE',
    'HOS_DRIV_MEASURE',
    'DRIV_FIT_MEASURE',
    'CONTR_SUBST_MEASURE',
    'VEH_MAINT_MEASURE',
]

sms_ab_cols_present = [c for c in sms_ab_cols_needed if c in sms_ab.columns]
sms_ab_small = sms_ab[sms_ab_cols_present].copy()
sms_ab_small['DOT_NUMBER'] = sms_ab_small['DOT_NUMBER'].apply(clean_dot).astype('string')
sms_ab_small = sms_ab_small.drop_duplicates(subset=['DOT_NUMBER'], keep='last')
# B) Vehicle Inspection File -> HAZMAT_OOS_TOTAL

hazmat_oos_df = (
    vehicle_insp[['DOT_NUMBER', 'HAZMAT_OOS_TOTAL']]
    .copy()
)

hazmat_oos_df['DOT_NUMBER'] = hazmat_oos_df['DOT_NUMBER'].apply(clean_dot).astype('string')
hazmat_oos_df = (
    hazmat_oos_df.dropna(subset=['DOT_NUMBER'])
    .groupby('DOT_NUMBER', as_index=False)['HAZMAT_OOS_TOTAL']
    .sum()
)

# C) SMS-Input-Inspection -> HM_Insp
sms_input_insp = pd.read_csv("../data/SMS_Input_-_Inspection.csv")
sms_input_dot_col = 'DOT_Number'


sms_input_cols_needed = [
    'Insp_Date',
    'Report_Number',
    'Report_State',
    'Unit_Type_Desc',
    'Unit_Type_Desc2',
    'Unit_Make',
    'Unit_Make2',
    'Unit_License',
    'unit_license2',
    'Unit_License_State',
    'Unit_License_State2',
    'VIN',
    'VIN2',
    'Insp_level_ID',
    'BASIC_Viol',
    'OOS_Total',
    'HM_Insp',
]

sms_input_cols_present = [c for c in sms_input_cols_needed if c in sms_input_insp.columns]

if sms_input_dot_col is not None:
    sms_input_insp_small = sms_input_insp[[sms_input_dot_col] + sms_input_cols_present].copy()
    sms_input_insp_small.rename(columns={sms_input_dot_col: 'DOT_NUMBER'}, inplace=True)
    sms_input_insp_small['DOT_NUMBER'] = sms_input_insp_small['DOT_NUMBER'].apply(clean_dot).astype('string')

    if 'Insp_Date' in sms_input_insp_small.columns:
        sms_input_insp_small['Insp_Date'] = pd.to_datetime(sms_input_insp_small['Insp_Date'], errors='coerce')
        sms_input_insp_small = (
            sms_input_insp_small.sort_values(['DOT_NUMBER', 'Insp_Date'])
            .drop_duplicates(subset=['DOT_NUMBER'], keep='last')
        )
    else:
        sms_input_insp_small = sms_input_insp_small.drop_duplicates(subset=['DOT_NUMBER'], keep='last')
else:
    sms_input_insp_small = pd.DataFrame(columns=[
        'DOT_NUMBER',
        'Insp_Date',
        'Report_Number',
        'Report_State',
        'Unit_Type_Desc',
        'Unit_Type_Desc2',
        'Unit_Make',
        'Unit_Make2',
        'Unit_License',
        'unit_license2',
        'Unit_License_State',
        'Unit_License_State2',
        'VIN',
        'VIN2',
        'Insp_level_ID',
        'BASIC_Viol',
        'OOS_Total',
        'HM_Insp',
    ])

# Ensure consistent columns for downstream merge selection
for _col in [
    'DOT_NUMBER',
    'Insp_Date',
    'Report_Number',
    'Report_State',
    'Unit_Type_Desc',
    'Unit_Type_Desc2',
    'Unit_Make',
    'Unit_Make2',
    'Unit_License',
    'unit_license2',
    'Unit_License_State',
    'Unit_License_State2',
    'VIN',
    'VIN2',
    'Insp_level_ID',
    'BASIC_Viol',
    'OOS_Total',
    'HM_Insp',
]:
    if _col not in sms_input_insp_small.columns:
        sms_input_insp_small[_col] = pd.NA

sms_input_insp_small.rename(columns={'Report_State':'INSP_REPORT_STATE','Insp_Date':'INSP_DATE_SMS_INSPECTION'}, inplace=True)

# D) SMS-Input_Violation
sms_input_viol = pd.read_csv("../data/SMS_Input_-_Violation.csv")

viol_dot_col = 'DOT_Number'

viol_cols_needed = [
    'Insp_Date',
    'violation_date',
    'Viol_Code',
    'Group_Desc',
    'Section_Desc',
    'OOS_Indicator',
    'Time_Weight',
    'Severity_Weight',
]
viol_cols_present = [c for c in viol_cols_needed if c in sms_input_viol.columns]

if viol_dot_col is not None:
    sms_input_viol_small = sms_input_viol[[viol_dot_col] + viol_cols_present].copy()
    sms_input_viol_small.rename(columns={viol_dot_col: 'DOT_NUMBER'}, inplace=True)
    sms_input_viol_small['DOT_NUMBER'] = sms_input_viol_small['DOT_NUMBER'].apply(clean_dot).astype('string')
    total_violation = (
        sms_input_viol_small
        .groupby('DOT_NUMBER', dropna=False)
        .size()
        .reset_index(name='count')
        .sort_values('count', ascending=False)
        )
    sms_input_viol_small=sms_input_viol_small.merge(total_violation.rename(columns={'count':'TOTAL_VIOLATION'}), on=['DOT_NUMBER'], how='left')
    # Use Insp_Date when present, otherwise violation_date
    if 'Insp_Date' in sms_input_viol_small.columns:
        sms_input_viol_small['viol_event_date'] = pd.to_datetime(sms_input_viol_small['Insp_Date'], errors='coerce')
    else:
        sms_input_viol_small['viol_event_date'] = pd.NaT

    sms_input_viol_small = (
        sms_input_viol_small.sort_values(['DOT_NUMBER', 'viol_event_date'])
        .drop_duplicates(subset=['DOT_NUMBER'], keep='last')
    )
else:
    sms_input_viol_small = pd.DataFrame(columns=[
        'DOT_NUMBER',
        'Insp_Date',
        'violation_date',
        'Viol_Code',
        'Group_Desc',
        'Section_Desc',
        'OOS_Indicator',
        'Time_Weight',
        'Severity_Weight',
    ])

# Ensure consistent columns for downstream merge selection
for _col in [
    'DOT_NUMBER',
    'Insp_Date',
    'violation_date',
    'Viol_Code',
    'Group_Desc',
    'Section_Desc',
    'OOS_Indicator',
    'Time_Weight',
    'Severity_Weight',
]:
    if _col not in sms_input_viol_small.columns:
        sms_input_viol_small[_col] = pd.NA

sms_input_viol_small['VIOLATION_VALUE'] = sms_input_viol_small['Severity_Weight'] * sms_input_viol_small['Time_Weight']
sms_input_viol_small.rename(columns={'Severity_Weight':'Violation_Severity_Weight','Insp_Date':'INSP_DATE_SMS_VIOLATION'}, inplace=True)

# E) SMS-Input-Crash
sms_input_crash = pd.read_csv("../data/SMS_Input_-_Crash.csv")

crash_dot_col = 'DOT_Number'

crash_cols_needed = [
    'Report_Date',
    'Report_number',
    'Vehicle_ID_Number',
    'Report_State',
    'Vehicle_License_State',
    'Vehicle_License_number',
    'Fatalities',
    'Injuries',
    'Tow_Away',
    'Hazmat_Released',
    'Not_Preventable',
    'Severity_Weight',
]
crash_cols_present = [c for c in crash_cols_needed if c in sms_input_crash.columns]

if crash_dot_col is not None:
    sms_input_crash_small = sms_input_crash[[crash_dot_col] + crash_cols_present].copy()
    sms_input_crash_small.rename(columns={crash_dot_col: 'DOT_NUMBER'}, inplace=True)
    sms_input_crash_small['DOT_NUMBER'] = sms_input_crash_small['DOT_NUMBER'].apply(clean_dot).astype('string')
    
    total_crash = (
    sms_input_crash_small
    .groupby('DOT_NUMBER', dropna=False)
    .size()
    .reset_index(name='count')
    .sort_values('count', ascending=False)
    )
    sms_input_crash_small=sms_input_crash_small.merge(total_crash.rename(columns={'count':'TOTAL_CRASH'}), on=['DOT_NUMBER'], how='left')
    
    if 'Report_Date' in sms_input_crash_small.columns:
        sms_input_crash_small['Report_Date'] = pd.to_datetime(sms_input_crash_small['Report_Date'], errors='coerce')
        sms_input_crash_small = (
            sms_input_crash_small.sort_values(['DOT_NUMBER', 'Report_Date'])
            .drop_duplicates(subset=['DOT_NUMBER'], keep='last')
        )
    else:
        sms_input_crash_small = sms_input_crash_small.drop_duplicates(subset=['DOT_NUMBER'], keep='last')
else:
    sms_input_crash_small = pd.DataFrame(columns=[
        'DOT_NUMBER',
        'Report_Date',
        'Report_number',
        'Vehicle_ID_Number',
        'Report_State',
        'Vehicle_License_State',
        'Vehicle_License_number',
        'Fatalities',
        'Injuries',
        'Tow_Away',
        'Hazmat_Released',
        'Not_Preventable',
        'Severity_Weight',
    ])

sms_input_crash_small.rename(columns={'Severity_Weight':'Crash_Severity_Weight','Report_State':'CRASH_REPORT_STATE'}, inplace=True)
    


# ----------------------------------
# Credibility & Stability
# ----------------------------------
##### undeliv_phy - majority null

df['ADD_DATE_'] = pd.to_datetime(df['ADD_DATE'], format='%Y%m%d')
# Step 1: Convert to datetime (parse both date and time)
df['MCS150_DATE_'] = pd.to_datetime(df['MCS150_DATE'], format='%Y%m%d %H%M', errors='coerce')


# Calculate number of days before today
today = pd.Timestamp.today()
df['days_since_mcs150'] = (today - df['MCS150_DATE_']).dt.days
df = df[df['days_since_mcs150'] <= 1000]


# Calculate number of days before today
today = pd.Timestamp.today()
df['days_since_inception'] = (today - df['ADD_DATE_']).dt.days

# Min-max normalization reversed (older = higher score)
min_days = df['days_since_inception'].min()
max_days = df['days_since_inception'].max()

df['inception_score'] = 1 - (df['days_since_inception'] - min_days) / (max_days - min_days)
print(df['DOCKET_NUMBER'].nunique())
print(df.shape)

# # # ------------------------------------------------------------
# # # Capacity & Scale
# # # ------------------------------------------------------------

# # df["POWER_UNITS"], df["FLEETSIZE"], df["TOTAL_DRIVERS"]


import pandas as pd

df['efficiency'] = df['TOTAL_DRIVERS'] / df['POWER_UNITS']

# normalize
df['pu_norm'] = (df['POWER_UNITS'] - df['POWER_UNITS'].min()) / (df['POWER_UNITS'].max() - df['POWER_UNITS'].min())
df['eff_norm'] = (df['efficiency'] - df['efficiency'].min()) / (df['efficiency'].max() - df['efficiency'].min())

# weighted score
df['relevancy_score'] = 0.6 * df['pu_norm'] + 0.4 * df['eff_norm']

df['relevancy_score'] = (
    (df['relevancy_score'] - df['relevancy_score'].min()) /
    (df['relevancy_score'].max() - df['relevancy_score'].min())
)


# # df.sort_values(by='DOT_NUMBER').to_csv("datas/part1.csv", index=False)

#  Get unique DOT_NUMBERs from each dataframe
docket_numbers_df = set(df['DOCKET_NUMBER'].dropna().unique())
docket_numbers_coverage = set(coverage_df['docket_number'].dropna().unique())
docket_numbers_carrier = set(carrier_scores['DOCKET_NUMBER'].dropna().unique())

# Find intersection (carriers present in all three)
common_docket_numbers = docket_numbers_df.intersection(docket_numbers_coverage).intersection(docket_numbers_carrier)
union_docket_numbers = docket_numbers_df.union(docket_numbers_coverage).union(docket_numbers_carrier)


print(f"Total DOCKET_NUMBERs in df: {len(docket_numbers_df)}")
print(f"Total docket_numbers in coverage_df: {len(docket_numbers_coverage)}")
print(f"Total DOCKET_NUMBERs in carrier_scores: {len(docket_numbers_carrier)}")
print(f"Common DOCKET_NUMBERs (intersection): {len(common_docket_numbers)}")
print(f"Union DOCKET_NUMBERs (union): {len(union_docket_numbers)}")

# Build final master dataframe using left joins on DOCKET_NUMBER
final_df = (
    df[['DOCKET_NUMBER','DOT_NUMBER','LEGAL_NAME','COMPANY_OFFICER_1', 'COMPANY_OFFICER_2', 'PHONE', 'CELL_PHONE', 'FAX', 'EMAIL_ADDRESS','CARRIER_MAILING_STREET', 'CARRIER_MAILING_STATE', 'CARRIER_MAILING_CITY', 'CARRIER_MAILING_COUNTRY', 'CARRIER_MAILING_ZIP', 'CARRIER_MAILING_CNTY','PHY_STREET', 'PHY_CITY', 'PHY_COUNTRY', 'PHY_STATE', 'PHY_ZIP', 'PHY_CNTY', 'SAFETY_RATING', 'SAFETY_RATING_DATE','relevancy_score', 'inception_score', 'Status_code', 'CLASSDEF', 'TRUCK_UNITS', 'POWER_UNITS', 'BUS_UNITS','OWNTRAIL', 'TRMTRAIL', 'TRPTRAIL', 'OWNTRUCK', 'TRMTRUCK', 'TRPTRUCK', 'CRGO_COLDFOOD','FLEETSIZE','MCSIPSTEP','MCSIPDATE','CARSHIP','CRGO_GENFREIGHT','CRGO_HOUSEHOLD','CRGO_METALSHEET','CRGO_MOTOVEH','CRGO_DRIVETOW','CRGO_LOGPOLE','CRGO_BLDGMAT','CRGO_MOBILEHOME','CRGO_MACHLRG','CRGO_PRODUCE','CRGO_LIQGAS','CRGO_INTERMODAL','CRGO_PASSENGERS','CRGO_OILFIELD','CRGO_LIVESTOCK','CRGO_GRAINFEED','CRGO_COALCOKE','CRGO_MEAT','CRGO_GARBAGE','CRGO_USMAIL','CRGO_CHEM','CRGO_DRYBULK','CRGO_COLDFOOD','CRGO_BEVERAGES','CRGO_PAPERPROD','CRGO_UTILITY','CRGO_FARMSUPP','CRGO_CONSTRUCT','CRGO_WATERWELL','CRGO_CARGOOTHR','CRGO_CARGOOTHR_DESC','CLASSDEF']]
    .merge(coverage_df.rename(columns={'docket_number': 'DOCKET_NUMBER', 'dot_number':'DOT_NUMBER'})[['DOT_NUMBER','DOCKET_NUMBER', 'coverage_ratio_exp']], on=['DOT_NUMBER','DOCKET_NUMBER'], how='outer')
    .merge(carrier_scores.rename(columns={'Carrier_Risk_Index': 'Weighted_Severity'})[['DOT_NUMBER', 'DOCKET_NUMBER', 'Weighted_Severity']],
        on=['DOT_NUMBER','DOCKET_NUMBER'],
        how='outer'
    )
    .merge(
        df2_latest,
        on=[ 'DOT_NUMBER','DOCKET_NUMBER'],
        how='outer'
    )
    .merge(
        actpend_detail_df,
        on=['DOT_NUMBER','DOCKET_NUMBER'],
        how='outer'
    )
    .merge(
        inspection_joined[['DOT_NUMBER','DOCKET_NUMBER', 'INSPECTION_ID', 'INSP_DATE', 'INSP_UNIT_TYPE_ID', 'INSP_UNIT_NUMBER', 'INSP_UNIT_VEHICLE_ID_NUMBER', 'INSP_UNIT_MAKE']],
        on=['DOT_NUMBER', 'DOCKET_NUMBER'],
        how='outer'
    )
    .merge(
        sms_ab_small[
            ['DOT_NUMBER','DRIVER_OOS_INSP_TOTAL', 'DRIVER_INSP_TOTAL','VEHICLE_OOS_INSP_TOTAL', 'VEHICLE_INSP_TOTAL','UNSAFE_DRIV_MEASURE', 'HOS_DRIV_MEASURE','DRIV_FIT_MEASURE', 'CONTR_SUBST_MEASURE', 'VEH_MAINT_MEASURE']
        ],
        on='DOT_NUMBER',
        how='outer'
    )
    .merge(
        hazmat_oos_df[['DOT_NUMBER', 'HAZMAT_OOS_TOTAL']],
        on='DOT_NUMBER',
        how='outer'
    )
    .merge(
        sms_input_insp_small[
            ['DOT_NUMBER',
             'INSP_DATE_SMS_INSPECTION',
             'Report_Number',
             'INSP_REPORT_STATE',
             'Unit_Type_Desc',
             'Unit_Type_Desc2',
             'Unit_Make',
             'Unit_Make2',
             'Unit_License',
             'unit_license2',
             'Unit_License_State',
             'Unit_License_State2',
             'VIN',
             'VIN2',
             'Insp_level_ID',
             'BASIC_Viol',
             'OOS_Total',
             'HM_Insp']
        ],
        on='DOT_NUMBER',
        how='outer'
    )
    .merge(
        sms_input_viol_small[['DOT_NUMBER', 'INSP_DATE_SMS_VIOLATION', 'violation_date', 'Viol_Code', 'Group_Desc', 'Section_Desc', 'OOS_Indicator', 'Time_Weight', 'Violation_Severity_Weight']],
        on='DOT_NUMBER',
        how='outer'
    )
    .merge(
        sms_input_crash_small[
            ['DOT_NUMBER',
             'Report_Date',
             'Report_number',
             'Vehicle_ID_Number',
             'CRASH_REPORT_STATE',
             'Vehicle_License_State',
             'Vehicle_License_number',
             'Fatalities',
             'Injuries',
             'Tow_Away',
             'Hazmat_Released',
             'Not_Preventable',
             'Crash_Severity_Weight']
        ],
        on='DOT_NUMBER',
        how='outer'
    )
    .merge(
        df_carrier_flags,
        on=['DOT_NUMBER','DOCKET_NUMBER'],
        how='outer'
    )
)





# only active carriers show honge 



final_df=final_df[final_df['Status_code']=='A']







col = final_df.pop('DOT_NUMBER')   # removes column
final_df.insert(1, 'DOT_NUMBER', col)

print(final_df['DOCKET_NUMBER'].nunique())
print(final_df.shape)
final_df.to_csv(DATA_DIR / "final_df1.csv", index=False)

# 'LEGAL_NAME','BUS_CITY','BUS_STATE_CODE','BUS_ZIP_CODE','BUS_STREET_PO',''