"""Load the cleaned CSVs into a SQLite database (data/sales.db) for SQL analysis."""
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "sales.db"
TABLES = ["fact_sales", "fact_targets", "fact_inventory", "fact_service", "dim_product", "dim_dealer", "dim_date"]

def main():
    if DB.exists():
        DB.unlink()
    with sqlite3.connect(DB) as con:
        for t in TABLES:
            pd.read_csv(ROOT / "data" / "clean" / f"{t}.csv").to_sql(t, con, index=False)
        con.executescript("""
            CREATE INDEX idx_sales_date ON fact_sales(order_date);
            CREATE INDEX idx_sales_region ON fact_sales(region);
            CREATE INDEX idx_sales_product ON fact_sales(product_code);
        """)
    print("Loaded", len(TABLES), "tables into", DB)

if __name__ == "__main__":
    main()
