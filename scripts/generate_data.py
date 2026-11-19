"""Generate a SYNTHETIC consumer-durables dataset (ACs, coolers, appliances).

All data is artificially generated with a fixed random seed. It is NOT real
company data. It is deliberately messy (duplicates, inconsistent region names,
mixed date formats, missing values) so the cleaning pipeline has real work to do.
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

REGIONS = {
    "North": ["Delhi", "Punjab", "Uttar Pradesh", "Rajasthan"],
    "South": ["Karnataka", "Tamil Nadu", "Telangana", "Kerala"],
    "East": ["West Bengal", "Odisha", "Bihar", "Assam"],
    "West": ["Maharashtra", "Gujarat", "Madhya Pradesh", "Goa"],
}
REGION_W = {"North": 1.25, "South": 1.0, "East": 0.7, "West": 1.1}

PRODUCTS = pd.DataFrame([
    ("AC-S15", "1.5 Ton Split AC", "Split AC", 42000),
    ("AC-S10", "1.0 Ton Split AC", "Split AC", 34000),
    ("AC-W15", "1.5 Ton Window AC", "Window AC", 31000),
    ("CL-P50", "50L Personal Cooler", "Air Cooler", 9500),
    ("CL-D80", "80L Desert Cooler", "Air Cooler", 14500),
    ("RF-D25", "250L Double Door Fridge", "Refrigerator", 26000),
    ("WM-F70", "7kg Front Load Washer", "Washing Machine", 33000),
], columns=["product_code", "product_name", "category", "mrp"])

# monthly seasonality index per category (Jan..Dec)
SEASON = {
    "Split AC":        [0.35, 0.55, 1.3, 2.1, 2.4, 1.8, 0.8, 0.5, 0.45, 0.4, 0.35, 0.3],
    "Window AC":       [0.3, 0.5, 1.2, 2.0, 2.3, 1.7, 0.7, 0.45, 0.4, 0.35, 0.3, 0.25],
    "Air Cooler":      [0.25, 0.6, 1.6, 2.4, 2.2, 1.2, 0.5, 0.3, 0.3, 0.3, 0.25, 0.2],
    "Refrigerator":    [0.9, 0.95, 1.1, 1.2, 1.2, 1.0, 0.9, 0.9, 1.0, 1.2, 1.1, 0.9],
    "Washing Machine": [0.95, 0.9, 0.9, 0.95, 0.95, 1.0, 1.1, 1.1, 1.0, 1.15, 1.1, 1.0],
}
BASE_UNITS = {"Split AC": 22, "Window AC": 9, "Air Cooler": 26, "Refrigerator": 16, "Washing Machine": 12}
LEVELS = {"Primary": 1.6, "Secondary": 1.2, "Tertiary": 1.0}

months = pd.period_range("2024-01", "2025-12", freq="M")
rows = []
dealers = {}
c = 0
for region, states in REGIONS.items():
    for st in states:
        for _ in range(3):
            c += 1
            dealers[f"D{c:03d}"] = (region, st)

for m in months:
    growth = 1.0 + 0.08 * (m.year - 2024)
    for dealer_id, (region, state) in dealers.items():
        for _, p in PRODUCTS.iterrows():
            for level, lvl_mult in LEVELS.items():
                if RNG.random() < 0.35:
                    continue
                lam = (BASE_UNITS[p.category] * SEASON[p.category][m.month - 1]
                       * REGION_W[region] * lvl_mult * growth) / 6
                units = int(RNG.poisson(max(lam, 0.2)))
                if units == 0:
                    continue
                day = int(RNG.integers(1, 28))
                rows.append((pd.Timestamp(m.year, m.month, day), region, state, dealer_id,
                             p.product_code, level, units,
                             round(units * p.mrp * RNG.uniform(0.82, 0.95), 2)))

sales = pd.DataFrame(rows, columns=["order_date", "region", "state", "dealer_id",
                                    "product_code", "channel_level", "units", "net_value_inr"])

# ---------- targets / inventory / service built from the CLEAN truth ----------
tertiary = sales[sales.channel_level == "Tertiary"].merge(PRODUCTS[["product_code", "category"]], on="product_code")
tertiary["month"] = tertiary["order_date"].dt.to_period("M").astype(str)
act = tertiary.groupby(["month", "region", "category"], as_index=False)["units"].sum()
targets = act.assign(target_units=lambda d: (d["units"] * RNG.uniform(0.85, 1.15, len(d))).astype(int))
targets[["month", "region", "category", "target_units"]].to_csv(RAW / "targets.csv", index=False)

inv = []
for m in months:
    for region in REGIONS:
        for _, p in PRODUCTS.iterrows():
            base = BASE_UNITS[p.category] * REGION_W[region] * 9
            nxt = SEASON[p.category][m.month % 12]
            inv.append((str(m.end_time.date()), region, p.product_code, int(base * nxt * RNG.uniform(0.7, 1.4))))
pd.DataFrame(inv, columns=["snapshot_date", "region", "product_code", "stock_units"]).to_csv(RAW / "inventory.csv", index=False)

sv = []
for m in months:
    for region in REGIONS:
        for cat in SEASON:
            for _ in range(int(RNG.poisson(30 * SEASON[cat][m.month - 1] * REGION_W[region]))):
                day = int(RNG.integers(1, 28))
                closed = RNG.random() < 0.93
                sv.append((pd.Timestamp(m.year, m.month, day).strftime("%Y-%m-%d"), region, cat,
                           "Closed" if closed else "Open",
                           round(float(RNG.gamma(2.2, 1.1)) + 0.5, 1) if closed else np.nan))
pd.DataFrame(sv, columns=["ticket_date", "region", "category", "status", "resolution_days"]).to_csv(RAW / "service_tickets.csv", index=False)

PRODUCTS.to_csv(RAW / "products.csv", index=False)

# ---------- inject realistic mess into sales ----------
raw = sales.copy()
n = len(raw)
fmt = RNG.integers(0, 3, n)
raw["order_date"] = [d.strftime(["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"][k]) for d, k in zip(raw["order_date"], fmt)]
variants = {"North": ["north", "NORTH ", "North Zone", " North"], "South": ["south", "SOUTH", "South "],
            "East": ["east ", "EAST", "East Zone"], "West": ["west", "WEST ", " West"]}
raw["region"] = [str(RNG.choice(variants[r])) if RNG.random() < 0.12 else r for r in raw["region"]]
raw["units"] = raw["units"].astype(float)
raw.loc[RNG.choice(n, int(n * 0.012), replace=False), "units"] = np.nan
raw.loc[RNG.choice(n, int(n * 0.010), replace=False), "net_value_inr"] = np.nan
raw.loc[RNG.choice(n, 25, replace=False), "units"] = -RNG.integers(1, 5, 25)
raw.loc[RNG.choice(n, 15, replace=False), "units"] = RNG.integers(900, 2000, 15)
dups = raw.sample(int(n * 0.015), random_state=1)
raw = pd.concat([raw, dups], ignore_index=True).sample(frac=1, random_state=7).reset_index(drop=True)
raw.to_csv(RAW / "sales_raw.csv", index=False)
print("sales_raw rows:", len(raw))
