import glob
import os
 
import numpy as np
import pandas as pd
 
DATA_DIR = "data/processed"
SCHOOL_DIR = "data/raw/school_districts"
INPUT = os.path.join(DATA_DIR, "sold_clean.csv")
OUTPUT = os.path.join(DATA_DIR, "sold_features.csv")
 
DATE_FIELDS = ["CloseDate", "PurchaseContractDate", "ListingContractDate"]
METRICS = ["price_ratio", "close_to_original_list_ratio", "price_per_sqft",
           "DaysOnMarket", "listing_to_contract_days", "contract_to_close_days"]
 
# prints large numbers instead of using e
pd.set_option("display.float_format", "{:,.2f}".format)
pd.set_option("display.width", 200)
 
# candidate column names for the district name in the boundary file
DISTRICT_NAME_COLUMNS = ["DistrictName", "DISTRICT", "District", "NAME", "Name"]
 
 
def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
 
 
def safe_divide(numerator, denominator):
    """Divide, returning NaN where the denominator is missing or not positive."""
    return numerator / denominator.where(denominator > 0)
 
 
def add_metrics(df):
    for c in DATE_FIELDS:
        df[c] = pd.to_datetime(df[c], errors="coerce")
 
    # pricing metrics
    df["price_ratio"] = safe_divide(df["ClosePrice"], df["ListPrice"])
    df["close_to_original_list_ratio"] = safe_divide(df["ClosePrice"], df["OriginalListPrice"])
    df["price_per_sqft"] = safe_divide(df["ClosePrice"], df["LivingArea"])
 
    # time-series fields from closeDate
    df["Year"] = df["CloseDate"].dt.year
    df["Month"] = df["CloseDate"].dt.month
    df["YrMo"] = df["CloseDate"].dt.strftime("%Y-%m")
 
    # timeline metrics in days
    df["listing_to_contract_days"] = (df["PurchaseContractDate"] - df["ListingContractDate"]).dt.days
    df["contract_to_close_days"] = (df["CloseDate"] - df["PurchaseContractDate"]).dt.days
 
    # blank negative durations so they don't drag averages down
    for c in ["listing_to_contract_days", "contract_to_close_days"]:
        negative = (df[c] < 0).sum()
        df.loc[df[c] < 0, c] = np.nan
        print(f"  {c}: {negative:,} negative values set to blank")
    return df

def add_school_districts(df):
    files = (glob.glob(os.path.join(SCHOOL_DIR, "*.geojson"))
             + glob.glob(os.path.join(SCHOOL_DIR, "*.shp")))
    if not files:
        print(f"  Skipped: no .geojson or .shp file found in {SCHOOL_DIR}/")
        return df
    try:
        import geopandas as gpd
    except ImportError:
        print("  Skipped: geopandas isn't installed (python -m pip install geopandas)")
        return df
 
    districts = gpd.read_file(files[0]).to_crs("EPSG:4326")
    name_col = next((c for c in DISTRICT_NAME_COLUMNS if c in districts.columns), None)
    if name_col is None:
        print(f"  Skipped: no district name column found. Columns are: {list(districts.columns)}")
        print("  Add the right one to DISTRICT_NAME_COLUMNS and rerun.")
        return df
 
    # rows with usable coordinates can be placed in a district
    usable = df["Latitude"].notna() & df["Longitude"].notna() & (df["Longitude"] < 0)
    if "invalid_coords_flag" in df.columns:
        usable &= ~df["invalid_coords_flag"].astype(bool)
    points = gpd.GeoDataFrame(
        df.loc[usable, []],
        geometry=gpd.points_from_xy(df.loc[usable, "Longitude"], df.loc[usable, "Latitude"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points, districts[[name_col, "geometry"]], how="left", predicate="within")
    # A point on a shared border can match two districts; keep the first
    joined = joined[~joined.index.duplicated(keep="first")]
    df["school_district"] = joined[name_col].reindex(df.index)
 
    matched = df["school_district"].notna().sum()
    print(f"  Using {os.path.basename(files[0])}, name column '{name_col}'")
    print(f"  Rows matched to a school district: {matched:,} ({matched / len(df):.1%})")
    return df
 
 
def segment_summary(df, by, label):
    summary = (
        df.groupby(by, dropna=False)
        .agg(
            sales=("ClosePrice", "size"),
            total_volume=("ClosePrice", "sum"),
            median_close_price=("ClosePrice", "median"),
            median_price_per_sqft=("price_per_sqft", "median"),
            median_dom=("DaysOnMarket", "median"),
            avg_price_ratio=("price_ratio", "mean"),
            avg_close_to_original=("close_to_original_list_ratio", "mean"),
            median_listing_to_contract=("listing_to_contract_days", "median"),
            median_contract_to_close=("contract_to_close_days", "median"),
        )
        .sort_values("sales", ascending=False)
        .round(3)
    )
    path = os.path.join(DATA_DIR, f"segment_{label}.csv")
    summary.to_csv(path)
    print(f"\nBy {' + '.join(by)} (top 10 of {len(summary):,}, full table in {path}):")
    print(summary.head(10).to_string())
    return summary
 
 
def main():
    df = pd.read_csv(INPUT, low_memory=False)
    print(f"Loaded {INPUT}: {len(df):,} rows")
 
    section("1. ENGINEERED METRICS")
    df = add_metrics(df)
 
    section("2. SCHOOL DISTRICTS")
    df = add_school_districts(df)
 
    section("3. SAMPLE OUTPUT (new columns populated)")
    sample_cols = (["ListingKey", "CloseDate", "ClosePrice", "ListPrice", "OriginalListPrice",
                    "LivingArea", "Year", "Month", "YrMo"] + METRICS
                   + (["school_district"] if "school_district" in df.columns else []))
    print(df[[c for c in sample_cols if c in df.columns]].head(10).to_string())
 
    print("\nMetric summary:")
    print(df[METRICS].describe(percentiles=[0.25, 0.5, 0.75]).T.round(3).to_string())
    print("\nPopulated (non-blank) rows per new column:")
    print(df[METRICS + ["Year", "Month", "YrMo"]].notna().sum().to_string())
 
    section("4. SEGMENT ANALYSIS")
    segment_summary(df, ["PropertyType", "PropertySubType"], "property_type")
    segment_summary(df, ["CountyOrParish"], "county")
    segment_summary(df, ["CountyOrParish", "MLSAreaMajor"], "county_mls_area")
    segment_summary(df, ["ListOfficeName"], "list_office")
    segment_summary(df, ["BuyerOfficeName"], "buyer_office")
 
    section("5. SAVE")
    df.to_csv(OUTPUT, index=False)
    print(f"Saved {OUTPUT}: {len(df):,} rows, {df.shape[1]} columns")
 
 
if __name__ == "__main__":
    main()