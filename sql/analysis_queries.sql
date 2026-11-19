-- SQLite-compatible analysis queries. Run after: python scripts/load_to_sqlite.py
-- Achievement basis = TERTIARY (retail sell-out) units.

-- 1. Monthly tertiary units and value by category (seasonality view)
SELECT substr(s.order_date, 1, 7) AS year_month,
       p.category,
       SUM(s.units)          AS units,
       ROUND(SUM(s.net_value_inr)) AS net_value_inr
FROM fact_sales s
JOIN dim_product p ON p.product_code = s.product_code
WHERE s.channel_level = 'Tertiary'
GROUP BY year_month, p.category
ORDER BY year_month, p.category;

-- 2. Target vs achievement by month / region / category
WITH actual AS (
    SELECT substr(s.order_date, 1, 7) AS month, s.region, p.category, SUM(s.units) AS actual_units
    FROM fact_sales s
    JOIN dim_product p ON p.product_code = s.product_code
    WHERE s.channel_level = 'Tertiary'
    GROUP BY month, s.region, p.category
)
SELECT t.month, t.region, t.category, t.target_units,
       COALESCE(a.actual_units, 0) AS actual_units,
       ROUND(100.0 * COALESCE(a.actual_units, 0) / t.target_units, 1) AS achievement_pct
FROM fact_targets t
LEFT JOIN actual a ON a.month = t.month AND a.region = t.region AND a.category = t.category
ORDER BY t.month, t.region, t.category;

-- 3. Primary -> Secondary -> Tertiary movement by region (channel pipeline), 2025
SELECT region,
       SUM(CASE WHEN channel_level = 'Primary'   THEN units END) AS primary_units,
       SUM(CASE WHEN channel_level = 'Secondary' THEN units END) AS secondary_units,
       SUM(CASE WHEN channel_level = 'Tertiary'  THEN units END) AS tertiary_units
FROM fact_sales
WHERE order_date >= '2025-01-01'
GROUP BY region
ORDER BY region;

-- 4. Year-over-year growth by category (window function)
WITH yearly AS (
    SELECT p.category, CAST(substr(s.order_date, 1, 4) AS INT) AS yr, SUM(s.units) AS units
    FROM fact_sales s JOIN dim_product p ON p.product_code = s.product_code
    WHERE s.channel_level = 'Tertiary'
    GROUP BY p.category, yr
)
SELECT category, yr, units,
       ROUND(100.0 * (units - LAG(units) OVER (PARTITION BY category ORDER BY yr))
             / LAG(units) OVER (PARTITION BY category ORDER BY yr), 1) AS yoy_growth_pct
FROM yearly
ORDER BY category, yr;

-- 4b. Peak-season (Mar-Jun) share of annual units, by category and year
SELECT p.category, substr(s.order_date, 1, 4) AS yr,
       ROUND(100.0 * SUM(CASE WHEN CAST(substr(s.order_date, 6, 2) AS INT) BETWEEN 3 AND 6 THEN s.units END)
             / SUM(s.units), 1) AS peak_season_share_pct
FROM fact_sales s JOIN dim_product p ON p.product_code = s.product_code
WHERE s.channel_level = 'Tertiary'
GROUP BY p.category, yr
ORDER BY p.category, yr;

-- 5. Top 10 dealers by tertiary value, 2025, with rank within region
SELECT * FROM (
    SELECT d.region, d.state, s.dealer_id,
           ROUND(SUM(s.net_value_inr)) AS net_value_inr,
           RANK() OVER (PARTITION BY d.region ORDER BY SUM(s.net_value_inr) DESC) AS rank_in_region
    FROM fact_sales s JOIN dim_dealer d ON d.dealer_id = s.dealer_id
    WHERE s.channel_level = 'Tertiary' AND s.order_date >= '2025-01-01'
    GROUP BY d.region, d.state, s.dealer_id
) WHERE rank_in_region <= 3
ORDER BY region, rank_in_region;

-- 6. Latest-month stock cover (months of cover = stock / average monthly tertiary sales)
WITH avg_sales AS (
    SELECT s.region, p.category, SUM(s.units) * 1.0 / COUNT(DISTINCT substr(s.order_date, 1, 7)) AS avg_monthly_units
    FROM fact_sales s JOIN dim_product p ON p.product_code = s.product_code
    WHERE s.channel_level = 'Tertiary'
    GROUP BY s.region, p.category
), latest AS (
    SELECT i.region, p.category, SUM(i.stock_units) AS stock_units
    FROM fact_inventory i JOIN dim_product p ON p.product_code = i.product_code
    WHERE i.snapshot_date = (SELECT MAX(snapshot_date) FROM fact_inventory)
    GROUP BY i.region, p.category
)
SELECT l.region, l.category, l.stock_units, ROUND(a.avg_monthly_units, 1) AS avg_monthly_units,
       ROUND(l.stock_units / a.avg_monthly_units, 2) AS months_of_cover
FROM latest l JOIN avg_sales a ON a.region = l.region AND a.category = l.category
ORDER BY months_of_cover DESC;

-- 7. Service performance by region and category
SELECT region, category,
       COUNT(*) AS tickets,
       SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) AS open_tickets,
       ROUND(AVG(resolution_days), 2) AS avg_resolution_days
FROM fact_service
GROUP BY region, category
ORDER BY avg_resolution_days DESC;
