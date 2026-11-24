'''Read-only queries for the dashboard pages. Most read the small mart_* tables built by src/marts.py.'''
import streamlit as st
from .data import connect
from .query import query_dataframe

SQL = {
 'kpis': '''
    SELECT (SELECT COUNT(*) FROM basket_sizes) AS orders,
           (SELECT COUNT(*) FROM mart_customer) AS customers,
           (SELECT SUM(items) FROM mart_department) AS items,
           (SELECT COUNT(*) FROM mart_product) AS products,
           (SELECT ROUND(SUM(items*reorder_pct)/SUM(items),1) FROM mart_department) AS reorder_pct,
           (SELECT ROUND(AVG(basket_size)::numeric,1) FROM basket_sizes) AS avg_basket''',
 'departments': 'SELECT * FROM mart_department ORDER BY items DESC',
 'aisles': 'SELECT * FROM mart_aisle ORDER BY items DESC',
 'top_products': '''
    SELECT product_name, aisle, department, items, customers, reorder_pct, first_in_cart
    FROM mart_product WHERE (%(dept)s = 'All' OR department = %(dept)s)
    ORDER BY items DESC LIMIT %(n)s''',
 'loyal_products': '''
    SELECT product_name, aisle, department, items, reorder_pct
    FROM mart_product WHERE items >= %(min_items)s AND (%(dept)s = 'All' OR department = %(dept)s)
    ORDER BY reorder_pct DESC, items DESC LIMIT %(n)s''',
 'first_in_cart': '''
    SELECT product_name, department, first_in_cart, items,
      ROUND(100.0*first_in_cart/items,1) AS first_pct
    FROM mart_product WHERE items >= 500 ORDER BY first_in_cart DESC LIMIT %(n)s''',
 'hour_day': 'SELECT order_dow, order_hour_of_day, orders, items, avg_basket FROM mart_hour_day',
 'basket_size': 'SELECT basket_size, orders FROM mart_basket_size ORDER BY basket_size',
 'days_between': 'SELECT days, orders FROM mart_days_between ORDER BY days',
 'organic': '''
    SELECT CASE WHEN is_organic THEN 'Organic' ELSE 'Conventional' END AS type,
      COUNT(*) AS products, SUM(items) AS items, ROUND(SUM(items*reorder_pct)/SUM(items),2) AS reorder_pct
    FROM mart_product GROUP BY 1''',
 'organic_by_dept': '''
    SELECT department, ROUND(100.0*SUM(CASE WHEN is_organic THEN items END)/SUM(items),1) AS organic_share
    FROM mart_product GROUP BY department HAVING SUM(items) > 10000 ORDER BY organic_share DESC''',
 'pairs': '''
    SELECT product_a, product_b, co_orders, pct_of_a_orders, lift FROM mart_pairs
    WHERE co_orders >= %(min_co)s ORDER BY {order} DESC LIMIT %(n)s''',
 'customer_segments': '''
    SELECT CASE WHEN orders = 1 THEN '1 order' WHEN orders <= 3 THEN '2 to 3 orders'
      WHEN orders <= 6 THEN '4 to 6 orders' WHEN orders <= 10 THEN '7 to 10 orders' ELSE '11+ orders' END AS segment,
      MIN(orders) AS sort_key, COUNT(*) AS customers, SUM(items) AS items,
      ROUND(AVG(avg_basket),1) AS avg_basket, ROUND(AVG(reorder_pct),1) AS reorder_pct
    FROM mart_customer GROUP BY 1 ORDER BY sort_key''',
 'customers': 'SELECT orders, avg_basket, avg_days_between, reorder_pct FROM mart_customer',
 'order_sequence': 'SELECT * FROM mart_order_sequence ORDER BY order_number',
 'cart_position': 'SELECT * FROM mart_cart_position ORDER BY cart_position',
 'product_curve': 'SELECT items FROM mart_product ORDER BY items DESC',
 'dept_time': '''
    SELECT order_dow, order_hour_of_day, SUM(items) AS items, ROUND(100.0*SUM(reorders)/SUM(items),2) AS reorder_pct
    FROM mart_department_time WHERE (%(dept)s = 'All' OR department = %(dept)s)
    GROUP BY order_dow, order_hour_of_day''',
 'products_in_aisle': '''
    SELECT product_name, aisle, items, customers, reorder_pct, avg_cart_position
    FROM mart_product WHERE department = %(dept)s AND (%(aisle)s = 'All' AISLE_FILTER)
      AND product_name ILIKE %(search)s
    ORDER BY items DESC LIMIT 200''',
 'product_search': '''
    SELECT product_id, product_name, department, items FROM mart_product
    WHERE product_name ILIKE %(search)s ORDER BY items DESC LIMIT 25''',
 'product_hours': '''
    SELECT order_hour_of_day, COUNT(*) AS items FROM order_items WHERE product_id = %(pid)s GROUP BY 1 ORDER BY 1''',
 'product_days': '''
    SELECT order_dow, COUNT(*) AS items FROM order_items WHERE product_id = %(pid)s GROUP BY 1 ORDER BY 1''',
 'bought_with': '''
    WITH baskets AS (SELECT order_id FROM order_items WHERE product_id = %(pid)s),
    together AS (
      SELECT i.product_id, COUNT(*) AS together FROM order_items i JOIN baskets USING (order_id)
      WHERE i.product_id <> %(pid)s GROUP BY i.product_id)
    SELECT p.product_name, p.department, t.together,
      ROUND(100.0 * t.together / (SELECT COUNT(*) FROM baskets), 1) AS pct_of_baskets,
      ROUND(t.together::numeric * (SELECT COUNT(*) FROM basket_sizes) / ((SELECT COUNT(*) FROM baskets) * p.items), 2) AS lift
    FROM together t JOIN mart_product p USING (product_id)
    WHERE t.together >= 20 ORDER BY t.together DESC LIMIT 12''',
 'dept_pairs': 'SELECT dept_a, dept_b, together, lift FROM mart_department_pairs',
}
SQL['products_in_aisle'] =SQL['products_in_aisle'].replace('AISLE_FILTER', 'OR aisle = %(aisle)s')

DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']


@st.cache_data(show_spinner='Crunching the numbers…')
def run(name, **params):
    sql = SQL[name]
    if name == 'pairs': sql = sql.format(order='lift' if params.pop('by_lift', True) else 'co_orders')
    with connect(read_only=True) as conn:
        return query_dataframe(conn, sql, params)


@st.cache_data(show_spinner=False)
def raw(sql, params=()):
    with connect(read_only=True) as conn:
        return query_dataframe(conn, sql, params)


def hour_label(h):
    h = int(h)
    return f'{12 if h % 12 == 0 else h % 12} {"am" if h < 12 else "pm"}'
