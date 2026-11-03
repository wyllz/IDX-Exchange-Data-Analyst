"""
Week 8 Tableau dashboard preperation

This script turns the week 4-7 outputs into small, Tableau-friendly CSVs and computes the numbers each graph should show

Inputs (data/processed/):
    sold_outliers_flagged.csv week 7: every cleaned sale, with outlier flags
    listings_clean.csv        week 4-5: cleaned listings
"""

import os
from datetime import date
 
import pandas as pd
 
DATA_DIR = "data/processed"
OUT_DIR = "data/tableau"
SOLD_IN = os.path.join(DATA_DIR, "sold_outliers_flagged.csv")
LISTINGS_IN = os.path.join(DATA_DIR, "listings_clean.csv")
 
START_MONTH = pd.Period("2024-01", freq="M")
TOP_N = 100
 
# Columns each Tableau data source keeps. Missing ones are skipped with a note.
GEO_COLUMNS = ["City", "CountyOrParish", "PostalCode", "PropertySubType"]
SOLD_COLUMNS = [
    "ListingKey", "CloseDate", "YrMo", "Year", "Month",
    "ClosePrice", "ListPrice", "OriginalListPrice", "LivingArea",
    "price_per_sqft", "price_ratio", "close_to_original_list_ratio",
    "DaysOnMarket", "listing_to_contract_days", "contract_to_close_days",
    "BedroomsTotal", "BathroomsTotalInteger", "YearBuilt",
    *GEO_COLUMNS, "MLSAreaMajor", "Latitude", "Longitude",
    "ListAgentFullName", "ListOfficeName", "BuyerOfficeName",
    "rate_30yr_fixed", "school_district",
    "any_outlier_flag", "invalid_coords_flag",
]
LISTING_COLUMNS = [
    "ListingKey", "ListingContractDate", "ListPrice", "OriginalListPrice",
    "LivingArea", "BedroomsTotal", "BathroomsTotalInteger",
    *GEO_COLUMNS, "MLSAreaMajor", "Latitude", "Longitude",
    "ListAgentFullName", "ListOfficeName", "MlsStatus", "rate_30yr_fixed",
]


pd.set_option("display.float_format", "{:,.2f}".format)
pd.set_option("display.width", 200)

def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

def keep_columns(df, wanted, name):
    present = [c for c in wanted if c in df.columns]
    missing = [c for c in wanted if c not in df.columns]
    if missing:
        print(f"  {name}: columns not found, skipped: {missing}")
    return df[present].copy()
 
 
def clean_zip(series):
    """Zip codes are labels: 5-character text so Tableau maps them as postal codes."""
    s = series.astype("string").str.extract(r"(\d{5})", expand=False)
    return s

def last_completed_month():
    return pd.Period(date.today(), freq="M") - 1
 
 
def in_window(month, end):
    return (month >= START_MONTH) & (month <= end)
 
 
def prep_sold(end):
    df = pd.read_csv(SOLD_IN, low_memory=False)
    print(f"Loaded {SOLD_IN}: {len(df):,} rows")
    df["CloseDate"] = pd.to_datetime(df["CloseDate"], errors="coerce")
    month = df["CloseDate"].dt.to_period("M")
    before = len(df)
    df = df[in_window(month, end)].copy()
    print(f"  Kept closings from {START_MONTH} to {end}: {before:,} -> {len(df):,} rows")
 
    # Week 6 already built these; rebuild only if an older file is missing them
    df["YrMo"] = df["CloseDate"].dt.strftime("%Y-%m")
    df["Year"] = df["CloseDate"].dt.year
    df["Month"] = df["CloseDate"].dt.month
    if "any_outlier_flag" not in df.columns:
        print("  WARNING: any_outlier_flag not found; run 07_outliers.py first. "
              "Treating every row as not an outlier.")
        df["any_outlier_flag"] = False
    df["any_outlier_flag"] = df["any_outlier_flag"].astype(str).str.lower().eq("true")
 
    df = keep_columns(df, SOLD_COLUMNS, "Sold")
    if "PostalCode" in df.columns:
        df["PostalCode"] = clean_zip(df["PostalCode"])
    return df
 
 
def prep_listings(end):
    df = pd.read_csv(LISTINGS_IN, low_memory=False)
    print(f"Loaded {LISTINGS_IN}: {len(df):,} rows")
    df["ListingContractDate"] = pd.to_datetime(df["ListingContractDate"], errors="coerce")
    month = df["ListingContractDate"].dt.to_period("M")
    before = len(df)
    df = df[in_window(month, end)].copy()
    print(f"  Kept listings dated {START_MONTH} to {end}: {before:,} -> {len(df):,} rows")
 
    df = keep_columns(df, LISTING_COLUMNS, "Listings")
    df["YrMo"] = df["ListingContractDate"].dt.strftime("%Y-%m")
    if "PostalCode" in df.columns:
        df["PostalCode"] = clean_zip(df["PostalCode"])
    return df
 
 
def market_activity(sold, listings):
    """Stack sales and new listings so one Tableau source drives the comparison chart."""
    cols = ["ListingKey", "YrMo", *GEO_COLUMNS]
    s = sold[[c for c in cols if c in sold.columns]].assign(
        activity_type="Closed Sale", activity_date=sold["CloseDate"],
        price=sold["ClosePrice"])
    l = listings[[c for c in cols if c in listings.columns]].assign(
        activity_type="New Listing", activity_date=listings["ListingContractDate"],
        price=listings["ListPrice"])
    return pd.concat([s, l], ignore_index=True)
 
 
def monthly_checks(sold, listings):
    typical = sold[~sold["any_outlier_flag"]]
    monthly = typical.groupby("YrMo").agg(
        median_close_price=("ClosePrice", "median"),
        avg_days_on_market=("DaysOnMarket", "mean"),
        avg_close_to_original_list_ratio=("close_to_original_list_ratio", "mean"),
        closed_sales_filtered=("ClosePrice", "size"),
    )
    monthly["closed_sales_all"] = sold.groupby("YrMo").size()
    monthly["new_listings"] = listings.groupby("YrMo").size()
    monthly = monthly.fillna({"new_listings": 0, "closed_sales_all": 0})
    return monthly.round(3)
 
 
def top_n(sold, by, label):
    """Top N by volume and by units. Every row counts (see the outlier decision)."""
    named = sold[sold[by].notna() & (sold[by].astype(str).str.strip() != "")]
    unnamed = len(sold) - len(named)
    g = named.groupby(by).agg(
        sales_volume=("ClosePrice", "sum"),
        units=("ClosePrice", "size"),
        median_close_price=("ClosePrice", "median"),
    )
    g["rank_by_volume"] = g["sales_volume"].rank(ascending=False, method="min").astype(int)
    g["rank_by_units"] = g["units"].rank(ascending=False, method="min").astype(int)
    out = g[(g["rank_by_volume"] <= TOP_N) | (g["rank_by_units"] <= TOP_N)]
    out = out.sort_values("rank_by_volume")
    path = os.path.join(OUT_DIR, f"check_top100_{label}.csv")
    out.to_csv(path)
    print(f"\nTop {TOP_N} {label} (top 10 by volume shown; {unnamed:,} sales had no {by}):")
    print(out.head(10).to_string())
    print(f"  Saved {path} ({len(out):,} rows: in the top {TOP_N} by volume or by units)")
    return out
 
 
def zip_summary(sold):
    z = sold.dropna(subset=["PostalCode"]).groupby("PostalCode").agg(
        city=("City", lambda s: s.mode().iat[0] if not s.mode().empty else None),
        county=("CountyOrParish", lambda s: s.mode().iat[0] if not s.mode().empty else None),
        median_close_price=("ClosePrice", "median"),
        homes_sold=("ClosePrice", "size"),
    ).sort_values("homes_sold", ascending=False)
    return z
 
 
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    end = last_completed_month()
    report = [f"WEEK 8 TABLEAU PREP - {date.today():%Y-%m-%d}", ""]
 
    section("1. SOLD DATA SOURCE")
    sold = prep_sold(end)
    path = os.path.join(OUT_DIR, "tableau_sold.csv")
    sold.to_csv(path, index=False)
    n_typical = int((~sold["any_outlier_flag"]).sum())
    print(f"  Saved {path}: {len(sold):,} rows, {sold.shape[1]} columns "
          f"({n_typical:,} not flagged as outliers)")
 
    section("2. LISTINGS DATA SOURCE")
    listings = prep_listings(end)
    path = os.path.join(OUT_DIR, "tableau_listings.csv")
    listings.to_csv(path, index=False)
    print(f"  Saved {path}: {len(listings):,} rows, {listings.shape[1]} columns")
 
    activity = market_activity(sold, listings)
    path = os.path.join(OUT_DIR, "tableau_market_activity.csv")
    activity.to_csv(path, index=False)
    print(f"  Saved {path}: {len(activity):,} rows "
          f"({activity['activity_type'].value_counts().to_dict()})")
 
    section("3. DATE COVERAGE")
    sold_months = sorted(sold["YrMo"].dropna().unique())
    list_months = sorted(listings["YrMo"].dropna().unique())
    expected = [str(p) for p in pd.period_range(START_MONTH, end, freq="M")]
    gaps = {"Sold": [m for m in expected if m not in sold_months],
            "Listings": [m for m in expected if m not in list_months]}
    print(f"  Expected months: {expected[0]} to {expected[-1]} ({len(expected)})")
    for name, months in [("Sold", sold_months), ("Listings", list_months)]:
        span = f"{months[0]} to {months[-1]}" if months else "none"
        print(f"  {name}: {span} ({len(months)} months), missing: {gaps[name] or 'none'}")
        report.append(f"{name} months: {span} ({len(months)}); missing: {gaps[name] or 'none'}")
 
    section("4. CHECK TABLE - market_analysis.twbx (no filters, outliers excluded)")
    monthly = monthly_checks(sold, listings)
    path = os.path.join(OUT_DIR, "check_monthly_market.csv")
    monthly.to_csv(path)
    print(monthly.to_string())
    print(f"  Saved {path}")
 
    # Small month-to-month dips at the end usually mean late-reported sales
    if len(monthly) >= 2:
        last, prev = monthly.iloc[-1], monthly.iloc[-2]
        if last["closed_sales_all"] < 0.8 * prev["closed_sales_all"]:
            print(f"  NOTE: {monthly.index[-1]} has {last['closed_sales_all']:,.0f} sales vs "
                  f"{prev['closed_sales_all']:,.0f} the month before. If the data was pulled "
                  "early in the month, recent closings may still be missing.")
 
    section("5. CHECK TABLES - competitive_analysis.twbx (all rows)")
    top_n(sold, "ListAgentFullName", "agents")
    top_n(sold, "ListOfficeName", "offices")
 
    if "PostalCode" in sold.columns:
        zips = zip_summary(sold)
        path = os.path.join(OUT_DIR, "check_zip_summary.csv")
        zips.to_csv(path)
        print(f"\nZip codes: {len(zips):,} (top 10 by homes sold):")
        print(zips.head(10).to_string())
        print(f"  Saved {path}")
        missing_zip = sold["PostalCode"].isna().sum()
        print(f"  Sales without a valid 5-digit zip (left off the heat maps): {missing_zip:,}")
        report.append(f"Sales without a valid zip: {missing_zip:,}")
 
    section("6. REPORT")
    report += [
        f"Sold rows: {len(sold):,} (not outliers: {n_typical:,})",
        f"Listings rows: {len(listings):,}",
    ]
    if len(monthly):
        latest = monthly.iloc[-1]
        report.append(f"Latest month {monthly.index[-1]}: median close price "
                      f"${latest['median_close_price']:,.0f}, closed sales "
                      f"{latest['closed_sales_all']:,.0f}, new listings "
                      f"{latest['new_listings']:,.0f}")
    report += [
        "",
        "Outlier rule: market_analysis.twbx filters any_outlier_flag = False; "
        "competitive_analysis.twbx keeps every sale so volume is not understated.",
        "New listings are counted by ListingContractDate month; closed sales by CloseDate month.",
    ]
    text = "\n".join(report)
    with open(os.path.join(OUT_DIR, "tableau_prep_report.txt"), "w") as f:
        f.write(text + "\n")
    print(text)
 
 
if __name__ == "__main__":
    main()