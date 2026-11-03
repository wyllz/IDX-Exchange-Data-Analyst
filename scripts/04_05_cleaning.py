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
    sparse = [c for c in df.columns if null_pct[c] > 90 and c not in CORE_FIELDS] # drops non-core columns that are >90% null
    df = df.drop(columns=sparse)
    print(f"  Dropped {len(sparse)} non-core columns over 90% null: {sparse}")
    return df
 
 
def drop_duplicates(df, latest_by):
    # exact duplicate rows, repeat listingkeys
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
    # convert to datetimes and numerics
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
        # keep zipcodes as 5-character text
        df["PostalCode"] = df["PostalCode"].astype(str).str[:5].replace({"nan": pd.NA})
    return df
 
 
def drop_missing_required(df, required):
    # missing fields that are necessary
    before = len(df)
    df = df.dropna(subset=[c for c in required if c in df.columns])
    log("Missing required fields", before, len(df),
        f"Rows without {required} can't be used for any market metric.")
    return df

def flag_invalid_numeric(df):
    #bbusiness-rule invalid values
    rules = {
        "invalid_close_price_flag": ("ClosePrice", lambda s: s <= 0),
        "invalid_living_area_flag": ("LivingArea", lambda s: s <= 0),
        "invalid_dom_flag": ("DaysOnMarket", lambda s: s < 0),
        "invalid_bedrooms_flag": ("BedroomsTotal", lambda s: s < 0),
        "invalid_bathrooms_flag": ("BathroomsTotalInteger", lambda s: s < 0),
    }
    flags = []
    for flag, (col, rule) in rules.items():
        if col in df.columns:
            df[flag] = rule(df[col]).fillna(False).astype(bool)
            flags.append(flag)
            print(f"  {flag}: {df[flag].sum():,}")
    df["invalid_numeric_flag"] = df[flags].any(axis=1)
    print(f"  Any invalid numeric value: {df['invalid_numeric_flag'].sum():,}")
    return df
 
 
def flag_dates(df):
    # logical order ListingContractDate <= PurchaseContractDate <= CloseDate
    listing = df.get("ListingContractDate")
    purchase = df.get("PurchaseContractDate")
    close = df.get("CloseDate")
    # comparisons with a missing date are marked false
    df["listing_after_close_flag"] = (listing > close) if listing is not None and close is not None else False
    df["purchase_after_close_flag"] = (purchase > close) if purchase is not None and close is not None else False
    df["negative_timeline_flag"] = (purchase < listing) if purchase is not None and listing is not None else False
    for c in ["listing_after_close_flag", "purchase_after_close_flag", "negative_timeline_flag"]:
        print(f"  {c}: {int(df[c].sum()):,}")
    return df
 
 
def flag_geography(df):
    # coordinate quality
    lat, lon = df["Latitude"], df["Longitude"]
    df["missing_coords_flag"] = lat.isnull() | lon.isnull()
    df["zero_coords_flag"] = (lat == 0) | (lon == 0)
    df["positive_longitude_flag"] = lon > 0
    usable = ~df["missing_coords_flag"] & ~df["zero_coords_flag"]
    outside = ~lat.between(*CA_LAT) | ~lon.between(*CA_LON)
    # positive longitudes counted separately
    df["out_of_state_flag"] = usable & outside & ~df["positive_longitude_flag"]
    df["invalid_coords_flag"] = df[["missing_coords_flag", "zero_coords_flag",
                                    "positive_longitude_flag", "out_of_state_flag"]].any(axis=1)
 
    summary = df[["missing_coords_flag", "zero_coords_flag", "positive_longitude_flag",
                  "out_of_state_flag", "invalid_coords_flag"]].sum().to_frame("records")
    summary["pct"] = (summary["records"] / len(df) * 100).round(2)
    print(summary.to_string())
    return df, summary
 
 
def clean(name, cfg):
    print("\n" + "=" * 70)
    print(f"{name.upper()}")
    print("=" * 70)
 
    df = pd.read_csv(os.path.join(DATA_DIR, cfg["input"]), low_memory=False)
    rows_in, cols_in = df.shape
    print(f"Loaded {cfg['input']}: {rows_in:,} rows, {cols_in} columns")
 
    print("\nStep 2 - redundant columns")
    df = drop_redundant_columns(df)
 
    print("\nStep 3 - data types")
    df = convert_types(df)
 
    print("\nSteps 4-5 - duplicates")
    df = drop_duplicates(df, cfg["latest_by"])
 
    print("\nStep 6 - missing values")
    df = drop_missing_required(df, cfg["required"])
 
    print("\nStep 7 - invalid numeric values")
    df = flag_invalid_numeric(df)
 
    print("\nStep 8 - date consistency flags")
    df = flag_dates(df)
 
    print("\nStep 9 - geographic data quality")
    df, geo = flag_geography(df)
    geo.to_csv(os.path.join(DATA_DIR, f"{name.lower()}_geo_quality_summary.csv"))
 
    print("\nStep 10 - save")
    flagged_path = os.path.join(DATA_DIR, f"{name.lower()}_flagged.csv")
    df.to_csv(flagged_path, index=False)
    print(f"  Saved full flagged dataset: {flagged_path} ({len(df):,} rows)")
 
    before = len(df)
    cleaned = df[~df["invalid_numeric_flag"]]
    log("Invalid numeric values", before, len(cleaned),
        "These values are impossible (e.g. a $0 sale), so they're excluded.")
    clean_path = os.path.join(DATA_DIR, f"{name.lower()}_clean.csv")
    cleaned.to_csv(clean_path, index=False)
    print(f"  Saved cleaned dataset: {clean_path}")
 
    print(f"\n{name} BEFORE/AFTER: {rows_in:,} -> {len(cleaned):,} rows, "
          f"{cols_in} -> {cleaned.shape[1]} columns")
 
    print(f"\n{name} data type confirmation (key fields):")
    key = [c for c in DATE_FIELDS + NUMERIC_FIELDS if c in cleaned.columns]
    print(cleaned[key].dtypes.to_string())
    return cleaned
 

def main():
    for name, cfg in DATASETS.items():
        clean(name, cfg)

 
if __name__ == "__main__":
    main()
