'''Precomputed summary tables ("marts") so dashboard pages read thousands of rows, not millions.

Run on its own after build.py with:  python -m src.marts  (or name specific marts to rebuild)
'''

STAGE_SORT = '''CASE WHEN order_number = 1 THEN 1 WHEN order_number <= 3 THEN 2 WHEN order_number <= 10 THEN 3
    WHEN order_number <= 20 THEN 4 WHEN order_number <= 50 THEN 5 ELSE 6 END'''
STAGE = '''CASE WHEN order_number = 1 THEN '1st order' WHEN order_number <= 3 THEN 'Orders 2 to 3'
    WHEN order_number <= 10 THEN 'Orders 4 to 10' WHEN order_number <= 20 THEN 'Orders 11 to 20'
    WHEN order_number <= 50 THEN 'Orders 21 to 50' ELSE 'Orders 51 to 100' END'''
PACE_SORT = '''CASE WHEN c.avg_days_between IS NULL THEN 5 WHEN c.avg_days_between <= 8 THEN 1
    WHEN c.avg_days_between <= 15 THEN 2 WHEN c.avg_days_between <= 25 THEN 3 ELSE 4 END'''
PACE = '''CASE WHEN c.avg_days_between IS NULL THEN 'Unknown pace' WHEN c.avg_days_between <= 8 THEN 'Weekly'
    WHEN c.avg_days_between <= 15 THEN 'Every 1 to 2 weeks' WHEN c.avg_days_between <= 25 THEN 'Every 2 to 4 weeks'
    ELSE 'Monthly or slower' END'''

MARTS = {
 'mart_department': '''
    SELECT department_id, department, COUNT(*) AS items, COUNT(DISTINCT order_id) AS orders,
      COUNT(DISTINCT user_id) AS customers, COUNT(DISTINCT product_id) AS products,
      ROUND(100*AVG(reordered),2) AS reorder_pct, ROUND(AVG(add_to_cart_order)::numeric,2) AS avg_cart_position
    FROM order_items GROUP BY department_id, department''',
 'mart_aisle': '''
    SELECT department, aisle_id, aisle, COUNT(*) AS items, COUNT(DISTINCT product_id) AS products,
      ROUND(100*AVG(reordered),2) AS reorder_pct
    FROM order_items GROUP BY department, aisle_id, aisle''',
 'mart_product': '''
    SELECT product_id, MIN(product_name) AS product_name, MIN(aisle) AS aisle, MIN(department) AS department,
      COUNT(*) AS items, COUNT(DISTINCT user_id) AS customers, ROUND(100*AVG(reordered),2) AS reorder_pct,
      ROUND(AVG(add_to_cart_order)::numeric,2) AS avg_cart_position,
      SUM(CASE WHEN add_to_cart_order=1 THEN 1 ELSE 0 END) AS first_in_cart,
      BOOL_OR(product_name ILIKE '%%organic%%') AS is_organic
    FROM order_items GROUP BY product_id''',
 'mart_department_time': '''
    SELECT department, order_dow, order_hour_of_day, COUNT(*) AS items, SUM(reordered) AS reorders
    FROM order_items GROUP BY department, order_dow, order_hour_of_day''',
 'mart_hour_day': '''
    SELECT order_dow, order_hour_of_day, COUNT(*) AS orders, SUM(basket_size) AS items,
      ROUND(AVG(basket_size)::numeric,2) AS avg_basket
    FROM basket_sizes GROUP BY order_dow, order_hour_of_day''',
 'mart_customer': '''
    SELECT user_id, COUNT(*) AS orders, SUM(basket_size) AS items, ROUND(AVG(basket_size)::numeric,2) AS avg_basket,
      ROUND(AVG(days_since_prior_order)::numeric,1) AS avg_days_between,
      ROUND(SUM(basket_size*reorder_pct)/NULLIF(SUM(basket_size),0),2) AS reorder_pct
    FROM basket_sizes GROUP BY user_id''',
 'mart_order_sequence': '''
    SELECT order_number, COUNT(*) AS orders, COUNT(DISTINCT user_id) AS customers,
      ROUND(AVG(basket_size)::numeric,2) AS avg_basket,
      ROUND(SUM(basket_size*reorder_pct)/NULLIF(SUM(basket_size),0),2) AS reorder_pct
    FROM basket_sizes WHERE order_number <= 100 GROUP BY order_number''',
 'mart_basket_size': '''
    SELECT basket_size, COUNT(*) AS orders FROM basket_sizes GROUP BY basket_size''',
 'mart_days_between': '''
    SELECT days_since_prior_order::int AS days, COUNT(*) AS orders
    FROM orders WHERE days_since_prior_order IS NOT NULL GROUP BY 1''',
 'mart_cart_position': '''
    SELECT add_to_cart_order AS cart_position, COUNT(*) AS items, ROUND(100*AVG(reordered),2) AS reorder_pct
    FROM order_items WHERE add_to_cart_order BETWEEN 1 AND 50 GROUP BY 1''',
 'mart_pairs': '''
    WITH popular AS (
      SELECT product_id, product_name, items FROM mart_product ORDER BY items DESC LIMIT 150),
    lines AS (
      SELECT i.order_id, i.product_id FROM order_items i JOIN popular p USING (product_id)),
    pairs AS (
      SELECT a.product_id AS a, b.product_id AS b, COUNT(*) AS together
      FROM lines a JOIN lines b ON a.order_id=b.order_id AND a.product_id<b.product_id
      GROUP BY 1,2 HAVING COUNT(*) >= 50),
    total AS (SELECT COUNT(*) AS n FROM basket_sizes)
    SELECT p.product_name AS product_a, q.product_name AS product_b, pairs.together AS co_orders,
      ROUND(100.0*pairs.together/p.items,2) AS pct_of_a_orders,
      ROUND(pairs.together::numeric*total.n/(p.items::numeric*q.items),2) AS lift
    FROM pairs JOIN popular p ON p.product_id=pairs.a JOIN popular q ON q.product_id=pairs.b CROSS JOIN total''',
 'mart_department_pairs': '''
    WITH od AS (SELECT DISTINCT order_id, department FROM order_items),
    single AS (SELECT department, COUNT(*) AS n FROM od GROUP BY department),
    total AS (SELECT COUNT(DISTINCT order_id) AS n FROM od),
    pairs AS (
      SELECT a.department AS dept_a, b.department AS dept_b, COUNT(*) AS together
      FROM od a JOIN od b ON a.order_id=b.order_id AND a.department<b.department GROUP BY 1,2)
    SELECT pairs.dept_a, pairs.dept_b, pairs.together,
      ROUND(pairs.together::numeric*total.n/(sa.n::numeric*sb.n),3) AS lift
    FROM pairs JOIN single sa ON sa.department=pairs.dept_a JOIN single sb ON sb.department=pairs.dept_b CROSS JOIN total''',
 # Cohorts. order_number is the order's true position in the customer's lifetime and days_since_prior_order is the
 # real gap to the previous order, even when that order is not in this sample, so both support cohort comparisons.
 'mart_lifecycle': f'''
    SELECT {STAGE_SORT} AS stage_sort, {STAGE} AS stage, COUNT(*) AS orders, ROUND(AVG(basket_size)::numeric,2) AS avg_basket,
      ROUND(SUM(basket_size*reorder_pct)/SUM(basket_size),2) AS reorder_pct,
      ROUND(AVG(days_since_prior_order)::numeric,2) AS avg_days_between
    FROM basket_sizes GROUP BY 1,2''',
 'mart_lifecycle_department': f'''
    SELECT {STAGE_SORT} AS stage_sort, {STAGE} AS stage, department, COUNT(*) AS items, ROUND(100*AVG(reordered),2) AS reorder_pct
    FROM order_items GROUP BY 1,2,3''',
 'mart_lifecycle_organic': f'''
    SELECT {STAGE_SORT.replace('order_number','i.order_number')} AS stage_sort, {STAGE.replace('order_number','i.order_number')} AS stage,
      ROUND(100.0*AVG(CASE WHEN p.is_organic THEN 1 ELSE 0 END),2) AS organic_share
    FROM order_items i JOIN mart_product p USING (product_id) GROUP BY 1,2''',
 'mart_pace_cohorts': f'''
    SELECT {PACE_SORT} AS pace_sort, {PACE} AS pace, {STAGE_SORT.replace('order_number','b.order_number')} AS stage_sort,
      {STAGE.replace('order_number','b.order_number')} AS stage, COUNT(*) AS orders, COUNT(DISTINCT b.user_id) AS customers,
      ROUND(AVG(b.basket_size)::numeric,2) AS avg_basket,
      ROUND(SUM(b.basket_size*b.reorder_pct)/SUM(b.basket_size),2) AS reorder_pct
    FROM basket_sizes b JOIN mart_customer c USING (user_id) GROUP BY 1,2,3,4''',
 'mart_lifetime_reach': '''
    WITH deepest AS (SELECT user_id, MAX(order_number) AS deepest FROM orders GROUP BY user_id)
    SELECT n AS order_number, COUNT(*) FILTER (WHERE deepest >= n) AS customers,
      ROUND(100.0*COUNT(*) FILTER (WHERE deepest >= n)/COUNT(*),2) AS pct_of_customers
    FROM deepest CROSS JOIN generate_series(1,100) AS n GROUP BY n''',
}


def build_marts(cur, only=None):
    for name, sql in MARTS.items():
        if only and name not in only: continue
        cur.execute(f'DROP TABLE IF EXISTS {name}')
        cur.execute(f'CREATE TABLE {name} AS {sql}')
        cur.execute(f'ANALYZE {name}')
        print(f'Built {name}', flush=True)


if __name__ == '__main__':
    import sys
    from .data import connect
    with connect() as conn:
        with conn.cursor() as cur: build_marts(cur, only=sys.argv[1:] or None)
