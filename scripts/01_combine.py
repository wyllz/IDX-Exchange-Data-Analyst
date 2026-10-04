import os
from datetime import date

import pandas as pd

RAW_DIR = "data/raw"
OUT_DIR = "data/processed"
START_MONTH = "2024-01"


def last_completed_month():
    """The month before today's month, e.g. 2026-09 when run in October 2026."""
    today = date.today()
    return (pd.Period(today, freq="M") - 1).strftime("%Y-%m")


def combine(prefix, months):
    """Read one CSV per month for this prefix and stack them into one DataFrame."""
    frames = []
    missing = []
    total_rows = 0

    print(f"\n=== {prefix} ===")
    for m in months:
        path = os.path.join(RAW_DIR, f"{prefix}{m.strftime('%Y%m')}.csv")
        if not os.path.exists(path):
            missing.append(m.strftime("%Y%m"))
            continue
        df = pd.read_csv(path, low_memory=False)
        print(f"  {os.path.basename(path)}: {len(df):,} rows")
        total_rows += len(df)
        frames.append(df)

    if missing:
        print(f"  WARNING - missing months: {missing}")

    combined = pd.concat(frames, ignore_index=True)

    print(f"  Files loaded: {len(frames)} of {len(months)}")
    print(f"  Before concatenation (sum of monthly files): {total_rows:,}")
    print(f"  After concatenation (combined dataset):      {len(combined):,}")

    # Concatenation should never add or drop rows
    assert len(combined) == total_rows, "Row count changed during concatenation"
    return combined


def filter_residential(df, name):
    """Keep only Residential properties and report counts before and after."""
    print(f"\n{name} PropertyType breakdown (before filter):")
    print(df["PropertyType"].value_counts(dropna=False).to_string())

    residential = df[df["PropertyType"] == "Residential"].copy()

    print(f"  Before Residential filter: {len(df):,}")
    print(f"  After Residential filter:  {len(residential):,} "
          f"({len(residential) / len(df):.1%} of rows kept)")
    return residential


def main():
    end_month = last_completed_month()
    months = pd.period_range(START_MONTH, end_month, freq="M")
    print(f"Months covered: {START_MONTH} to {end_month} ({len(months)} months)")

    # Concatenate monthly files
    sold = combine("CRMLSSold", months)
    listings = combine("CRMLSListing", months)

    # Keep Residential only
    sold_res = filter_residential(sold, "Sold")
    listings_res = filter_residential(listings, "Listings")

    # Save the combined Residential datasets
    os.makedirs(OUT_DIR, exist_ok=True)
    sold_path = os.path.join(OUT_DIR, "sold_combined_residential.csv")
    listings_path = os.path.join(OUT_DIR, "listings_combined_residential.csv")
    sold_res.to_csv(sold_path, index=False)
    listings_res.to_csv(listings_path, index=False)

    print(f"\nSaved {sold_path} ({len(sold_res):,} rows)")
    print(f"Saved {listings_path} ({len(listings_res):,} rows)")


if __name__ == "__main__":
    main()
