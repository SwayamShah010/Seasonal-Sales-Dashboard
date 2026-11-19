# Dashboard Build Guide (about 2 to 3 hours in Power BI Desktop)

The `.pbix` file is not included because Power BI Desktop is required to create it. Follow these steps, then save your file as `powerbi/Seasonal_Sales_Dashboard.pbix` and add screenshots to `docs/`.

## Step 1: Load data (about 15 min)
1. Get Data > Text/CSV. Load the 7 files in `data/clean/` (see `power_query_m.md`). Set `DataPath` as a parameter if you use the M scripts.
2. Add the `month_start` column to `fact_targets` (script 3 in `power_query_m.md`).
3. Confirm data types, then Close & Apply.

## Step 2: Model (about 15 min), star schema
Create calculated tables first (Modeling > New table):
```dax
DimRegion   = DISTINCT ( dim_dealer[region] )
DimCategory = DISTINCT ( dim_product[category] )
```
Then relationships (all many-to-one, single direction, dimension filters fact):

| From (many) | To (one) |
|---|---|
| fact_sales[order_date] | dim_date[date] |
| fact_sales[product_code] | dim_product[product_code] |
| fact_sales[dealer_id] | dim_dealer[dealer_id] |
| dim_dealer[region] | DimRegion[region] |
| dim_product[category] | DimCategory[category] |
| fact_targets[month_start] | dim_date[date] |
| fact_targets[region] | DimRegion[region] |
| fact_targets[category] | DimCategory[category] |
| fact_inventory[snapshot_date] | dim_date[date] |
| fact_inventory[region] | DimRegion[region] |
| fact_inventory[product_code] | dim_product[product_code] |
| fact_service[ticket_date] | dim_date[date] |
| fact_service[region] | DimRegion[region] |
| fact_service[category] | DimCategory[category] |

Mark `dim_date` as a date table (Table tools > Mark as date table > `date`). Use `DimRegion[region]` and `DimCategory[category]` in slicers and axes so every fact table is filtered together.
Tip: set `dim_date[month_name]` to sort by `month_num`.

## Step 3: Measures (about 15 min)
Create all measures in `DAX_measures.md`.

## Step 4: Pages (about 1.5 hrs)

**Page 1: Executive Overview**
- KPI cards: Tertiary Units, Tertiary Value (INR), Achievement %, YoY Growth %, Open Ticket %
- Line chart: Tertiary Units by `year_month`, legend = category
- Clustered bar: Achievement % by region
- Slicers: year, `DimRegion[region]`, `DimCategory[category]`

**Page 2: Seasonality and Demand**
- Line chart: Tertiary Units by `month_name` (sorted by `month_num`), legend = year
- Heatmap matrix: rows = category, columns = `month_name`, values = Seasonality Index (conditional-format background colour)
- Cards: Peak Season Share %, Rolling 3M Units
- Takeaway text box: write the 2-3 insights you see (see README for the ones in this dataset)

**Page 3: Target vs Achievement and Regions**
- Matrix: rows = region > category; values = Target Units, Tertiary Units, Achievement %, Gap to Target
- Conditional formatting on Achievement % (red < 90%, amber 90 to 100%, green >= 100%) or use Achievement Status as a rules-based font colour
- Bar chart: Gap to Target by region
- Optional: top/bottom 5 states by Achievement %

**Page 4: Channel, Inventory and Service**
- Clustered column: Primary vs Secondary vs Tertiary Units by region
- Table: region x category with Stock Units, Months of Cover, Stock Flag (conditional formatting)
- Bar/column: Tickets and Avg Resolution Days by category; card for Open Ticket %

## Step 5: Polish and export (about 30 min)
- Consistent theme and font; title and subtitle on every page; units and `INR` labels on axes
- Page navigation buttons (optional)
- Save as `.pbix`
- Export each page: File > Export > PDF, and take screenshots with Snipping Tool
- Save screenshots as `docs/01_overview.png`, `docs/02_seasonality.png`, `docs/03_target_vs_achievement.png`, `docs/04_channel_inventory_service.png`
- Replace the screenshot placeholders in the README
