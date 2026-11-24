# IDX Exchange Data Analyst Internship: California MLS Market Analytics

A Python and Tableau pipeline that turns monthly California MLS (CRMLS) transaction files into cleaned, enriched, analysis-ready datasets and interactive market and competitive dashboards.

> **Status: final prototype (Weeks 0 to 10 complete).** The data pipeline (Weeks 1 to 8) and both Tableau workbooks are built. The final report and presentation (Weeks 11 to 12) are still to come. Items marked **`[PLACEHOLDER]`** need a real value or link before this README is final.

---

## Table of contents

1. [Project goal](#project-goal)
2. [Data sources](#data-sources)
3. [Repository structure](#repository-structure)
4. [Pipeline overview](#pipeline-overview)
5. [Pipeline steps by week](#pipeline-steps-by-week)
6. [How to run](#how-to-run)
7. [Outputs and dashboards](#outputs-and-dashboards)
8. [Data quality findings](#data-quality-findings)
9. [Key results](#key-results)
10. [Tools used](#tools-used)
11. [Next steps](#next-steps)
12. [Data confidentiality](#data-confidentiality)

---

## Project goal

The IDX Exchange Data Analyst Internship is a 12-week program on how real estate analytics datasets are produced, cleaned and turned into housing market intelligence. This project follows the program's pipeline end to end:

| Phase | What it does | Weeks |
|---|---|---|
| Data aggregation | Combine monthly MLS files into multi-month datasets | 1 |
| Validation and enrichment | EDA, residential filtering, mortgage rate merge | 2 to 3 |
| Data cleaning | Types, duplicates, invalid values, date and geography flags | 4 to 5 |
| Market analytics | Engineer pricing and timeline metrics, segment summaries | 6 |
| Data quality | IQR outlier flagging and a filtered analysis dataset | 7 |
| Dashboard development | Tableau market and competitive workbooks | 8 to 10 |
| Market insights | 1-page market report and 5-minute presentation | 11 to 12 (next) |

**Analysis window:** January 2024 through the most recently completed calendar month at run time (the current build covers **January 2024 to March 2026, 27 months**).

---

## Data sources

| Source | Description | Used in |
|---|---|---|
| **CRMLS Sold files** (`CRMLSSoldYYYYMM.csv`) | One file per month of closed transactions, produced from the CoreLogic Trestle API by the IDX Exchange extraction pipeline | Weeks 1 to 8 |
| **CRMLS Listing files** (`CRMLSListingYYYYMM.csv`) | One file per month of listings | Weeks 1 to 8 |
| **FRED `MORTGAGE30US`** | Freddie Mac 30-year fixed mortgage rate, published weekly by the St. Louis Fed. Pulled live as CSV, no API key needed: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US` | Weeks 2 to 3 |
| **California School District Areas 2024-25** (optional) | District boundary file from data.ca.gov, used for a spatial join | Week 6 |

Most monthly files came pre-generated from the IDX Exchange FTP server. A few Sold months (2024-01, 2024-03 to 2024-07 and 2025-01) came from `_filled` files on the FTP and were renamed to the standard `CRMLSSoldYYYYMM.csv` pattern. Any remaining months were pulled with the extraction script. **`[PLACEHOLDER: list any months you pulled yourself with the extraction script, or write "none"]`**

Field definitions come from the Trestle Property Metadata document. The key fields used throughout are `ClosePrice`, `ListPrice`, `OriginalListPrice`, `LivingArea`, `DaysOnMarket`, the four contract and close dates, location fields (`City`, `CountyOrParish`, `PostalCode`, `MLSAreaMajor`, `Latitude`, `Longitude`) and agent and office fields (`ListAgentFullName`, `ListOfficeName`, `BuyerOfficeName`).

---

## Repository structure

The scripts expect to be run from the project root, `IDX-Exchange-Data-Analyst/`:

```
IDX-Exchange-Data-Analyst/
├── README.md
├── scripts/
│   ├── 01_combine.py           # Week 1    Combine monthly files, keep Residential
│   ├── 02_eda.py               # Weeks 2-3 EDA, missing value report, distributions
│   ├── 03_mortgage_rates.py    # Weeks 2-3 FRED mortgage rate enrichment
│   ├── 04_clean.py             # Weeks 4-5 Cleaning and data quality flags
│   ├── 06_features.py          # Week 6    Engineered metrics and segment summaries
│   ├── 07_outliers.py          # Week 7    IQR outlier flags and filtered dataset
│   └── 08_tableau_prep.py      # Week 8    Tableau data sources and check tables
├── data/
│   ├── raw/                    # Monthly CRMLS CSVs (not committed)
│   │   └── school_districts/   # Optional boundary file for Week 6
│   ├── processed/              # Pipeline outputs, Weeks 1-7 (not committed)
│   └── tableau/                # Tableau-ready CSVs and check tables (not committed)
├── figures/                    # Histograms and boxplots from 02_eda.py
└── tableau/
    ├── market_analysis.twbx
    └── competitive_analysis.twbx
```

There is no `05_` script: the handbook's Weeks 4 and 5 are one phase, handled by `04_clean.py`.

> MLS data is confidential, so `data/` should stay out of version control. Add `data/` to `.gitignore` if this is pushed to GitHub.

---

## Pipeline overview

Each script reads the previous step's output from `data/processed/`, so they run in order:

```
data/raw/CRMLSSold*.csv ─┐
data/raw/CRMLSListing*.csv ┘
        │
        ▼
01_combine.py ──────────► sold_combined_residential.csv, listings_combined_residential.csv
        │                       │
        │   02_eda.py ◄─────────┘ (reads raw files; reports + sold_residential_filtered.csv)
        ▼
03_mortgage_rates.py ───► sold_with_rates.csv, listings_with_rates.csv   (+ FRED)
        ▼
04_clean.py ────────────► sold_clean.csv, listings_clean.csv (+ *_flagged.csv)
        ▼
06_features.py ─────────► sold_features.csv (+ segment_*.csv)
        ▼
07_outliers.py ─────────► sold_outliers_flagged.csv, sold_analysis_filtered.csv
        ▼
08_tableau_prep.py ─────► data/tableau/tableau_sold.csv, tableau_listings.csv,
                          tableau_market_activity.csv, check_*.csv
        ▼
Tableau Desktop ────────► market_analysis.twbx, competitive_analysis.twbx
```

`02_eda.py` is a side branch. It documents the raw data and does not feed the main chain.

---

## Pipeline steps by week

### Week 0: MLS data pipeline orientation

Learned how the monthly CSVs are produced from the CoreLogic Trestle API (authentication, pagination, date filters, CSV export), downloaded the available `CRMLSListing` and `CRMLSSold` files from the IDX Exchange FTP, and reviewed the Trestle Property Metadata.

### Week 1: Monthly dataset aggregation (`01_combine.py`)

**Input:** `data/raw/CRMLSSoldYYYYMM.csv` and `CRMLSListingYYYYMM.csv`
**Output:** `data/processed/sold_combined_residential.csv`, `listings_combined_residential.csv`

- Builds the month list from 2024-01 to the last completed month (computed from today's date, so the window extends on its own).
- Loads one file per month for each prefix, reports per-file row counts, and warns about any missing months.
- Concatenates and **asserts that the combined row count equals the sum of the monthly files**.
- Prints the `PropertyType` breakdown, then keeps `PropertyType == 'Residential'` only, reporting rows before and after and the share kept.

### Weeks 2 to 3: Structuring and validation, EDA (`02_eda.py`)

**Input:** all raw Sold files from 2024-01 on
**Output:** `missing_value_report.csv`, `numeric_distribution_summary.csv`, `sold_residential_filtered.csv`, and `figures/<field>_distribution.png`

1. **Property types:** lists every type with counts and shares. The filter is an exact match on `Residential`, so `ResidentialLease`, `ResidentialIncome`, `Land`, `Commercial` and others are excluded.
2. **Structure:** row and column counts, data types, and a split of market analysis fields vs. metadata fields.
3. **Missing values:** null count and percentage per column. Columns over 90% null are flagged. Non-core ones are dropped, and core fields are kept even when partly missing.
4. **Numeric distributions:** min, max, mean, median and 1st to 99th percentiles for nine key fields, with `ClosePrice`, `LivingArea` and `DaysOnMarket` highlighted. Values beyond 3×IQR and values ≤ 0 are counted and left for Week 7. A histogram (capped at the 99th percentile so the shape is visible) and boxplot are saved per field.
5. **Handbook EDA questions:** Residential share, median and mean close price, DOM distribution, share sold above, at or below list, date consistency issues, and top counties by median price (50+ sales).

### Weeks 2 to 3: Mortgage rate enrichment (`03_mortgage_rates.py`)

**Input:** Week 1 outputs and FRED `MORTGAGE30US`
**Output:** `sold_with_rates.csv`, `listings_with_rates.csv`

- Fetches the weekly series live from FRED and averages it to monthly (`year_month`).
- Builds a `year_month` key from **`CloseDate`** for Sold and **`ListingContractDate`** for Listings.
- Left-merges so no MLS rows are lost, **asserts the row count is unchanged**, and checks for null `rate_30yr_fixed` values, listing any unmatched months if there are some.

### Weeks 4 to 5: Data cleaning and preparation (`04_clean.py`)

**Input:** `sold_with_rates.csv`, `listings_with_rates.csv`
**Output:** `sold_clean.csv`, `listings_clean.csv`, `sold_flagged.csv`, `listings_flagged.csv`, `*_geo_quality_summary.csv`

Every step logs rows before and after and the reason:

| Step | Action | Decision |
|---|---|---|
| Redundant columns | Drop duplicate `Name.1` columns from the extraction script and non-core columns over 90% null | Same rule as the EDA |
| Data types | Dates to datetime (unparseable values counted), numerics coerced, `PostalCode` kept as 5-character text | Zip codes are labels, not numbers |
| Duplicates | Drop exact duplicate rows, then repeated `ListingKey`s, keeping the latest record | One record per property |
| Missing values | Drop rows missing required fields (Sold: `ClosePrice`, `CloseDate`; Listings: `ListPrice`, `ListingContractDate`). Other gaps stay as NaN | No imputation, so averages aren't distorted by made-up values |
| Invalid numerics | Flag `ClosePrice ≤ 0`, `LivingArea ≤ 0`, `DaysOnMarket < 0`, negative beds or baths, then remove them from the clean file | Impossible values |
| Date consistency | `listing_after_close_flag`, `purchase_after_close_flag`, `negative_timeline_flag` | Flagged, not removed |
| Geography | `missing_coords_flag`, `zero_coords_flag`, `positive_longitude_flag`, `out_of_state_flag` (outside a rough California bounding box), rolled into `invalid_coords_flag` | Flagged, not removed |

### Week 6: Feature engineering and market metrics (`06_features.py`)

**Input:** `sold_clean.csv`
**Output:** `sold_features.csv`, `segment_property_type.csv`, `segment_county.csv`, `segment_county_mls_area.csv`, `segment_list_office.csv`, `segment_buyer_office.csv`

| Metric | Formula |
|---|---|
| `price_ratio` | `ClosePrice / ListPrice` |
| `close_to_original_list_ratio` | `ClosePrice / OriginalListPrice` |
| `price_per_sqft` | `ClosePrice / LivingArea` |
| `DaysOnMarket` | raw field |
| `Year`, `Month`, `YrMo` | from `CloseDate` |
| `listing_to_contract_days` | `PurchaseContractDate − ListingContractDate` |
| `contract_to_close_days` | `CloseDate − PurchaseContractDate` |
| `school_district` (optional) | point-in-polygon join on `Latitude` and `Longitude` |

Key decisions:
- **Two different ratios.** The handbook gives `ClosePrice / OriginalListPrice` for both "Price Ratio" and "Close to Original List Ratio". Two identical columns add nothing, so `price_ratio` uses the final `ListPrice` (sale vs. last asking price) and `close_to_original_list_ratio` uses `OriginalListPrice` (captures every price cut).
- **Safe division.** Ratios are blank where the denominator is missing or ≤ 0.
- **Negative durations are blanked.** They come from the date errors flagged in Weeks 4 to 5 and would pull averages down.
- **School districts are optional.** The step runs only if a `.geojson` or `.shp` file is in `data/raw/school_districts/` and GeoPandas is installed. Otherwise it is skipped with a message. **`[PLACEHOLDER: say whether the school district join was run, and the match rate]`**

Segment summaries (sales, total volume, median price, median $/sqft, median DOM, average ratios, median timelines) are produced by property type and subtype, county, county plus MLS area, listing office and buyer office.

### Week 7: Outlier detection and data quality (`07_outliers.py`)

**Input:** `sold_features.csv`
**Output:** `sold_outliers_flagged.csv`, `sold_analysis_filtered.csv`, `outlier_bounds.csv`, `outlier_comparison.csv`, `outlier_report.txt`

Uses the handbook's tiered approach:

1. **Business rules:** impossible values were already removed in Weeks 4 to 5.
2. **IQR flags:** values outside `[Q1 − 1.5×IQR, Q3 + 1.5×IQR]` are flagged on the required fields `ClosePrice`, `LivingArea` and `DaysOnMarket`, plus `price_per_sqft` and `close_to_original_list_ratio`.
3. **Percentile cross-check:** each field's 1st and 99th percentiles are printed next to its IQR bounds.

`any_outlier_flag` is True when a row is an outlier on any of the **three required fields**. The filtered dataset drops those rows. The two extra fields are flagged only, so they can serve as optional Tableau filters. Nothing is deleted, and the full flagged file keeps every row. The script writes a before/after comparison of size, medians and means, and the flag rate by county, since statewide bounds flag more sales in expensive counties.

### Weeks 8 to 10: Tableau prep and dashboards (`08_tableau_prep.py`)

**Input:** `sold_outliers_flagged.csv`, `listings_clean.csv`
**Output (`data/tableau/`):**

| File | Purpose |
|---|---|
| `tableau_sold.csv` | One row per closed sale, only the columns the dashboards use, with `any_outlier_flag` and `price_error_flag` |
| `tableau_listings.csv` | One row per new listing, keyed by `ListingContractDate` month |
| `tableau_market_activity.csv` | Sales and new listings stacked (`activity_type` = "Closed Sale" / "New Listing") so one chart shares one set of filters |
| `check_monthly_market.csv` | Expected monthly values for market_analysis |
| `check_top100_agents.csv`, `check_top100_offices.csv` | Expected top 100 by volume and by units |
| `check_zip_summary.csv` | Expected median price and homes sold per zip |
| `check_price_errors.csv` | Sales flagged as likely price typos, for review |
| `tableau_prep_report.txt` | Date coverage, row counts and the rules below |

Key decisions:
- **Outlier rule per workbook.** `market_analysis.twbx` filters `any_outlier_flag = False`, because medians and averages should describe the typical home. `competitive_analysis.twbx` keeps every sale, because volume and units are real business for the agent or office, and dropping a $6M sale would understate luxury brokerages.
- **Price error rule.** A sale gets `price_error_flag = True` when `ClosePrice` is under half or over double `ListPrice`, or over $100M. These are excluded from the competitive workbook. This was added after the first Top 100 agents chart was led by single sales of $820M to $970M, which were mistyped prices.
- **Ratio rule.** `close_to_original_list_ratio` values outside 0.5 to 2.0 come from near-zero original list prices (e.g. $1 typed into the MLS). They are left out of the average ratio only. The sale still counts for price, DOM and volume.
- **Check tables.** Each check file holds what the matching Tableau view should show with no filters applied, so each dashboard was verified against Python.
- **Date coverage check.** Lists any month missing from Sold or Listings, and warns when the latest month looks incomplete (under 80% of the previous month's sales).

---

## How to run

### Requirements

- Python 3.9 or later
- `pandas`, `numpy`, `matplotlib`
- `geopandas` (optional, only for the Week 6 school district join)
- Tableau Desktop Public Edition (free) for the workbooks
- Internet access for the FRED download in `03_mortgage_rates.py`

```bash
python -m pip install pandas numpy matplotlib
python -m pip install geopandas   # optional
```

### Steps

1. Put the monthly `CRMLSSoldYYYYMM.csv` and `CRMLSListingYYYYMM.csv` files in `data/raw/`.
2. (Optional) Put the California school district boundary file in `data/raw/school_districts/`.
3. From the project root, run the scripts in order:

```bash
cd IDX-Exchange-Data-Analyst
python scripts/01_combine.py
python scripts/02_eda.py
python scripts/03_mortgage_rates.py
python scripts/04_clean.py
python scripts/06_features.py
python scripts/07_outliers.py
python scripts/08_tableau_prep.py
```

4. Open the workbooks in `tableau/` and refresh each data source (**Data → [source] → Refresh**) so they read the new CSVs.

**Notes**
- Run from the project root, not from inside `scripts/`. Every path is relative to the root, so running from `scripts/` fails with a file-not-found error.
- The window ends at the last completed month **on the day you run it**, so a re-run next month adds a month.
- If Tableau doesn't show a new column after a refresh, quit Tableau and reopen it to clear its cached copy of the CSV, or use **Edit Connection** to pick the file again.
- Each script's docstring has a results block to paste the printed counts into after the final run.

---

## Outputs and dashboards

Both workbooks use the cleaned, Residential-only data from January 2024 to the latest month.

### `market_analysis.twbx` (outliers filtered out)

All filterable by city, county, zip code and `PropertySubType`:

| Dashboard | Measure |
|---|---|
| Monthly Median Close Price | Median `ClosePrice` by `YrMo` |
| Average Days on Market | Mean `DaysOnMarket` by month |
| Close-to-Original-List Ratio | Mean `close_to_original_list_ratio` (0.5 to 2.0 only) by month |
| New Listings | Count of listings by `ListingContractDate` month |
| Closed Sales | Count of sales by `CloseDate` month |
| Own design: Listings vs. Sales | New listings and closed sales as two lines from `tableau_market_activity.csv`. When listings run well above sales, inventory is building |

### `competitive_analysis.twbx` (all sales except price errors)

| Dashboard | Filters |
|---|---|
| Top 100 Listing Agents (volume and units) | Price error excluded |
| Top 100 Listing Offices (volume and units) | City, county, zip, `PropertySubType` |
| Zip Code Heat Map: Median Close Price | Month, city, county, zip, `PropertySubType` |
| Zip Code Heat Map: Homes Sold | Month, city, county, zip, `PropertySubType` |
| Own design: Volume vs. Luxury Agents | Scatter of top 100 agents: number of sales vs. average close price. Far right = high-volume agents; high up = luxury specialists |

Build notes: the Price Error and geography filters are set as **context filters** so the Top 100 re-ranks inside the selection and always shows 100 rows. The heat maps use stepped colors with the scale capped (for example at $2.5M for median price) so differences between ordinary zips show.

---

## Data quality findings

Problems caught by the pipeline and the dashboards, and how each was handled:

| Finding | How it was found | Handling |
|---|---|---|
| Mistyped close prices (single sales of $820M to $970M) | Topped the first Top 100 agents chart | `price_error_flag` in `08_tableau_prep.py`; excluded from competitive views |
| Near-zero original list prices, giving ratios up to ~800× | Spikes on the close-to-original-list ratio chart | Ratios outside 0.5 to 2.0 left out of the average |
| A low monthly count (about 1,700 new listings in January 2026) | The New Listings chart | Likely an incomplete monthly source file. **`[PLACEHOLDER: confirm against the 01_combine.py row counts and say whether it was re-pulled]`** |
| Out-of-state and mistyped zip codes | Marks outside California on the zip heat maps | Excluded on the maps; coordinates flagged by `out_of_state_flag` |
| One brokerage under several spellings (capitalization, "Inc" vs. ", Inc.", short names) | Top 100 Listing Offices | Totals are split across rows. Noted as a limitation; can be merged with Tableau groups |
| Dates out of order and negative timelines | `04_clean.py` date flags | Flagged; negative durations blanked in Week 6 |
| Statewide IQR bounds flag more sales in expensive counties | `07_outliers.py` flag rate by county | Documented; market workbook uses the filter, competitive does not |
| Duplicate columns from the extraction script (`Name.1`) | `04_clean.py` | Dropped |

---

## Key results

Values below come from the script output and Tableau screenshots shared during the project. **Exact** values were printed by a script or shown in a Tableau tooltip or status bar. **Approx.** values were read off a chart and should be replaced with the exact number from the check tables in `data/tableau/` before this is final. Items still marked `[PLACEHOLDER]` were never shared, so they need to come from your own run output.

### Data volume (Week 1 and cleaning)

| Metric | Value | Source |
|---|---|---|
| Months covered | Sold: 2024-01 to 2026-03 (27 months). Listings: 2024-01 to 2026-04 (28 months) | Tableau month counts |
| Listings rows before Residential filter | 860,898 | `01_combine.py` (exact) |
| Listings rows after Residential filter | 547,162 (63.6% kept) | `01_combine.py` (exact) |
| Other listing types removed | ResidentialLease 178,740 · Land 56,281 · ResidentialIncome 31,878 · ManufacturedInPark 24,650 · CommercialSale 11,682 · CommercialLease 7,758 · BusinessOpportunity 2,747 | `01_combine.py` (exact) |
| Sold rows after Residential filter | 397,473 | `01_combine.py` (exact) |
| Sold rows before Residential filter, and Residential share | **`[PLACEHOLDER]`** | `01_combine.py` Sold section |
| Listings rows in Tableau (after cleaning, 2024-01 to 2026-04) | 546,636 (536 fewer than the combined file, removed during cleaning in `04_clean.py`) | Tableau status bar (exact) |
| Sold rows after cleaning | **`[PLACEHOLDER]`** | `04_clean.py` |
| Sales flagged as IQR outliers | **`[PLACEHOLDER]`** (%) | `07_outliers.py` |
| Sales flagged as price errors | **`[PLACEHOLDER]`** | `08_tableau_prep.py` |

### Market trends, statewide (Tableau, January 2024 to March 2026)

| Metric | Value | Source |
|---|---|---|
| Median close price | Rose from about **$750K** (January 2024) to a peak of about **$860K** (spring 2024), then held between about $780K and $850K, ending near **$815K** in March 2026. The average of the 27 monthly medians is about **$820K** | Approx., median close price chart before the outlier filter |
| Close-to-original-list ratio | About **101%** at the spring 2024 peak, mostly **97% to 99%** since. Average across the 27 months is about **98.8%** | Approx., ratio chart (0.5 to 2.0 filter) |
| Closed sales per month | From **10,063** (January 2026, the low) to about **18,400** (May 2024, the high). Typically 13,000 to 16,000 | Tooltip (exact low), chart (approx. high) |
| New listings per month | About **10,500 to 26,700**, peaking in spring (about 26,700 in May 2025). February 2024 was 17,476. January 2026 shows only about **1,700**, which points to an incomplete source file | Tooltip (exact Feb 2024), chart (approx.) |
| Median days on market | **`[PLACEHOLDER]`** | `02_eda.py` Q3 |
| Share sold above / at / below list | **`[PLACEHOLDER]`** | `02_eda.py` Q4 |

### Example county view: San Francisco

| Metric | Value | Source |
|---|---|---|
| Median close price | About **$975K to $1.37M** per month, with a peak near $1.37M in February 2024 and a low near $975K in January 2025 | Approx., filtered dashboard |
| Average days on market | About **21 to 78 days** per month (the chart axis was formatted as a percentage at the time, so 2,100% = 21 days) | Approx., chart |

### Competitive landscape

| Metric | Value | Source |
|---|---|---|
| Largest listing office | About **$50.7 billion** in sales volume across **27,779** sales | Tableau Top 100 offices |
| Data issue | Several brokerages appear under more than one spelling, so their true totals are split across rows | Tableau Top 100 offices |

### What the results show

- **Prices are flat to slightly up.** The statewide median rose about 9% from January 2024 to March 2026 (about $750K to $815K), but almost all of that came in the first five months of 2024.
- **The market cooled after spring 2024.** Homes went from selling slightly above their original list price to about 1 to 3% below it.
- **Activity is seasonal.** Closed sales and new listings peak in spring and early summer and dip each winter. January 2026 closed sales (10,063) were close to January 2025.
- **Listings outnumber sales.** New listings ran well above closed sales in most months, which suggests inventory building up.
- **High-priced coastal zip codes and high-volume Southern California zip codes** stand out on the heat maps.

---

## Tools used

| Category | Tools |
|---|---|
| Language | Python |
| Data processing | pandas, NumPy |
| Visualization (EDA) | Matplotlib |
| Geospatial (optional) | GeoPandas |
| Dashboards | Tableau Desktop Public Edition, Tableau Public |
| Data sources | CRMLS via CoreLogic Trestle API, FRED (St. Louis Fed), data.ca.gov |
| Data transfer | FileZilla (FTP) |
| Editor | VS Code, Jupyter Notebooks |

---

## Next steps

**Weeks 11 to 12 (remaining deliverables)**
- [ ] Finish and save both workbooks as `.twbx` and publish them to Tableau Public (after supervisor sign-off).
- [ ] Write the **1-page Market Intelligence Report** for one county, city or zip: market overview, pricing trends, market activity, competitive landscape, and 3 to 5 data-driven takeaways.
- [ ] Prepare the **5-minute presentation** walking through the dashboards and findings.

**Improvements worth considering**
- Standardize office and agent names (case, punctuation, "Inc") before ranking, so each brokerage has one total.
- Compute IQR bounds per county instead of statewide, so expensive areas aren't over-filtered.
- Add the mortgage rate to a dashboard (e.g. rate vs. median price or closed sales) to use the Week 2 to 3 enrichment.
- Re-pull any month the coverage check marks as incomplete, and re-run from `01_combine.py`.
- Add a single `run_all.py` and a `requirements.txt`.

---

## Data confidentiality

The MLS data and the intern handbook are confidential to the IDX Exchange program. This repository should hold code and documentation only:
- Do not commit anything in `data/`, the raw CSVs, or FTP or API credentials.
- Keep agent names, office names and individual addresses out of public material unless your supervisor approves.

---

*IDX Exchange Data Analyst Internship · `William Zhang` · `Sep 2026 - Dec 2026`*
