import glob
import os

import matplotlib
matplotlib.use("Agg")  # save plots to files w/o opening windows
import matplotlib.pyplot as plt
import pandas as pd

RAW_DIR = "data/raw"
OUT_DIR = "data/processed"
FIG_DIR = "figures"
START_MONTH = "202401"

# fields 
NUMERIC_FIELDS = [
    "ClosePrice", "ListPrice", "OriginalListPrice", "LivingArea", "LotSizeAcres",
    "BedroomsTotal", "BathroomsTotalInteger", "DaysOnMarket", "YearBuilt",
]
SUMMARY_FIELDS = ["ClosePrice", "LivingArea", "DaysOnMarket"]
DATE_FIELDS = ["CloseDate", "ListingContractDate", "PurchaseContractDate",
               "ContractStatusChangeDate"]

# core fields 
CORE_FIELDS = set(NUMERIC_FIELDS + DATE_FIELDS + [
    "ListingKey", "PropertyType", "PropertySubType", "City", "CountyOrParish",
    "PostalCode", "MLSAreaMajor", "Latitude", "Longitude", "ListOfficeName",
    "BuyerOfficeName", "ListAgentFullName", "MlsStatus",
])

# market analysis fields vs metadata fields
MARKET_FIELDS = CORE_FIELDS | {
    "ParkingTotal", "GarageSpaces", "Stories", "Levels", "NewConstructionYN",
    "AssociationFee", "TaxAnnualAmount", "LotSizeSquareFeet", "FireplaceYN",
    "ElementarySchoolDistrict", "HighSchoolDistrict", "SubdivisionName",
}

PERCENTILES = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def load_all_sold():
    """monthly sold file from Jan 2024 on w/o filtering."""
    files = sorted(
        f for f in glob.glob(os.path.join(RAW_DIR, "CRMLSSold*.csv"))
        if os.path.basename(f)[9:15] >= START_MONTH
    )
    frames = [pd.read_csv(f, low_memory=False) for f in files]
    df = pd.concat(frames, ignore_index=True)
    print(f"Loaded {len(files)} Sold files: {len(df):,} rows")
    return df


def property_types(df):
    """property type and its share, keepds residents only"""
    section("1. PROPERTY TYPES AND FILTER")
    print("Unique property types:", sorted(df["PropertyType"].dropna().unique()))
    shares = pd.DataFrame({
        "count": df["PropertyType"].value_counts(dropna=False),
        "share_pct": (df["PropertyType"].value_counts(dropna=False, normalize=True) * 100).round(2),
    })
    print(shares.to_string())

    # keep exact matches of PropertyType == 'Residential'.
    res = df[df["PropertyType"] == "Residential"].copy()
    print(f"\nFilter: PropertyType == 'Residential'")
    print(f"Rows before: {len(df):,}  after: {len(res):,}  ({len(res) / len(df):.1%} kept)")
    return res


def structure(df):
    """rows, columns, data types, and market vs metadata field split."""
    section("2. DATASET STRUCTURE")
    print(f"Rows: {len(df):,}   Columns: {df.shape[1]}")
    print("\nColumn data types:")
    print(df.dtypes.value_counts().to_string())
    print()
    print(df.dtypes.to_string())

    market = [c for c in df.columns if c in MARKET_FIELDS]
    metadata = [c for c in df.columns if c not in MARKET_FIELDS]
    print(f"\nMarket analysis fields ({len(market)}): {market}")
    print(f"\nMetadata fields ({len(metadata)}): {metadata}")


def missing_report(df):
    """null counts and percentages per column; flag and drop >90% null non-core columns."""
    section("3. MISSING VALUE REPORT")
    nulls = df.isnull().sum().to_frame("null_count")
    nulls["null_pct"] = (nulls["null_count"] / len(df) * 100).round(2)
    nulls["over_90_pct"] = nulls["null_pct"] > 90
    nulls["core_field"] = nulls.index.isin(CORE_FIELDS)
    nulls["decision"] = "keep"
    nulls.loc[nulls["over_90_pct"] & ~nulls["core_field"], "decision"] = "drop"
    nulls = nulls.sort_values("null_pct", ascending=False)

    print(nulls.to_string())
    flagged = nulls[nulls["over_90_pct"]]
    print(f"\nColumns over 90% null: {len(flagged)}")
    print(flagged[["null_pct", "core_field", "decision"]].to_string())

    nulls.to_csv(os.path.join(OUT_DIR, "missing_value_report.csv"))
    return nulls.index[nulls["decision"] == "drop"].tolist()


def numeric_distributions(df):
    """percentile summaries, histograms and boxplots for the key numeric fields."""
    section("4. NUMERIC DISTRIBUTIONS")
    fields = [c for c in NUMERIC_FIELDS if c in df.columns]
    for c in fields:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    summary = df[fields].describe(percentiles=PERCENTILES).T
    summary.insert(summary.columns.get_loc("mean") + 1, "median", df[fields].median())
    print(summary.round(2).to_string())
    summary.to_csv(os.path.join(OUT_DIR, "numeric_distribution_summary.csv"))

    print("\nRequired summary (ClosePrice, LivingArea, DaysOnMarket):")
    print(summary.loc[[c for c in SUMMARY_FIELDS if c in fields],
                      ["min", "1%", "25%", "median", "mean", "75%", "99%", "max"]].round(2).to_string())

    # extreme outliers
    print("\nPossible extreme values (flag for later, not removed):")
    for c in fields:
        s = df[c].dropna()
        if s.empty:
            continue
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        extreme = ((s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)).sum()
        nonpositive = (s <= 0).sum()
        print(f"  {c}: {extreme:,} beyond 3xIQR, {nonpositive:,} values <= 0")

    for c in fields:
        s = df[c].dropna()
        if s.empty:
            continue
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
        # clip the plotted range at the 99th percentile while maintaining visible shape
        s.clip(upper=s.quantile(0.99)).plot.hist(bins=50, ax=ax1)
        ax1.set_title(f"{c} histogram (capped at 99th pct)")
        ax1.set_xlabel(c)
        ax2.boxplot(s)
        ax2.set_title(f"{c} boxplot (all values)")
        ax2.set_ylabel(c)
        fig.tight_layout()
        fig.savefig(os.path.join(FIG_DIR, f"{c}_distribution.png"), dpi=120)
        plt.close(fig)
    print(f"\nSaved histograms and boxplots to {FIG_DIR}/")


def eda_questions(df, all_types):
    """suggested questions"""
    section("5. EDA QUESTIONS")

    res_share = (all_types["PropertyType"] == "Residential").mean()
    print(f"Q1 Residential share of all Sold records: {res_share:.1%} "
          f"(other types: {1 - res_share:.1%})")

    print(f"Q2 Median close price: ${df['ClosePrice'].median():,.0f}   "
          f"Mean close price: ${df['ClosePrice'].mean():,.0f}")

    dom = df["DaysOnMarket"].dropna()
    print(f"Q3 Days on market: median {dom.median():.0f}, mean {dom.mean():.1f}, "
          f"90th pct {dom.quantile(0.9):.0f}, negative values {(dom < 0).sum():,}")

    both = df.dropna(subset=["ClosePrice", "ListPrice"])
    above = (both["ClosePrice"] > both["ListPrice"]).mean()
    at = (both["ClosePrice"] == both["ListPrice"]).mean()
    below = (both["ClosePrice"] < both["ListPrice"]).mean()
    print(f"Q4 Sold vs list price: above {above:.1%}, at {at:.1%}, below {below:.1%}")

    dates = {c: pd.to_datetime(df[c], errors="coerce") for c in DATE_FIELDS if c in df.columns}
    close_before_list = (dates["CloseDate"] < dates["ListingContractDate"]).sum()
    close_before_contract = (dates["CloseDate"] < dates["PurchaseContractDate"]).sum()
    contract_before_list = (dates["PurchaseContractDate"] < dates["ListingContractDate"]).sum()
    print(f"Q5 Date issues: close before listing {close_before_list:,}, "
          f"close before purchase contract {close_before_contract:,}, "
          f"purchase contract before listing {contract_before_list:,}")

    county = (df.groupby("CountyOrParish")["ClosePrice"]
                .agg(median_price="median", sales="count")
                .query("sales >= 50")  # ignores counties with very few sales
                .sort_values("median_price", ascending=False))
    print("Q6 Counties with the highest median close price (50+ sales):")
    print(county.head(10).to_string())


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    sold_all = load_all_sold()
    sold = property_types(sold_all)
    structure(sold)
    drop_cols = missing_report(sold)
    numeric_distributions(sold)
    eda_questions(sold, sold_all)

    section("6. SAVE FILTERED DATASET")
    print(f"Dropping {len(drop_cols)} non-core columns over 90% null: {drop_cols}")
    filtered = sold.drop(columns=drop_cols)
    path = os.path.join(OUT_DIR, "sold_residential_filtered.csv")
    filtered.to_csv(path, index=False)
    print(f"Saved {path}: {len(filtered):,} rows, {filtered.shape[1]} columns")


if __name__ == "__main__":
    main()
