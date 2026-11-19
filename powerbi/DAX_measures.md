# DAX Measures

> Create a table called `_Measures` (Home > Enter Data, one blank column, then delete the column) and add the measures below to it.
> **Note:** these were written against the data model in `dashboard_build_guide.md`. Test each one in Power BI Desktop; column/table names must match your model.

## Volume and value
```dax
Units = SUM ( fact_sales[units] )

Tertiary Units =
CALCULATE ( [Units], fact_sales[channel_level] = "Tertiary" )

Secondary Units =
CALCULATE ( [Units], fact_sales[channel_level] = "Secondary" )

Primary Units =
CALCULATE ( [Units], fact_sales[channel_level] = "Primary" )

Tertiary Value (INR) =
CALCULATE ( SUM ( fact_sales[net_value_inr] ), fact_sales[channel_level] = "Tertiary" )

Avg Selling Price (INR) =
DIVIDE ( [Tertiary Value (INR)], [Tertiary Units] )
```

## Target vs achievement
```dax
Target Units = SUM ( fact_targets[target_units] )

Achievement % = DIVIDE ( [Tertiary Units], [Target Units] )

Gap to Target = [Tertiary Units] - [Target Units]

Achievement Status =
SWITCH (
    TRUE (),
    ISBLANK ( [Achievement %] ), BLANK (),
    [Achievement %] >= 1,   "On/above target",
    [Achievement %] >= 0.9, "Slightly behind",
    "Behind (<90%)"
)
```

## Time intelligence and seasonality
```dax
Tertiary Units LY =
CALCULATE ( [Tertiary Units], SAMEPERIODLASTYEAR ( dim_date[date] ) )

YoY Growth % =
DIVIDE ( [Tertiary Units] - [Tertiary Units LY], [Tertiary Units LY] )

Tertiary Units YTD =
TOTALYTD ( [Tertiary Units], dim_date[date] )

Rolling 3M Units =
CALCULATE (
    [Tertiary Units],
    DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -3, MONTH )
)

Peak Season Share % =
DIVIDE (
    CALCULATE ( [Tertiary Units], dim_date[season] = "Peak (Mar-Jun)" ),
    CALCULATE ( [Tertiary Units], ALL ( dim_date[season] ) )
)

Seasonality Index =
-- month's units vs. the average month (1.0 = average), within current filters on category/region
VAR MonthUnits = [Tertiary Units]
VAR AvgMonth =
    DIVIDE (
        CALCULATE ( [Tertiary Units], ALL ( dim_date[month_name], dim_date[month_num] ) ),
        12 * DISTINCTCOUNT ( dim_date[year] )
    )
RETURN DIVIDE ( MonthUnits, AvgMonth )
```

## Channel movement
```dax
Secondary to Tertiary Sell-Through % = DIVIDE ( [Tertiary Units], [Secondary Units] )

Primary to Secondary Conversion % = DIVIDE ( [Secondary Units], [Primary Units] )
```

## Inventory
```dax
Stock Units =
CALCULATE ( SUM ( fact_inventory[stock_units] ), LASTDATE ( fact_inventory[snapshot_date] ) )

Avg Monthly Units (All Time) =
CALCULATE (
    DIVIDE ( [Tertiary Units], DISTINCTCOUNT ( dim_date[year_month] ) ),
    ALL ( dim_date )
)

Months of Cover = DIVIDE ( [Stock Units], [Avg Monthly Units (All Time)] )

Stock Flag =
SWITCH (
    TRUE (),
    ISBLANK ( [Months of Cover] ), BLANK (),
    [Months of Cover] < 0.5, "Stock-out risk",
    [Months of Cover] > 4,   "Overstock",
    "Healthy"
)
```

## Service
```dax
Tickets = COUNTROWS ( fact_service )

Open Tickets = CALCULATE ( COUNTROWS ( fact_service ), fact_service[status] = "Open" )

Open Ticket % = DIVIDE ( [Open Tickets], [Tickets] )

Avg Resolution Days = AVERAGE ( fact_service[resolution_days] )
```
