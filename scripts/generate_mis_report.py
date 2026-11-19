"""Automated monthly MIS report: builds a formatted Excel workbook from the cleaned data.

Replaces a manual monthly Excel reporting routine. Sheets:
  Summary, Region x Category, Target vs Achievement, Seasonality, Inventory Cover, Service.
Run:  python scripts/generate_mis_report.py [YYYY-MM]   (defaults to the latest month)
"""
import sys
from pathlib import Path
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
CLEAN, OUT = ROOT / "data" / "clean", ROOT / "reports"
HDR_FILL = PatternFill("solid", start_color="1F3864")
HDR_FONT = Font(name="Arial", bold=True, color="FFFFFF")
BODY = Font(name="Arial", size=10)


def load():
    s = pd.read_csv(CLEAN / "fact_sales.csv", parse_dates=["order_date"])
    p = pd.read_csv(CLEAN / "dim_product.csv")
    s = s.merge(p[["product_code", "category"]], on="product_code")
    s["year_month"] = s["order_date"].dt.strftime("%Y-%m")
    return (s, pd.read_csv(CLEAN / "fact_targets.csv"), pd.read_csv(CLEAN / "fact_inventory.csv", parse_dates=["snapshot_date"]),
            pd.read_csv(CLEAN / "fact_service.csv", parse_dates=["ticket_date"]), p)


def style_sheet(ws, df, pct_cols=(), money_cols=()):
    for c, name in enumerate(df.columns, 1):
        cell = ws.cell(row=1, column=c)
        cell.fill, cell.font, cell.alignment = HDR_FILL, HDR_FONT, Alignment(horizontal="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = max(14, len(str(name)) + 4)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = BODY
            h = ws.cell(row=1, column=cell.column).value
            if h in pct_cols:
                cell.number_format = "0.0%"
            elif h in money_cols:
                cell.number_format = "#,##0"
            elif isinstance(cell.value, float):
                cell.number_format = "#,##0.0"
    ws.freeze_panes = "A2"


def main(month=None):
    s, tg, inv, sv, prod = load()
    month = month or s["year_month"].max()
    ter = s[s.channel_level == "Tertiary"]  # retail (tertiary) sell-out is the achievement basis

    cur = ter[ter.year_month == month]
    prev_m = (pd.Period(month) - 12).strftime("%Y-%m")
    ly = ter[ter.year_month == prev_m]
    t_cur = tg[tg.month == month]
    ach_units, tgt_units = int(cur.units.sum()), int(t_cur.target_units.sum())

    summary = pd.DataFrame({
        "KPI": ["Month", "Tertiary units (achievement)", "Target units", "Achievement %", "Tertiary value (INR)",
                "Same month last year (units)", "YoY growth %", "Primary units", "Secondary units",
                "Service tickets raised", "Avg resolution days (closed)", "Open ticket %"],
        "Value": [month, ach_units, tgt_units, ach_units / tgt_units if tgt_units else None, round(cur.net_value_inr.sum()),
                  int(ly.units.sum()), (ach_units / ly.units.sum() - 1) if ly.units.sum() else None,
                  int(s[(s.year_month == month) & (s.channel_level == "Primary")].units.sum()),
                  int(s[(s.year_month == month) & (s.channel_level == "Secondary")].units.sum()),
                  int((sv.ticket_date.dt.strftime("%Y-%m") == month).sum()),
                  round(sv[(sv.ticket_date.dt.strftime("%Y-%m") == month) & (sv.status == "Closed")].resolution_days.mean(), 1),
                  (sv[sv.ticket_date.dt.strftime("%Y-%m") == month].status == "Open").mean()],
    })

    pivot = cur.pivot_table(index="region", columns="category", values="units", aggfunc="sum", fill_value=0)
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.reset_index()

    act = cur.groupby(["region", "category"], as_index=False)["units"].sum().rename(columns={"units": "actual_units"})
    tva = t_cur.merge(act, on=["region", "category"], how="left").fillna({"actual_units": 0})
    tva["achievement_%"] = tva["actual_units"] / tva["target_units"]
    tva["gap_units"] = tva["actual_units"] - tva["target_units"]
    tva["status"] = pd.cut(tva["achievement_%"], [-1, 0.9, 1.0, 99], right=False, labels=["Behind (<90%)", "Slightly behind", "On/above target"])
    tva = tva[["region", "category", "target_units", "actual_units", "achievement_%", "gap_units", "status"]]
    tva["status"] = tva["status"].astype(str)

    seas = ter.pivot_table(index="year_month", columns="category", values="units", aggfunc="sum", fill_value=0).reset_index()

    last_snap = inv.snapshot_date.max()
    stock = inv[inv.snapshot_date == last_snap].merge(prod[["product_code", "category"]], on="product_code")
    avg_sales = (ter.groupby(["region", "category"]).units.sum() / ter.year_month.nunique()).rename("avg_monthly_units")
    cover = stock.groupby(["region", "category"], as_index=False).stock_units.sum().merge(avg_sales.reset_index(), on=["region", "category"])
    cover["months_of_cover"] = cover["stock_units"] / cover["avg_monthly_units"]
    cover["flag"] = pd.cut(cover["months_of_cover"], [-1, 0.5, 4.0, 999], right=False, labels=["Stock-out risk", "Healthy", "Overstock"]).astype(str)

    svc = sv.assign(year_month=sv.ticket_date.dt.strftime("%Y-%m"))
    svc_tbl = svc[svc.year_month == month].groupby(["region", "category"]).agg(
        tickets=("status", "size"), open_tickets=("status", lambda x: (x == "Open").sum()),
        avg_resolution_days=("resolution_days", "mean")).reset_index().round(1)

    OUT.mkdir(exist_ok=True)
    path = OUT / f"MIS_Report_{month}.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df, pct, money in [("Summary", summary, (), ()), ("Region x Category", pivot, (), ()),
                                     ("Target vs Achievement", tva, ("achievement_%",), ()),
                                     ("Seasonality", seas, (), ()), ("Inventory Cover", cover, (), ()),
                                     ("Service", svc_tbl, (), ())]:
            df.to_excel(xw, sheet_name=name, index=False)
            style_sheet(xw.sheets[name], df, pct, money)
        ws = xw.sheets["Summary"]
        ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 34, 18
        for r in (5, 8, 13):  # Achievement %, YoY %, Open ticket %
            ws.cell(row=r, column=2).number_format = "0.0%"
        for r in (3, 4, 6, 7, 9, 10, 11):
            ws.cell(row=r, column=2).number_format = "#,##0"
        ws.cell(row=14, column=1, value="Source: synthetic demo data. Achievement measured on tertiary (retail) units.").font = Font(name="Arial", italic=True, size=9)
    print(f"Report written: {path}")
    return path


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
