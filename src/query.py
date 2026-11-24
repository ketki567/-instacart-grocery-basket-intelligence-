"""Governed analytical questions: parameterized SQL, not arbitrary text-to-SQL."""
from dataclasses import dataclass
import re

DIMENSIONS = {
    'department': ('department','department'),
    'aisle': ('aisle','aisle'),
    'product': ('product_name','product_name'),
    'hour': ('order_hour_of_day','hour'),
    'day': ('order_dow','day'),
    'order_number': ('order_number','order_number'),
}
MEASURES = {
    'items': ('COUNT(*)','Item purchases'),
    'orders': ('COUNT(DISTINCT order_id)','Distinct orders'),
    'customers': ('COUNT(DISTINCT user_id)','Distinct customers'),
    'reorder_rate': ('ROUND(100.0*AVG(reordered),2)','Item reorder rate (%)'),
    'avg_cart_position': ('ROUND(AVG(add_to_cart_order)::numeric,2)','Avg cart position'),
}
@dataclass
class Spec:
    dimension: str = 'department'
    measure: str = 'items'
    department: str = 'All'
    hour_start: int = 0
    hour_end: int = 23
    min_items: int = 100
    limit: int = 20
    descending: bool = True


def validate(spec):
    if spec.dimension not in DIMENSIONS or spec.measure not in MEASURES: raise ValueError('Unknown field')
    if not (0 <= spec.hour_start <= spec.hour_end <= 23):raise ValueError('Invalid hour range')
    if not (0 <= spec.min_items <= 1000000):raise ValueError('Invalid minimum count')
    if not (1 <= spec.limit <= 100):raise ValueError('Invalid row limit')
    return spec


def compile_query(spec):
    validate(spec)
    col,alias = DIMENSIONS[spec.dimension]
    expr,_ = MEASURES[spec.measure]
    clauses=['order_hour_of_day BETWEEN %s AND %s']
    params=[spec.hour_start,spec.hour_end]
    if spec.department != 'All':clauses.append('department = %s');params.append(spec.department)
    direction='DESC' if spec.descending else 'ASC'
    # dimension + measure selected from fixed allowlists. Values are bound parameters.
    if spec.measure in ('orders','customers'):
        # Two-step distinct count (group, then count groups) hashes instead of sorting 4.5M rows per group.
        key='order_id' if spec.measure=='orders' else 'user_id'
        sql=f'''SELECT {alias}, COUNT(*) AS metric, SUM(n) AS supporting_items FROM (
            SELECT {col} AS {alias}, {key}, COUNT(*) AS n FROM order_items WHERE {' AND '.join(clauses)}
            GROUP BY {col}, {key}) grouped
            GROUP BY {alias} HAVING SUM(n) >= %s
            ORDER BY metric {direction} NULLS LAST LIMIT %s'''
        return sql,tuple(params+[spec.min_items,spec.limit])
    sql=f'''SELECT {col} AS {alias}, {expr} AS metric, COUNT(*) AS supporting_items
        FROM order_items WHERE {' AND '.join(clauses)}
        GROUP BY {col} HAVING COUNT(*) >= %s
        ORDER BY metric {direction} NULLS LAST LIMIT %s'''
    return sql,tuple(params+[spec.min_items,spec.limit])

UNSUPPORTED=re.compile(r'\b(revenue|profit|margin|dollars|sales price|income|cost|delivery|shipping|month|year|churn|conversion rate|customer age|customer gender|location|city)\b',re.I)
def interpret_question(question):
    """Transparent no-model fallback; API users may edit specs in UI before executing."""
    if UNSUPPORTED.search(question): return None,'This dataset has no prices, revenue, delivery dates, calendar months or demographics.'
    q=question.lower()
    dim='department'
    for names,key in [(('aisle',),'aisle'),(('product','item','grocery'),'product'),(('hour','time of day','morning','evening','peak time'),'hour'),(('weekday','day of week','which day'),'day'),(('order number','purchase sequence'),'order_number')]:
        if any(x in q for x in names):dim=key;break
    measure='items'
    if 'reorder' in q or 'repeat' in q: measure='reorder_rate'
    elif 'customer' in q or 'user' in q:measure='customers'
    elif 'basket' in q or 'order count' in q or 'number of orders' in q:measure='orders'
    elif 'position' in q:measure='avg_cart_position'
    # "least / lowest / fewest …" flips the ranking to show the bottom of the list.
    descending=not re.search(r'\b(least|lowest|fewest|bottom|worst|minimum|smallest|rarely|unpopular|less)\b',q)
    return Spec(dimension=dim,measure=measure,descending=descending),None


def query_dataframe(conn,sql,params=()):
    import pandas as pd
    with conn.cursor() as cur:
        cur.execute(sql,params)
        df=pd.DataFrame(cur.fetchall(),columns=[c.name for c in cur.description])
    # PostgreSQL NUMERIC arrives as Decimal objects; convert so pandas/numpy math and charts work.
    from decimal import Decimal
    for col in df.columns:
        if df[col].dtype==object and df[col].map(lambda v:isinstance(v,Decimal)).any():
            df[col]=pd.to_numeric(df[col],errors='coerce').astype(float)
    return df
