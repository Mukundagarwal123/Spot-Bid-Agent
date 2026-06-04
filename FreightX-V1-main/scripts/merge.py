import pandas as pd
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


df = pd.read_csv(DATA_DIR / "final_df1.csv")
print("Shape of the dataframe:", df.shape)
print("\nColumn names:")
print(df.columns.tolist())

df_part1 = pd.read_csv(DATA_DIR / "merged_data.csv")
print("Shape of the dataframe:", df_part1.shape)
print("\nColumn names:")
print(df_part1.columns.tolist())

for d in [df, df_part1]:
    d["DOT_NUMBER"] = d["DOT_NUMBER"].apply(clean_dot).astype("string")
    d["DOCKET_NUMBER"] = d["DOCKET_NUMBER"].apply(clean_docket).astype("string")

join_keys = ["DOT_NUMBER", "DOCKET_NUMBER"]
common_cols = [c for c in df_part1.columns if c in df.columns and c not in join_keys]

df_part1_clean = df_part1.drop(columns=common_cols)

print("Dropped from df_part1:", common_cols)
print("df_part1 shape after drop:", df_part1_clean.shape)

final_df = df_part1_clean.merge(
    df,
    on=["DOT_NUMBER", "DOCKET_NUMBER"],
    how="right",
)
print("final_df shape:", final_df.shape)

final_df.to_csv(DATA_DIR / "df_output_with_inspections1.csv", index=False)
