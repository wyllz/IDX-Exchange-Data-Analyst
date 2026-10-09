import os
import pandas as pd

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
OUT_DIR = "data/processed"
SOLD_IN = os.path.join(OUT_DIR, "sold_combined_residential.csv")
LISTINGS_IN = os.path.join(OUT_DIR, "listings_combined_residential.csv")


def fetch_mortgage_monthly():
    # fetching weekly rates from FRED
    mortgage = pd.read_csv(FRED_URL, parse_dates=["observation_date"])
    mortgage.columns = ["date", "rate_30yr_fixed"]
    mortgage["rate_30yr_fixed"] = pd.to_numeric(mortgage["rate_30yr_fixed"], errors="coerce")
    print(f"FRED weekly rows: {len(mortgage):,} "
          f"({mortgage['date'].min():%Y-%m-%d} to {mortgage['date'].max():%Y-%m-%d})")

    # resample weekly rates to monthly averages
    mortgage["year_month"] = mortgage["date"].dt.to_period("M")
    monthly = (
        mortgage.groupby("year_month")["rate_30yr_fixed"]
        .mean()
        .round(3)
        .reset_index()
    )
    print(f"FRED monthly rows: {len(monthly):,} "
          f"({monthly['year_month'].min()} to {monthly['year_month'].max()})")
    return monthly


def enrich(df, date_col, monthly, name):
    # create year_month key from the transaction date
    df["year_month"] = pd.to_datetime(df[date_col], errors="coerce").dt.to_period("M")
    missing_dates = df["year_month"].isnull().sum()

    # left merge so no MLS rows are lost
    before = len(df)
    merged = df.merge(monthly, on="year_month", how="left")

    # validating the merge
    print(f"\n{name} (key: {date_col})")
    print(f"  Rows before merge: {before:,}   after merge: {len(merged):,}")
    assert len(merged) == before, f"{name}: merge changed the row count"

    null_rates = merged["rate_30yr_fixed"].isnull().sum()
    print(f"  Rows with missing {date_col}: {missing_dates:,}")
    print(f"  Null rate values after merge: {null_rates:,}")
    if null_rates:
        unmatched = merged.loc[merged["rate_30yr_fixed"].isnull(), "year_month"]
        print("  Unmatched year_month values:")
        print(unmatched.value_counts(dropna=False).to_string())
    else:
        print("  PASS: every row has a mortgage rate")

    print(merged[[date_col, "year_month", "rate_30yr_fixed"]].head().to_string())
    return merged


def main():
    monthly = fetch_mortgage_monthly()

    sold = pd.read_csv(SOLD_IN, low_memory=False)
    listings = pd.read_csv(LISTINGS_IN, low_memory=False)

    sold_with_rates = enrich(sold, "CloseDate", monthly, "Sold")
    listings_with_rates = enrich(listings, "ListingContractDate", monthly, "Listings")

    sold_out = os.path.join(OUT_DIR, "sold_with_rates.csv")
    listings_out = os.path.join(OUT_DIR, "listings_with_rates.csv")
    sold_with_rates.to_csv(sold_out, index=False)
    listings_with_rates.to_csv(listings_out, index=False)
    print(f"\nSaved {sold_out} ({len(sold_with_rates):,} rows)")
    print(f"Saved {listings_out} ({len(listings_with_rates):,} rows)")


if __name__ == "__main__":
    main()
