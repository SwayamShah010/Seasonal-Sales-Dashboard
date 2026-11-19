import sys
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from clean_data import standardise_region, parse_mixed_dates, clean_sales  # noqa: E402

PRODUCTS = pd.DataFrame({"product_code": ["AC-S15"], "mrp": [42000]})
CLEAN = Path(__file__).resolve().parents[1] / "data" / "clean"


def test_region_variants_are_standardised():
    s = pd.Series(["North", " north", "NORTH ", "North Zone", "east ", "WEST", "Mars"])
    out = standardise_region(s).tolist()
    assert out[:6] == ["North", "North", "North", "North", "East", "West"]
    assert pd.isna(out[6])


def test_mixed_date_formats_parse_to_same_day():
    s = pd.Series(["2025-03-14", "14/03/2025", "14-Mar-2025", "not a date"])
    out = parse_mixed_dates(s)
    assert (out.iloc[:3] == pd.Timestamp("2025-03-14")).all()
    assert pd.isna(out.iloc[3])


def _raw(rows):
    return pd.DataFrame(rows, columns=["order_date", "region", "state", "dealer_id", "product_code",
                                       "channel_level", "units", "net_value_inr"])


def test_clean_sales_applies_all_rules_and_logs_them():
    good = ["2025-01-10", "North", "Delhi", "D001", "AC-S15", "Tertiary", 2.0, 70000.0]
    raw = _raw([
        good,
        good,                                                                        # exact duplicate
        ["10/01/2025", " north", "Delhi", "D001", "AC-S15", "Secondary", 3.0, 100000.0],  # dirty region + date
        ["2025-01-11", "North", "Delhi", "D001", "AC-S15", "Tertiary", None, 50000.0],    # missing units
        ["2025-01-12", "North", "Delhi", "D001", "AC-S15", "Tertiary", -2.0, 50000.0],    # negative
        ["2025-01-13", "North", "Delhi", "D001", "AC-S15", "Tertiary", 1500.0, 9e7],      # outlier
        ["2025-01-14", "North", "Delhi", "D001", "AC-S15", "Primary", 4.0, None],          # missing value
    ])
    df, log = clean_sales(raw, PRODUCTS)
    log = dict(zip(log["check"], log["count"]))
    assert log["exact_duplicate_rows_removed"] == 1
    assert log["missing_units_removed"] == 1
    assert log["zero_or_negative_units_removed"] == 1
    assert log["outlier_units_removed"] == 1
    assert log["missing_net_value_imputed"] == 1
    assert len(df) == 3
    assert set(df["region"]) == {"North"}
    assert df["net_value_inr"].notna().all()
    assert df["value_imputed"].sum() == 1


@pytest.mark.skipif(not (CLEAN / "fact_sales.csv").exists(), reason="run clean_data.py first")
def test_clean_output_integrity():
    s = pd.read_csv(CLEAN / "fact_sales.csv")
    assert not s.duplicated().any()
    assert (s["units"] > 0).all()
    assert s["net_value_inr"].notna().all()
    assert set(s["region"]) == {"North", "South", "East", "West"}
    assert set(s["channel_level"]) == {"Primary", "Secondary", "Tertiary"}
    products = pd.read_csv(CLEAN / "dim_product.csv")
    assert set(s["product_code"]) <= set(products["product_code"])  # referential integrity
