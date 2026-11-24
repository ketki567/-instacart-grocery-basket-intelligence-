'''Advanced SQL Lab examples: window functions, percentiles, regression, CTEs and market-basket lift.'''
EXAMPLES = {
 'Basket growth order-to-order (LAG window)': '''-- How does basket size change versus the customer's previous order?
WITH seq AS (
  SELECT user_id, order_number, basket_size,
         LAG(basket_size) OVER (PARTITION BY user_id ORDER BY order_number) AS prev_basket
  FROM basket_sizes
)
SELECT order_number,
       ROUND(AVG(basket_size - prev_basket), 2) AS avg_change_vs_previous,
       COUNT(*) AS orders
FROM seq
WHERE prev_basket IS NOT NULL AND order_number <= 25
GROUP BY order_number
ORDER BY order_number''',
 'Top 3 products in every department (ROW_NUMBER)': '''-- Ranking inside groups with a window function
SELECT department, rank_in_department, product_name, items, reorder_pct
FROM (
  SELECT department, product_name, items, reorder_pct,
         ROW_NUMBER() OVER (PARTITION BY department ORDER BY items DESC) AS rank_in_department
  FROM mart_product
) ranked
WHERE rank_in_department <= 3
ORDER BY department, rank_in_department''',
 'Percentiles of days between orders (PERCENTILE_CONT)': '''-- Distribution summary by how big the basket is
SELECT CASE WHEN basket_size <= 5 THEN '1-5 items' WHEN basket_size <= 15 THEN '6-15 items' ELSE '16+ items' END AS basket_band,
       COUNT(*) AS orders,
       PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_since_prior_order) AS p25_days,
       PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_since_prior_order) AS median_days,
       PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_since_prior_order) AS p75_days
FROM basket_sizes
WHERE days_since_prior_order IS NOT NULL
GROUP BY 1
ORDER BY 1''',
 'Products whose loyalty grows fastest (REGR_SLOPE)': '''-- Slope of the reorder flag against order number: positive = customers get more loyal over time
SELECT product_name,
       COUNT(*) AS purchases,
       ROUND((100 * AVG(reordered))::numeric, 1) AS reorder_pct,
       ROUND((100 * REGR_SLOPE(reordered, order_number))::numeric, 3) AS reorder_pct_gain_per_order
FROM order_items
WHERE product_id IN (SELECT product_id FROM mart_product WHERE items >= 3000)
GROUP BY product_name
ORDER BY reorder_pct_gain_per_order DESC
LIMIT 15''',
 'Hourly share within each department (SUM OVER)': '''-- Percent of each department's items sold in each hour (window over the grouped result)
SELECT department, order_hour_of_day,
       ROUND(100.0 * SUM(items) / SUM(SUM(items)) OVER (PARTITION BY department), 2) AS pct_of_department
FROM mart_department_time
WHERE department IN ('alcohol', 'breakfast', 'snacks', 'babies')
GROUP BY department, order_hour_of_day
ORDER BY department, order_hour_of_day''',
 'Customer retention funnel (cumulative window)': '''-- Share of customers who reach at least N observed orders
WITH dist AS (SELECT orders, COUNT(*) AS customers FROM mart_customer GROUP BY orders)
SELECT orders AS at_least_n_orders,
       SUM(customers) OVER (ORDER BY orders DESC) AS customers,
       ROUND(100.0 * SUM(customers) OVER (ORDER BY orders DESC) / SUM(customers) OVER (), 1) AS pct_of_customers
FROM dist
WHERE orders <= 20
ORDER BY orders''',
 'Market basket for one product (CTE + lift)': '''-- What goes with Organic Avocado? Support, confidence and lift
WITH target AS (SELECT product_id FROM products WHERE product_name = 'Organic Avocado'),
baskets AS (SELECT order_id FROM order_items WHERE product_id = (SELECT product_id FROM target)),
n AS (SELECT (SELECT COUNT(*) FROM basket_sizes) AS all_orders, (SELECT COUNT(*) FROM baskets) AS target_orders)
SELECT p.product_name,
       COUNT(*) AS together,
       ROUND(100.0 * COUNT(*) / MAX(n.target_orders), 1) AS confidence_pct,
       ROUND(COUNT(*)::numeric * MAX(n.all_orders) / (MAX(n.target_orders) * MAX(p.items)), 2) AS lift
FROM order_items i
JOIN baskets USING (order_id)
JOIN mart_product p ON p.product_id = i.product_id
CROSS JOIN n
WHERE i.product_id <> (SELECT product_id FROM target)
GROUP BY p.product_name
HAVING COUNT(*) >= 100
ORDER BY lift DESC
LIMIT 15''',
 'First-order vs repeat basket mix by department': '''-- Do first orders look different from later ones?
SELECT department,
       ROUND(100.0 * SUM(CASE WHEN order_number = 1 THEN 1 ELSE 0 END) / SUM(SUM(CASE WHEN order_number = 1 THEN 1 ELSE 0 END)) OVER (), 2) AS pct_of_first_orders,
       ROUND(100.0 * SUM(CASE WHEN order_number > 1 THEN 1 ELSE 0 END) / SUM(SUM(CASE WHEN order_number > 1 THEN 1 ELSE 0 END)) OVER (), 2) AS pct_of_repeat_orders
FROM order_items
GROUP BY department
ORDER BY pct_of_first_orders DESC''',
}
