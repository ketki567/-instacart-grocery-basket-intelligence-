'# PostgreSQL ingestion, reporting views, and integrity checks.'
import os
from pathlib import Path
import psycopg
from psycopg.rows import tuple_row

NAMES = ['orders','order_products__prior','order_products__train','products','aisles','departments']
SCHEMA = {
 'orders': 'order_id INTEGER PRIMARY KEY, user_id INTEGER, eval_set TEXT, order_number INTEGER, order_dow INTEGER, order_hour_of_day INTEGER, days_since_prior_order DOUBLE PRECISION',
 'order_products__prior': 'order_id INTEGER, product_id INTEGER, add_to_cart_order INTEGER, reordered INTEGER',
 'order_products__train': 'order_id INTEGER, product_id INTEGER, add_to_cart_order INTEGER, reordered INTEGER',
 'products': 'product_id INTEGER PRIMARY KEY, product_name TEXT, aisle_id INTEGER, department_id INTEGER',
 'aisles': 'aisle_id INTEGER PRIMARY KEY, aisle TEXT',
 'departments': 'department_id INTEGER PRIMARY KEY, department TEXT',
}

def load_env(path=Path(__file__).resolve().parent.parent/'.env'):
    '# Load KEY=VALUE pairs from the local .env file without overriding variables already set.'
    if not path.exists(): return
    for line in path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if line and not line.startswith('#') and '=' in line:
            key,value=line.split('=',1)
            os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))

load_env()

def connect(read_only=False):
    '# Use INSTA_DATABASE_URL or PostgreSQL env defaults.'
    url=os.getenv('INSTA_DATABASE_URL')
    conn=psycopg.connect(url,connect_timeout=5) if url else psycopg.connect(connect_timeout=5,dbname=os.getenv('PGDATABASE','instacart_bi'),host=os.getenv('PGHOST','localhost'),port=os.getenv('PGPORT','5432'),user=os.getenv('PGUSER','postgres'),password=os.getenv('PGPASSWORD',''))
    # JIT compilation adds seconds to every aggregate on this workload; extra work_mem keeps sorts in memory.
    conn.execute('SET jit = off');conn.execute("SET work_mem = '128MB'")
    if read_only:
        conn.execute('SET default_transaction_read_only = on')
    return conn

def build(data_dir='data'):
    directory=Path(data_dir)
    missing=[n+'.csv' for n in NAMES if not (directory/(n+'.csv')).exists()]
    if missing: raise FileNotFoundError('Download the Instacart CSV files first. Missing: '+', '.join(missing))
    with connect() as conn:
        with conn.cursor() as cur:
            for name in NAMES:
                cur.execute(f'DROP TABLE IF EXISTS "{name}" CASCADE')
                cur.execute(f'CREATE TABLE "{name}" ({SCHEMA[name]})')
                with (directory/(name+'.csv')).open('rb') as source:
                    with cur.copy(f'COPY "{name}" FROM STDIN WITH (FORMAT CSV, HEADER TRUE)') as copy:
                        while chunk:=source.read(1024*1024): copy.write(chunk)
                print(f'Imported {name}',flush=True)
            cur.execute('CREATE INDEX idx_prior_order ON order_products__prior(order_id)')
            cur.execute('CREATE INDEX idx_train_order ON order_products__train(order_id)')
            cur.execute('CREATE INDEX idx_prior_product ON order_products__prior(product_id)')
            cur.execute('CREATE INDEX idx_train_product ON order_products__train(product_id)')
            cur.execute('CREATE INDEX idx_orders_user ON orders(user_id)')
            # Materialized as a real table so dashboard queries don't re-join millions of rows each time.
            for rel in ('basket_sizes','order_items'):
                cur.execute("SELECT relkind FROM pg_class WHERE relname=%s AND relnamespace='public'::regnamespace",(rel,))
                kind=cur.fetchone()
                if kind: cur.execute(f'DROP {"VIEW" if kind[0]=="v" else "TABLE"} {rel} CASCADE')
            cur.execute('''CREATE TABLE order_items AS
                SELECT p.order_id,p.product_id,p.add_to_cart_order,p.reordered,o.user_id,
                o.order_dow,o.order_hour_of_day,o.days_since_prior_order,o.order_number,
                pr.product_name,pr.aisle_id,pr.department_id,a.aisle,d.department
                FROM (SELECT * FROM order_products__prior UNION ALL SELECT * FROM order_products__train) p
                JOIN orders o ON p.order_id=o.order_id
                JOIN products pr ON p.product_id=pr.product_id
                JOIN aisles a ON a.aisle_id=pr.aisle_id
                JOIN departments d ON d.department_id=pr.department_id
                ORDER BY p.order_id, p.add_to_cart_order''')
            for col in ('order_id','user_id','product_id','department','aisle'):
                cur.execute(f'CREATE INDEX idx_items_{col} ON order_items({col})')
            cur.execute('''CREATE TABLE basket_sizes AS
                SELECT order_id,MIN(user_id) AS user_id,COUNT(*) AS basket_size,
                ROUND(100*AVG(reordered),2) AS reorder_pct,
                MIN(order_dow) AS order_dow, MIN(order_hour_of_day) AS order_hour_of_day,
                MIN(order_number) AS order_number, MIN(days_since_prior_order) AS days_since_prior_order
                FROM order_items GROUP BY order_id''')
            cur.execute('CREATE INDEX idx_baskets_user ON basket_sizes(user_id)')
            for table in ('orders','order_products__prior','order_products__train','order_items','basket_sizes'):
                cur.execute(f'ANALYZE {table}')
            print('Built order_items and basket_sizes tables',flush=True)
            from .marts import build_marts
            build_marts(cur)
            from .ml import build_ml
            build_ml(cur, conn)
        results=check(conn)
        if any(results.values()): raise ValueError('Data quality checks failed: '+str(results))
    return 'PostgreSQL database instacart_bi'

def check(conn):
    checks={
      'duplicate order IDs':'SELECT count(*)-count(DISTINCT order_id) FROM orders',
      'duplicate product IDs':'SELECT count(*)-count(DISTINCT product_id) FROM products',
      'missing item-order references':'''SELECT count(*) FROM (SELECT order_id FROM order_products__prior UNION ALL SELECT order_id FROM order_products__train) x LEFT JOIN orders o USING(order_id) WHERE o.order_id IS NULL''',
      'missing product references':'''SELECT count(*) FROM (SELECT product_id FROM order_products__prior UNION ALL SELECT product_id FROM order_products__train) x LEFT JOIN products p USING(product_id) WHERE p.product_id IS NULL''',
      'invalid reorder flags':'SELECT count(*) FROM order_items WHERE reordered NOT IN (0,1) OR reordered IS NULL'}
    with conn.cursor() as cur:
        result={}
        for key,sql in checks.items():
            cur.execute(sql);result[key]=int(cur.fetchone()[0])
    return result
