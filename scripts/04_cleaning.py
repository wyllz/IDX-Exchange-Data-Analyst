import os
 
import pandas as pd
 
DATA_DIR = "data/processed"
 
DATE_FIELDS = ["CloseDate", "PurchaseContractDate", "ListingContractDate",
               "ContractStatusChangeDate"]
NUMERIC_FIELDS = [
    "ClosePrice", "ListPrice", "OriginalListPrice", "LivingArea", "LotSizeAcres",
    "LotSizeSquareFeet", "BedroomsTotal", "BathroomsTotalInteger", "DaysOnMarket",
    "YearBuilt", "Latitude", "Longitude", "AssociationFee", "TaxAnnualAmount",
    "GarageSpaces", "ParkingTotal", "Stories", "rate_30yr_fixed",
]
CORE_FIELDS = set(DATE_FIELDS + NUMERIC_FIELDS + [
    "ListingKey", "PropertyType", "PropertySubType", "City", "CountyOrParish",
    "PostalCode", "MLSAreaMajor", "ListOfficeName", "BuyerOfficeName",
    "ListAgentFullName", "MlsStatus", "year_month",
])
 
# California bounding box for the out-of-state check
CA_LAT = (32.5, 42.1)
CA_LON = (-124.5, -114.1)
 
DATASETS = {
    "Sold": {
        "input": "sold_with_rates.csv",
        "required": ["ClosePrice", "CloseDate"],
        "latest_by": "CloseDate",
    },
    "Listings": {
        "input": "listings_with_rates.csv",
        "required": ["ListPrice", "ListingContractDate"],
        "latest_by": "ListingContractDate",
    },
}
 
 
def log(step, before, after, why):
    print(f"  {step}: {before:,} -> {after:,} rows ({before - after:,} removed). {why}")
 
 
def drop_redundant_columns(df):
    dup_cols = [c for c in df.columns
                if c.endswith(".1") and c[:-2] in df.columns]
    df = df.drop(columns=dup_cols)
    print(f"  Dropped {len(dup_cols)} duplicate columns from the extraction script: {dup_cols}")
 
    null_pct = df.isnull().mean() * 100
    sparse = [c for c in df.columns if null_pct[c] > 90 and c not in CORE_FIELDS]
    df = df.drop(columns=sparse)
    print(f"  Dropped {len(sparse)} non-core columns over 90% null: {sparse}")
    return df
 
 
def drop_duplicates(df, latest_by):
    before = len(df)
    df = df.drop_duplicates()
    log("Exact duplicate rows", before, len(df), "Identical rows add no information.")
 
    if "ListingKey" in df.columns:
        before = len(df)
        has_key = df["ListingKey"].notna()
        keyed = (df[has_key].sort_values(latest_by)
                 .drop_duplicates(subset="ListingKey", keep="last"))
        df = pd.concat([keyed, df[~has_key]])
        log("Repeated ListingKey", before, len(df),
            f"One record per property; kept the one with the latest {latest_by}.")
    return df
 
 
def convert_types(df):
    for c in DATE_FIELDS:
        if c in df.columns:
            raw_missing = df[c].isnull().sum()
            df[c] = pd.to_datetime(df[c], errors="coerce")
            bad = df[c].isnull().sum() - raw_missing
            print(f"  {c} -> datetime ({bad:,} unparseable values set to NaT)")
    for c in NUMERIC_FIELDS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "PostalCode" in df.columns:
        # Zip codes are labels, not numbers: keep as 5-character text
        df["PostalCode"] = df["PostalCode"].astype(str).str[:5].replace({"nan": pd.NA})
    return df
 
 
def drop_missing_required(df, required):
    before = len(df)
    df = df.dropna(subset=[c for c in required if c in df.columns])
    log("Missing required fields", before, len(df),
        f"Rows without {required} can't be used for any market metric.")
    return df