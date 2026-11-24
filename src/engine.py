"""Business intelligence functions with explicit grains and limits."""
from .query import query_dataframe

def overview(conn):
    sql='''SELECT COUNT(DISTINCT order_id) orders,COUNT(DISTINCT user_id) customers,
        COUNT(*) items,ROUND(AVG(reordered)*100,2) reorder_rate_pct
        FROM order_items'''
    return query_dataframe(conn,sql)

def trend(conn,unit='hour',department='All'):
    field={'hour':'order_hour_of_day','day':'order_dow','order_sequence':'order_number'}[unit]
    wh='WHERE department = %s' if department!='All' else ''
    sql=f'''SELECT {field} AS period,COUNT(DISTINCT order_id) AS orders,
       COUNT(*) AS items, ROUND(100*AVG(reordered),2) AS reorder_pct FROM order_items
       {wh} GROUP BY {field} ORDER BY {field}'''
    return query_dataframe(conn,sql,(department,) if department!='All' else ())

def basket_segments(conn):
    return query_dataframe(conn,'''WITH b AS (
      SELECT user_id,order_id,COUNT(*) basket_size FROM order_items GROUP BY user_id,order_id
    ), u AS (SELECT user_id, COUNT(*) observed_orders, AVG(basket_size) avg_basket FROM b GROUP BY user_id)
    SELECT CASE WHEN observed_orders < 5 THEN '1–4' WHEN observed_orders < 11 THEN '5–10'
    WHEN observed_orders < 21 THEN '11–20' ELSE '21+' END segment,
    COUNT(*) customers, ROUND(AVG(avg_basket)::numeric,2) avg_basket
    FROM u GROUP BY 1 ORDER BY 1''')

def cohort(conn):
    # Order sequence is NOT calendar retention; count known observed baskets by sequence.
    return query_dataframe(conn,'''SELECT order_number, COUNT(DISTINCT user_id) observed_customers,
    COUNT(DISTINCT order_id) orders, ROUND(100*AVG(reordered),2) reorder_pct
    FROM order_items WHERE order_number <= 40 GROUP BY 1 ORDER BY 1''')

def comparison(conn,dimension='department',min_items=100,limit=30):
    allowed={'department':'department','aisle':'aisle','product':'product_name'}
    col=allowed[dimension]
    return query_dataframe(conn,f'''SELECT {col} AS segment,COUNT(*) item_purchases,
       COUNT(DISTINCT order_id) observed_orders,
       ROUND(AVG(reordered)*100,2) reorder_pct,
       ROUND(AVG(add_to_cart_order)::numeric,2) avg_cart_position
       FROM order_items GROUP BY {col} HAVING COUNT(*) >= %s
       ORDER BY item_purchases DESC LIMIT %s''',(min_items,limit))

def affinity(conn,min_orders=100,top_products=60,limit=25):
    # Prefilter before joining large item table, use supporting count and lift.
    return query_dataframe(conn,'''WITH popular AS (
      SELECT product_id,MIN(product_name) product_name,COUNT(DISTINCT order_id) n
      FROM order_items GROUP BY product_id ORDER BY n DESC LIMIT %s),
    pairs AS (SELECT a.product_id a,b.product_id b,COUNT(*) together
      FROM order_items a JOIN order_items b ON a.order_id=b.order_id AND a.product_id<b.product_id
      JOIN popular p ON p.product_id=a.product_id JOIN popular q ON q.product_id=b.product_id
      GROUP BY 1,2), total AS (SELECT COUNT(DISTINCT order_id) n FROM order_items)
    SELECT p.product_name product_a,q.product_name product_b,pairs.together co_orders,
    ROUND((pairs.together::numeric*total.n/NULLIF(p.n*q.n,0)),2) lift
    FROM pairs JOIN popular p ON p.product_id=pairs.a JOIN popular q ON q.product_id=pairs.b
    CROSS JOIN total WHERE pairs.together >= %s ORDER BY lift DESC,co_orders DESC LIMIT %s''',
    (top_products,min_orders,limit))

def quality(conn):
    from .data import check
    return check(conn)

def departments(conn):
    return [r[0] for r in query_dataframe(conn,'SELECT department FROM departments ORDER BY department').itertuples(index=False,name=None)]
