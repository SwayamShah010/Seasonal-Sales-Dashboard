"""Clean and validate the raw sales/targets/inventory/service data with pandas.

Outputs analysis-ready tables to data/clean/ plus a data quality log that
records every fix applied (row counts), so the cleaning is auditable.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean"
VALID_REGIONS = {"north": "North", "south": "South", "east": "East", "west": "West"}
MAX_UNITS_PER_ROW = 200  # a single dealer-product-month row above this is treated as a data-entry outlier
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"]


def standardise_region(s: pd.Series) -> pd.Series:
    """'NORTH ', ' north', 'North Zone' -> 'North'. Unknown values become NaN."""
    key = (s.astype(str).str.strip().str.lower()
             .str.replace(" zone", "", regex=False).str.strip())
    return key.map(VALID_REGIONS)


def parse_mixed_dates(s: pd.Series) -> pd.Series:
    """Parse a column holding several date formats, trying each explicit format."""
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        todo = out.isna()
        out.loc[todo] = pd.to_datetime(s[todo], format=fmt, errors="coerce")
    return out


def clean_sales(raw: pd.DataFrame, products: pd.DataFrame):
    log = []
    df = raw.copy()
    log.append(("rows_in", len(df)))

    n = len(df); df = df.drop_duplicates()
    log.append(("exact_duplicate_rows_removed", n - len(df)))

    df["order_date"] = parse_mixed_dates(df["order_date"])
    n = len(df); df = df.dropna(subset=["order_date"])
    log.append(("unparseable_dates_removed", n - len(df)))

    before = df["region"].copy()
    df["region"] = standardise_region(df["region"])
    log.append(("region_labels_standardised", int((before != df["region"]).sum())))
    n = len(df); df = df.dropna(subset=["region"])
    log.append(("unknown_region_removed", n - len(df)))

    n = len(df); df = df.dropna(subset=["units"])
    log.append(("missing_units_removed", n - len(df)))
    n = len(df); df = df[df["units"] > 0]
    log.append(("zero_or_negative_units_removed", n - len(df)))
    n = len(df); df = df[df["units"] <= MAX_UNITS_PER_ROW]
    log.append(("outlier_units_removed", n - len(df)))

    # impute missing net value = units x MRP x median realisation of that product
    df = df.merge(products[["product_code", "mrp"]], on="product_code", how="left")
    ratio = (df["net_value_inr"] / (df["units"] * df["mrp"]))
    med = ratio.groupby(df["product_code"]).transform("median")
    miss = df["net_value_inr"].isna()
    df.loc[miss, "net_value_inr"] = (df["units"] * df["mrp"] * med)[miss].round(2)
    df["value_imputed"] = miss
    log.append(("missing_net_value_imputed", int(miss.sum())))

    df["units"] = df["units"].astype(int)
    df = df.drop(columns="mrp").sort_values("order_date").reset_index(drop=True)
    log.append(("rows_out", len(df)))
    return df, pd.DataFrame(log, columns=["check", "count"])


def build_dim_date(start, end) -> pd.DataFrame:
    d = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    d["year"], d["month_num"] = d["date"].dt.year, d["date"].dt.month
    d["month_name"], d["year_month"] = d["date"].dt.strftime("%b"), d["date"].dt.strftime("%Y-%m")
    d["quarter"] = "Q" + d["date"].dt.quarter.astype(str)
    d["week_of_year"] = d["date"].dt.isocalendar().week.astype(int)
    # Indian cooling season Mar-Jun, treated as the 'peak season' for ACs/coolers
    d["season"] = np.where(d["month_num"].isin([3, 4, 5, 6]), "Peak (Mar-Jun)", "Off-Peak")
    return d


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    products = pd.read_csv(RAW / "products.csv")
    sales, log = clean_sales(pd.read_csv(RAW / "sales_raw.csv"), products)

    targets = pd.read_csv(RAW / "targets.csv")
    inventory = pd.read_csv(RAW / "inventory.csv", parse_dates=["snapshot_date"])
    service = pd.read_csv(RAW / "service_tickets.csv", parse_dates=["ticket_date"])
    inventory["region"] = standardise_region(inventory["region"])
    service["region"] = standardise_region(service["region"])

    sales.to_csv(CLEAN / "fact_sales.csv", index=False)
    targets.to_csv(CLEAN / "fact_targets.csv", index=False)
    inventory.to_csv(CLEAN / "fact_inventory.csv", index=False)
    service.to_csv(CLEAN / "fact_service.csv", index=False)
    products.to_csv(CLEAN / "dim_product.csv", index=False)
    sales[["dealer_id", "region", "state"]].drop_duplicates().sort_values("dealer_id") \
        .to_csv(CLEAN / "dim_dealer.csv", index=False)
    build_dim_date(sales["order_date"].min().replace(day=1), "2025-12-31").to_csv(CLEAN / "dim_date.csv", index=False)
    log.to_csv(CLEAN / "data_quality_log.csv", index=False)
    print(log.to_string(index=False))


if __name__ == "__main__":
    main()
