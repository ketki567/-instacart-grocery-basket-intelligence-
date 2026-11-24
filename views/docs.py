'''Documentation: project overview, datasets and dictionary, data model, metric definitions.'''
import pandas as pd
import streamlit as st
from src import ui
from src.analytics import raw, run
from src.marts import MARTS


DATASETS = {
    'orders': ('🧾', 'One row per order: who placed it, which of their orders it was, and when.', [
        ('order_id', 'integer', 'Unique order identifier (primary key).'),
        ('user_id', 'integer', 'Anonymized customer identifier.'),
        ('eval_set', 'text', 'Original Kaggle split. This sample has only history orders, set to “prior”.'),
        ('order_number', 'integer', 'Sequence of this order for the customer (1 = first order seen).'),
        ('order_dow', 'integer', 'Day of week, 0 to 6. The mapping to weekday names was not published.'),
        ('order_hour_of_day', 'integer', 'Hour the order was placed, 0 to 23.'),
        ('days_since_prior_order', 'decimal', 'Days since the previous order, capped at 30. Empty for a first order.')]),
    'order_products__prior': ('🛒', 'One row per product in an order. This is the core purchase fact table.', [
        ('order_id', 'integer', 'The order (links to orders).'),
        ('product_id', 'integer', 'The product (links to products).'),
        ('add_to_cart_order', 'integer', 'Position the product was added to the cart (1 = first).'),
        ('reordered', '0 / 1', '1 if this customer has bought this product before.')]),
    'order_products__train': ('🧪', 'Same layout as the prior table; held out orders in the original competition. Empty in this sample.', [
        ('order_id', 'integer', 'The order.'), ('product_id', 'integer', 'The product.'),
        ('add_to_cart_order', 'integer', 'Cart position.'), ('reordered', '0 / 1', 'Bought before by this customer.')]),
    'products': ('🏷️', 'Product catalog.', [
        ('product_id', 'integer', 'Unique product identifier.'), ('product_name', 'text', 'Product name (“Unknown” where missing).'),
        ('aisle_id', 'integer', 'Aisle the product sits in.'), ('department_id', 'integer', 'Department the product belongs to.')]),
    'aisles': ('🛤️', 'The 134 aisles.', [('aisle_id', 'integer', 'Unique aisle identifier.'), ('aisle', 'text', 'Aisle name.')]),
    'departments': ('🏬', 'The 21 departments.', [('department_id', 'integer', 'Unique department identifier.'), ('department', 'text', 'Department name.')]),
}

MODEL_DOT = '''digraph {
  graph [rankdir=LR, bgcolor="transparent", pad=0.3, nodesep=0.5, ranksep=0.9, fontname="Helvetica"];
  node [shape=plain, fontname="Helvetica", fontsize=11];
  edge [color="#8A978E", arrowhead=crow, arrowtail=none];
  orders [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="6" bgcolor="#FFFFFF" color="#0F9D58">
    <tr><td bgcolor="#0F9D58"><font color="white"><b>orders</b></font></td></tr>
    <tr><td align="left"><b>order_id</b> PK</td></tr><tr><td align="left">user_id</td></tr><tr><td align="left">order_number</td></tr>
    <tr><td align="left">order_dow · order_hour_of_day</td></tr><tr><td align="left">days_since_prior_order</td></tr></table>>];
  items [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="6" bgcolor="#FFFFFF" color="#FF7A1A">
    <tr><td bgcolor="#FF7A1A"><font color="white"><b>order_products__prior / __train</b></font></td></tr>
    <tr><td align="left">order_id FK</td></tr><tr><td align="left">product_id FK</td></tr>
    <tr><td align="left">add_to_cart_order</td></tr><tr><td align="left">reordered</td></tr></table>>];
  products [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="6" bgcolor="#FFFFFF" color="#4C6EF5">
    <tr><td bgcolor="#4C6EF5"><font color="white"><b>products</b></font></td></tr>
    <tr><td align="left"><b>product_id</b> PK</td></tr><tr><td align="left">product_name</td></tr>
    <tr><td align="left">aisle_id FK</td></tr><tr><td align="left">department_id FK</td></tr></table>>];
  aisles [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="6" bgcolor="#FFFFFF" color="#E5487F">
    <tr><td bgcolor="#E5487F"><font color="white"><b>aisles</b></font></td></tr><tr><td align="left"><b>aisle_id</b> PK</td></tr><tr><td align="left">aisle</td></tr></table>>];
  departments [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="6" bgcolor="#FFFFFF" color="#F2B705">
    <tr><td bgcolor="#F2B705"><font color="white"><b>departments</b></font></td></tr><tr><td align="left"><b>department_id</b> PK</td></tr><tr><td align="left">department</td></tr></table>>];
  orders -> items [label=" 1 : many", fontsize=10, fontcolor="#6C7B71"];
  products -> items [label=" 1 : many", fontsize=10, fontcolor="#6C7B71"];
  aisles -> products; departments -> products;
}'''

PIPELINE_DOT = '''digraph {
  graph [rankdir=TB, bgcolor="transparent", pad=0.3, nodesep=0.4, ranksep=0.6];
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=12, color="#E5EBE0", margin="0.25,0.15"];
  edge [color="#8A978E"];
  csv [label="6 CSV files\\n(raw downloads)", fillcolor="#EEF4EA"];
  clean [label="Clean & convert\\n(; → , · dedupe · fill names)", fillcolor="#FFF3E6"];
  pg [label="PostgreSQL raw tables\\n(COPY, indexes)", fillcolor="#E8EDFF"];
  model [label="Modeled tables\\norder_items · basket_sizes", fillcolor="#E8EDFF"];
  marts [label="12 summary tables\\n(built ahead of time)", fillcolor="#E3F6EA"];
  app [label="Web dashboard (Streamlit)\\n(cached, read only)", fillcolor="#FDE7EF"];
  ask [label="Ask the data\\n(allow listed, parameterized SQL)", fillcolor="#FDE7EF"];
  llm [label="Optional local LLM\\n(Ollama, explains results only)", fillcolor="#F3EEFB", style="rounded,filled,dashed"];
  csv -> clean -> pg -> model -> marts -> app; model -> ask -> llm;
}'''

METRICS = [
    ('Orders', 'Number of orders with at least one product line.', 'COUNT(*) FROM basket_sizes'),
    ('Shoppers', 'Distinct customers with at least one product line.', 'COUNT(DISTINCT user_id)'),
    ('Items bought', 'Product lines across all orders (a product once per order).', 'COUNT(*) FROM order_items'),
    ('Reorder rate', 'Share of product lines the customer had bought before. Not customer retention.', '100 × AVG(reordered)'),
    ('Basket size', 'Product lines in one order.', 'COUNT(*) GROUP BY order_id'),
    ('Avg cart position', 'Average position an item was added to the cart. Lower means added earlier.', 'AVG(add_to_cart_order)'),
    ('Days between orders', 'Gap since the customer’s previous order, capped at 30 by Instacart.', 'days_since_prior_order'),
    ('Lift', 'How much more often two products appear together than if they were independent.', 'P(A∩B) / (P(A)·P(B))'),
    ('First in cart', 'Times a product was the first item added.', 'SUM(add_to_cart_order = 1)'),
    ('Organic', 'Product name contains “organic”.', "product_name ILIKE '%organic%'"),
]

def _overview():
    k = run('kpis').iloc[0]
    st.markdown('#### 🎯 What this project is')
    st.markdown('A study of customer shopping behavior on real, anonymized grocery orders. It answers what people buy, '
                'when they shop, what they buy together and who keeps coming back.')
    st.markdown('Raw CSV files are cleaned, loaded into PostgreSQL, modeled into analysis ready tables, summarised for speed, '
                'and explored through an interactive web dashboard built with Streamlit, with plain English insights, technical deep dives and a '
                'safe way to ask questions.')
    st.markdown('#### 💼 Why it matters')
    st.markdown('The same questions drive merchandising, staffing, promotions and loyalty programs for any grocery or '
                'online retail business.')
    st.markdown('#### 📦 Where the data comes from')
    st.markdown('The public [Instacart Market Basket Analysis](https://www.kaggle.com/datasets/psparks/instacart-market-basket-analysis) '
                'dataset, released by Instacart for research. This project uses an anonymized sample of it. The data has no prices, '
                'revenue or calendar dates, so none are invented here.')
    c = st.columns(4)
    for col, (icon, label, value) in zip(c, [('🧾', 'Orders with items', f"{int(k['orders']):,}"), ('👥', 'Shoppers', f"{int(k['customers']):,}"),
                                             ('🛒', 'Purchase lines', f"{int(k['items']):,}"), ('🏷️', 'Products bought', f"{int(k['products']):,}")]):
        with col: ui.kpi(icon, label, value)
    st.markdown('#### 🛠️ Tech stack')
    ui.badges(['🐘 PostgreSQL', '🐍 Python', '🐼 pandas', '🤖 scikit learn', '📊 Plotly', '🎈 Streamlit', '🧪 pytest', '🦙 Ollama (optional)'])
    st.markdown('#### 🔄 How it was built')
    ui.pipeline(['📄 CSV files', '🧹 Clean', '🐘 PostgreSQL', '🧱 Model', '⚡ Summary tables', '🤖 Machine learning', '🌐 Web dashboard'])
    cols = st.columns(4)
    for col, (e, t, d) in zip(cols, [('🐘', 'PostgreSQL', 'COPY loading, indexes, modeled tables, 12 summary tables'),
                                      ('🐍', 'Python', 'pandas, NumPy, psycopg 3'),
                                      ('📊', 'Streamlit and Plotly', '7 pages and more than 40 interactive charts'),
                                      ('🛡️', 'Safe querying', 'A guarded question builder and a read only SQL Lab')]):
        with col: ui.card(e, t, d)
    st.markdown('#### 🧠 Skills demonstrated')
    st.markdown('''
- **Data engineering:** File cleaning, bulk loading, data modeling, indexing, summary tables and query tuning. Pages read small summary tables instead of millions of rows (see the live speed race in Deep dives).
- **SQL:** Joins, CTEs, window functions (LAG, ROW_NUMBER, running totals), percentiles, regression slopes, self joins for market basket lift and parameterized queries.
- **Analysis:** Lifecycle and pace cohorts, survival analysis of order gaps, Pareto and long tail, distributions and correlation, basket affinity.
- **Machine learning:** Customer segmentation with k means (silhouette based choice of k) and a gradient boosting reorder model, evaluated on unseen customers against simple baselines, with permutation importance and calibration.
- **Experimentation:** A/B test design with sample size and power for the recommendations.
- **Storytelling:** Every chart has a plain English takeaway and a recommendation. Technical pages show the method and SQL.
- **Responsible analytics:** Documented limitations, no invented revenue and no AI generated SQL.''')


def _datasets():
    st.markdown('The original dataset is the public **Instacart Market Basket Analysis** release '
                '([Kaggle](https://www.kaggle.com/datasets/psparks/instacart-market-basket-analysis)). '
                'This project uses a **sample** of it (about 14% of orders), cleaned as described under *Deep dives → Data quality*.')
    counts = raw('''SELECT relname AS table_name, n_live_tup AS rows FROM pg_stat_user_tables''').set_index('table_name')['rows']
    for name, (emoji, desc, cols) in DATASETS.items():
        with st.expander(f'{emoji} **{name}** · {int(counts.get(name, 0)):,} rows', expanded=name == 'orders'):
            st.markdown(desc)
            st.dataframe(pd.DataFrame(cols, columns=['Column', 'Type', 'Meaning']), hide_index=True, width='stretch')
            sample = raw(f'SELECT * FROM {name} LIMIT 8')
            st.markdown('**Sample rows**')
            st.dataframe(sample, hide_index=True, width='stretch')
            ui.download(sample, f'sample_{name}.csv', '⬇️ Download sample')
    st.markdown('#### 🧱 Tables built by this project')
    built = pd.DataFrame([('order_items', 'Every purchase line joined with order, product, aisle and department.'),
                          ('basket_sizes', 'One row per order: size, reorder share, timing.')] +
                         [(n, ' '.join(sql.split())[:110] + '…') for n, sql in MARTS.items()], columns=['Table', 'What it holds'])
    built['Rows'] = [int(counts.get(t, 0)) for t in built['Table']]
    st.dataframe(built, hide_index=True, width='stretch')


def _model():
    st.markdown('#### 🧩 Source data model')
    st.graphviz_chart(MODEL_DOT, width='stretch')
    st.markdown('#### 🔄 Pipeline')
    st.graphviz_chart(PIPELINE_DOT, width='stretch')


def _metrics():
    st.dataframe(pd.DataFrame(METRICS, columns=['Metric', 'Definition', 'Formula / SQL']), hide_index=True, width='stretch')
    st.info('Day names assume day 0 = Sunday. The dataset has no calendar dates, prices, revenue, locations or demographics.', icon='ℹ️')


def render():
    ui.page_header('📚', 'Documentation', 'Everything about the project: overview, data, data model and metrics.', ui.PALETTE[6])
    tabs = st.tabs(['🏁 Overview', '🗃️ Datasets', '🧩 Data model', '📐 Metrics'])
    for tab, fn in zip(tabs, [_overview, _datasets, _model, _metrics]):
        with tab: fn()
    ui.footer()
