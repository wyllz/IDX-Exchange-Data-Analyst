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