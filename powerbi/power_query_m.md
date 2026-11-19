# Power Query (M) scripts

> Tested logic mirrors `scripts/clean_data.py`. Paste into Home > Transform data > New Source > Blank Query > Advanced Editor.
> **Test in Power BI Desktop** and adjust column names if your CSV headers differ.

## 0. Parameter
Create a Text parameter named `DataPath` = the full path to the `data` folder, e.g. `C:\projects\seasonal-sales-dashboard\data`.

## 1. Clean sales directly from the raw CSV (Power Query version of the pandas cleaning)
```m
let
    Source   = Csv.Document(File.Contents(DataPath & "\raw\sales_raw.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    // 1) remove exact duplicate rows
    Dedupe   = Table.Distinct(Promoted),
    // 2) standardise region: trim, lower-case, strip " zone", then proper-case
    Region   = Table.TransformColumns(Dedupe, {{"region", each Text.Proper(Text.Trim(Text.Replace(Text.Lower(Text.Trim(_)), " zone", ""))), type text}}),
    // 3) parse the mixed date formats (try yyyy-MM-dd, then dd/MM/yyyy, then dd-MMM-yyyy)
    Dates    = Table.AddColumn(Region, "order_date_clean", each
                   try Date.FromText([order_date], [Format="yyyy-MM-dd", Culture="en-GB"])
                   otherwise try Date.FromText([order_date], [Format="dd/MM/yyyy", Culture="en-GB"])
                   otherwise try Date.FromText([order_date], [Format="dd-MMM-yyyy", Culture="en-GB"])
                   otherwise null, type date),
    DropDate = Table.RemoveColumns(Dates, {"order_date"}),
    Renamed  = Table.RenameColumns(DropDate, {{"order_date_clean", "order_date"}}),
    // 4) set types
    Typed    = Table.TransformColumnTypes(Renamed, {{"units", type number}, {"net_value_inr", type number}}, "en-US"),
    // 5) drop missing / non-positive / outlier units
    Valid    = Table.SelectRows(Typed, each [order_date] <> null and [units] <> null and [units] > 0 and [units] <= 200),
    Final    = Table.TransformColumnTypes(Valid, {{"units", Int64.Type}})
in
    Final
```
(Missing `net_value_inr` is imputed in the pandas pipeline; in Power Query it is left null. The pandas-cleaned `fact_sales.csv` is the recommended source for the report.)

## 2. Loading the already-cleaned tables (recommended)
Use this pattern for each of `fact_sales`, `fact_targets`, `fact_inventory`, `fact_service`, `dim_product`, `dim_dealer`, `dim_date`:
```m
let
    Source   = Csv.Document(File.Contents(DataPath & "\clean\fact_sales.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
                  {"order_date", type date}, {"region", type text}, {"state", type text}, {"dealer_id", type text},
                  {"product_code", type text}, {"channel_level", type text},
                  {"units", Int64.Type}, {"net_value_inr", type number}, {"value_imputed", type logical}}, "en-US")
in
    Typed
```

## 3. fact_targets: add a month-start date so it joins to dim_date
```m
let
    Source   = Csv.Document(File.Contents(DataPath & "\clean\fact_targets.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed    = Table.TransformColumnTypes(Promoted, {{"month", type text}, {"region", type text}, {"category", type text}, {"target_units", Int64.Type}}, "en-US"),
    AddDate  = Table.AddColumn(Typed, "month_start", each Date.FromText([month] & "-01", [Format="yyyy-MM-dd"]), type date)
in
    AddDate
```

## 4. fact_inventory / fact_service type steps
```m
// fact_inventory
Table.TransformColumnTypes(Promoted, {{"snapshot_date", type date}, {"region", type text}, {"product_code", type text}, {"stock_units", Int64.Type}}, "en-US")
// fact_service
Table.TransformColumnTypes(Promoted, {{"ticket_date", type date}, {"region", type text}, {"category", type text}, {"status", type text}, {"resolution_days", type number}}, "en-US")
// dim_date
Table.TransformColumnTypes(Promoted, {{"date", type date}, {"year", Int64.Type}, {"month_num", Int64.Type}, {"week_of_year", Int64.Type}}, "en-US")
```
