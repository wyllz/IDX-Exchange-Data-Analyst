import os
import pandas as pd

DATA_DIR = "data/processed"
INPUT = os.path.join(DATA_DIR, "sold_features.csv")

REQUIRED_FIELDS = ["ClosePrice", "LivingArea", "DaysOnMarket"]
EXTRA_FIELDS = ["price_per_sqft", "close_to_original_list_ratio"]
MEDIAN_FIELDS = REQUIRED_FIELDS + EXTRA_FIELDS
IQR_MULTIPLIER = 1.5

pd.set_option("display.float_format", "{:,.2f}".format)
pd.set_option("display.width", 200)

# iqr for lower/upper cutoff for one numeric column
def iqr_bounds(series):
    """Q1, Q3, IQR and the lower/upper cut-offs for one numeric column."""
    s = series.dropna()
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return {
        "Q1": q1, "Q3": q3, "IQR": iqr,
        "lower": q1 - IQR_MULTIPLIER * iqr,
        "upper": q3 + IQR_MULTIPLIER * iqr,
        "p01": s.quantile(0.01), "p99": s.quantile(0.99),
        "min": s.min(), "max": s.max(),
    }


def add_flags(df, fields):
    rows = []
    for c in fields:
        if c not in df.columns:
            print(f"  Skipped {c}: column not found")
            continue
        df[c] = pd.to_numeric(df[c], errors="coerce")
        b = iqr_bounds(df[c])
        flag = f"{c}_outlier_flag"
        # A missing value isn't an outlier, so comparisons with NaN stay False
        df[flag] = (df[c] < b["lower"]) | (df[c] > b["upper"])
        b.update({
            "field": c,
            "flagged_low": int((df[c] < b["lower"]).sum()),
            "flagged_high": int((df[c] > b["upper"]).sum()),
            "flagged_total": int(df[flag].sum()),
            "flagged_pct": round(df[flag].mean() * 100, 2),
        })
        rows.append(b)
    return df, pd.DataFrame(rows).set_index("field")


def main():
    df = pd.read_csv(INPUT, low_memory=False)
    print(f"Loaded {INPUT}: {len(df):,} rows")

    print("\n1. IQR BOUNDS AND FLAG COUNTS")
    df, bounds = add_flags(df, REQUIRED_FIELDS + EXTRA_FIELDS)
    print(bounds[["Q1", "Q3", "IQR", "lower", "upper", "p01", "p99",
                  "flagged_low", "flagged_high", "flagged_pct"]].to_string())
    bounds.to_csv(os.path.join(DATA_DIR, "outlier_bounds.csv"))

    required_flags = [f"{c}_outlier_flag" for c in REQUIRED_FIELDS if f"{c}_outlier_flag" in df.columns]
    df["any_outlier_flag"] = df[required_flags].any(axis=1)
    print(f"\nRows flagged on any required field: {df['any_outlier_flag'].sum():,} "
          f"({df['any_outlier_flag'].mean():.1%})")

    print("\n2. SAVE")
    flagged_path = os.path.join(DATA_DIR, "sold_outliers_flagged.csv")
    filtered_path = os.path.join(DATA_DIR, "sold_analysis_filtered.csv")
    filtered = df[~df["any_outlier_flag"]]
    df.to_csv(flagged_path, index=False)
    filtered.to_csv(filtered_path, index=False)
    print(f"  Full flagged dataset:   {flagged_path} ({len(df):,} rows)")
    print(f"  Clean filtered dataset: {filtered_path} ({len(filtered):,} rows)")

    print("\n3. BEFORE VS AFTER FILTERING")
    fields = [c for c in MEDIAN_FIELDS if c in df.columns]
    comparison = pd.DataFrame({
        "median_before": df[fields].median(),
        "median_after": filtered[fields].median(),
        "mean_before": df[fields].mean(),
        "mean_after": filtered[fields].mean(),
    })
    comparison["median_change_pct"] = (
        (comparison["median_after"] / comparison["median_before"] - 1) * 100).round(2)
    comparison["mean_change_pct"] = (
        (comparison["mean_after"] / comparison["mean_before"] - 1) * 100).round(2)
    print(comparison.to_string())
    comparison.to_csv(os.path.join(DATA_DIR, "outlier_comparison.csv"))

    # written comparison for the deliverable
    removed = len(df) - len(filtered)
    cp = comparison.loc["ClosePrice"]
    lines = [
        "WEEK 7 OUTLIER FILTERING - WRITTEN COMPARISON",
        "",
        f"Dataset size: {len(df):,} rows before filtering and {len(filtered):,} after. "
        f"{removed:,} rows ({removed / len(df):.1%}) were flagged as IQR outliers on "
        f"ClosePrice, LivingArea or DaysOnMarket and left out of the filtered dataset. "
        f"They remain in sold_outliers_flagged.csv.",
        "",
        f"ClosePrice: the median moved from ${cp['median_before']:,.0f} to "
        f"${cp['median_after']:,.0f} ({cp['median_change_pct']:+.1f}%), while the mean moved "
        f"from ${cp['mean_before']:,.0f} to ${cp['mean_after']:,.0f} ({cp['mean_change_pct']:+.1f}%).",
    ]
    for c in fields[1:]:
        r = comparison.loc[c]
        lines.append(f"{c}: median {r['median_before']:,.2f} -> {r['median_after']:,.2f} "
                     f"({r['median_change_pct']:+.1f}%), mean {r['mean_before']:,.2f} -> "
                     f"{r['mean_after']:,.2f} ({r['mean_change_pct']:+.1f}%).")
    if abs(cp["median_change_pct"]) < abs(cp["mean_change_pct"]):
        interpretation = (
            "Interpretation: the ClosePrice median moved less than the mean. The median "
            "depends on the middle of the distribution, while a small number of very "
            "expensive homes pull the mean up, so removing them shifts the mean most. "
            "This is why the dashboards report medians.")
    else:
        interpretation = (
            "Interpretation: unusually, the ClosePrice median moved at least as much as "
            "the mean. Check whether the flagged rows are concentrated in one price range "
            "or county before relying on the filtered dataset.")
    lines += [
        "",
        interpretation,
        "Outliers are flagged rather than deleted because luxury and distressed sales "
        "are real transactions that some analyses need.",
        "",
        "Note: IQR bounds are computed across all of California. Expensive counties will "
        "have more sales above the ClosePrice upper bound than cheaper ones, so check the "
        "flag rate by county before relying on the filtered dataset for county comparisons.",
    ]
    report = "\n".join(lines)
    with open(os.path.join(DATA_DIR, "outlier_report.txt"), "w") as f:
        f.write(report + "\n")
    print("\n" + report)

    print("\nFlag rate by county (top 10 by sales):")
    if "CountyOrParish" in df.columns:
        by_county = (df.groupby("CountyOrParish")["any_outlier_flag"]
                       .agg(sales="size", flagged_pct="mean")
                       .sort_values("sales", ascending=False).head(10))
        by_county["flagged_pct"] = (by_county["flagged_pct"] * 100).round(1)
        print(by_county.to_string())


if __name__ == "__main__":
    main()
