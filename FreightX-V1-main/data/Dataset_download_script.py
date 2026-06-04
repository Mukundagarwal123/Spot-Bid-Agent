import requests
import os
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from config.config import FMCSA_X_APP_TOKEN

# -----------------------------
# GET CURRENT SCRIPT DIRECTORY
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -----------------------------
# DATASET MAP
# -----------------------------
dataset_map = {
    "4y6x-dmck": "SMS_AB_PassProperty.csv",
    "4wxs-vbns": "SMS_Input_-_Crash.csv",
    "9mw4-x3tu": "AuthHist_-_All_With_History.csv",
    "qh9u-swkp": "ActPendInsur_-_All_With_History.csv",
    "6sqe-dvqs": "InsHist_-_All_With_History.csv",
    "rbkj-cgst": "SMS_Input_-_Inspection.csv",

    "fx4q-ay7w": "Vehicle_Inspection_File.csv",
    "wt8s-2hbx": "Inspection_Per_Unit.csv",
    "az4n-8mr2": "Company_Census_File.csv",

    "8mt8-2mdr": "SMS_Input_-_Violation.csv"
}

headers = {
    "Accept": "text/csv",
    "x-app-token": FMCSA_X_APP_TOKEN
}

# -----------------------------
# DOWNLOAD LOOP
# -----------------------------
for dataset_id, file_name in dataset_map.items():

    url = f"https://data.transportation.gov/api/v3/views/{dataset_id}/export.csv?accessType=DOWNLOAD"

    # Save in SAME folder as script
    file_path = os.path.join(BASE_DIR, file_name)

    print(f"Downloading {dataset_id} -> {file_name}")

    try:
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()

            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        print(f"Saved: {file_path}\n")

    except Exception as e:
        print(f"Failed: {dataset_id} -> {e}\n")


# https://data.transportation.gov/api/v3/views//query.csv


# 1. company_census
# https://data.transportation.gov/api/v3/views/az4n-8mr2/query.csv

# 2. SMS AB pass property 
# https://data.transportation.gov/api/v3/views/4y6x-dmck/query.csv


# 3. sms input crash  
# https://data.transportation.gov/api/v3/views/4wxs-vbns/query.csv


# 4. Auth hist all with history
# https://data.transportation.gov/api/v3/views/9mw4-x3tu/query.json


# 5. ActPendInsur_-_All_With_History_20250923
# https://data.transportation.gov/api/v3/views/qh9u-swkp/query.csv


# 6. InsHist_-_All_With_History_20251006 
# https://data.transportation.gov/api/v3/views/6sqe-dvqs/query.csv

# 7. Vehicle_Inspection_File_20251022   
# https://data.transportation.gov/api/v3/views/fx4q-ay7w/query.csv

# 8. inspection per unit
# https://data.transportation.gov/api/v3/views/wt8s-2hbx/query.csv

# 9. SMS_Input_-_Inspection
# https://data.transportation.gov/api/v3/views/rbkj-cgst/query.csv

# 10. SMS_Input_-_Violation
# https://data.transportation.gov/api/v3/views/8mt8-2mdr/query.csv