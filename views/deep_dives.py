'''Technical deep dives: methods, statistics, data quality and database design, each with chart, finding, data and SQL.'''
import time
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src import ui
from src.analytics import run, raw, SQL, DAY_NAMES, hour_label
from src.data import connect
from src.marts import MARTS


def _head(emoji, title, question):
    st.markdown(f'### {emoji} {title}')
    st.markdown(f'<p class="note" style="font-size:1rem;margin-top:-6px">{ui.esc(question)}</p>', unsafe_allow_html=True)


def _data(frame, name, sql):
    with st.expander('📋 See the data'):
        st.dataframe(frame, hide_index=True, width='stretch')
        ui.download(frame, name)
    ui.show_sql(sql)


# ---------------- Technical deep dives ----------------

def _place_labels(nx, ny, texts, radii, width=1000, height=500):
    '''Greedy label placement: try spots around each bubble (in pixels) and keep the first that hits no other label or bubble.'''
    px_x, px_y = nx * width, ny * height
    bubbles = [(px_x[i] - r, px_y[i] - r, px_x[i] + r, px_y[i] + r) for i, r in enumerate(radii)]
    placed, shifts = [], []
    for i in np.argsort(-np.asarray(radii)):
        w, h, r = 7.2 * len(texts[i]) + 6, 16, radii[i]
        options = [(0, r + 10), (0, -(r + 10)), (r + w / 2 + 4, 0), (-(r + w / 2 + 4), 0),
                   (0, r + 28), (0, -(r + 28)), (r + w / 2 + 4, 18), (-(r + w / 2 + 4), -18)]
        for dx, dy in options:
            cx, cy = px_x[i] + dx, px_y[i] + dy
            box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            hit = lambda o: not (box[2] < o[0] or box[0] > o[2] or box[3] < o[1] or box[1] > o[3])
            if not any(hit(o) for o in placed) and not any(hit(o) for j, o in enumerate(bubbles) if j != i):
                break
        placed.append(box)
        shifts.append((i, dx, dy))
    return sorted(shifts)


def volume_vs_loyalty():
    _head('📈', 'Volume vs loyalty by department', 'Each bubble is a department. Right means more items bought, higher means more reorders, bigger means more products.')
    d = run('departments')
    d = d[~d['department'].isin(['missing', 'other'])].reset_index(drop=True)
    logx = np.log10(d['items'])
    mx, my = float(np.median(logx)), float(d['reorder_pct'].median())
    fig = go.Figure()
    sizes = 10 + 34 * np.sqrt(d['products'] / d['products'].max())
    texts = [f'{ui.dept_emoji(x)} {x}' for x in d['department']]
    ymin, ymax = d['reorder_pct'].min() - 6, d['reorder_pct'].max() + 6
    xmin, xmax = logx.min() - 0.15, logx.max() + 0.15
    for i, dx, dy in _place_labels(((logx - xmin) / (xmax - xmin)).values, ((d['reorder_pct'] - ymin) / (ymax - ymin)).values,
                                   texts, list(sizes / 2)):
        fig.add_annotation(x=logx.iloc[i], y=d['reorder_pct'].iloc[i], text=texts[i], showarrow=False, xshift=dx, yshift=dy,
                           font=dict(size=13, color='#3E4C43'))
    fig.add_scatter(x=d['items'], y=d['reorder_pct'], mode='markers',
                    marker=dict(size=sizes, sizemode='diameter',
                                color=[ui.DEPARTMENT_COLOR.get(x, ui.GREEN) for x in d['department']], opacity=.75,
                                line=dict(color='white', width=1.5)),
                    customdata=d[['department', 'products', 'customers']].values,
                    hovertemplate='<b>%{customdata[0]}</b><br>Items: %{x:,}<br>Reorder: %{y}%<br>Products: %{customdata[1]:,}<extra></extra>')
    fig.add_vline(x=10 ** mx, line_dash='dot', line_color='#B8C4B2')
    fig.add_hline(y=my, line_dash='dot', line_color='#B8C4B2')
    for xa, ya, text in [(0.99, 0.99, 'Big and habitual'), (0.01, 0.99, 'Small but loyal'),
                         (0.99, 0.01, 'Big but switchy'), (0.01, 0.01, 'Small and switchy')]:
        fig.add_annotation(xref='paper', yref='paper', x=xa, y=ya, text=f'<b>{text}</b>', showarrow=False,
                           xanchor='right' if xa > .5 else 'left', yanchor='top' if ya > .5 else 'bottom',
                           font=dict(size=13, color='#8A978E'))
    fig.update_xaxes(type='log', title='Items bought (log scale)', range=[xmin, xmax])
    fig.update_yaxes(title='Reorder rate (%)', range=[ymin, ymax])
    fig.update_layout(title='Departments: scale vs repeat behaviour', showlegend=False)
    ui.chart(fig, height=620)
    r = np.corrcoef(logx, d['reorder_pct'])[0, 1]
    ui.insight(f"Correlation between log(volume) and reorder rate across departments: <b>r = {r:.2f}</b>. "
               f"Produce and dairy are big <i>and</i> habitual. Pantry, personal care and household are bought often "
               f"but people rarely pick the same product again, which is where brand switching and promotions work best.")
    _data(d, 'departments.csv', SQL['departments'])


def order_sequence():
    _head('🔁', 'Reorder rate by order sequence', 'How behaviour changes from a customer’s 1st order to their 100th.')
    df = run('order_sequence')
    fig = go.Figure()
    fig.add_bar(x=df['order_number'], y=df['customers'], name='Customers observed', marker_color='#D7E6D0', yaxis='y2')
    fig.add_scatter(x=df['order_number'], y=df['reorder_pct'], name='Reorder rate %', line=dict(color=ui.GREEN, width=3))
    fig.update_layout(title='Reorder rate rises with every order while the observed base shrinks',
                      xaxis_title='Order number', yaxis=dict(title='Reorder rate (%)'),
                      yaxis2=dict(title='Customers', overlaying='y', side='right', showgrid=False), legend=dict(orientation='h', y=1.08))
    ui.chart(fig, height=460)
    first = df[df['order_number'] == 1]['reorder_pct']
    tenth = df[df['order_number'] == 10]['reorder_pct']
    ui.insight(f"Order #1 has a reorder rate of <b>{first.iloc[0] if len(first) else 0}%</b> (by definition nothing has been bought before); "
               f"by order #10 it reaches <b>{tenth.iloc[0] if len(tenth) else 'n/a'}%</b>. This is <i>sequence</i>, not calendar retention: "
               f"survivorship bias means later points describe only the most engaged customers.")
    _data(df, 'order_sequence.csv', SQL['order_sequence'])


def cart_position():
    _head('🛒', 'Cart position vs reorder probability', 'Are items added earlier more likely to be repeat purchases?')
    df = run('cart_position')
    fig = go.Figure()
    fig.add_bar(x=df['cart_position'], y=df['items'], name='Items', marker_color='#FFE3C7', yaxis='y2')
    fig.add_scatter(x=df['cart_position'], y=df['reorder_pct'], name='Reorder rate %', line=dict(color=ui.ORANGE, width=3))
    fig.update_layout(title='Earlier in the cart → more likely a reorder', xaxis_title='Position the item was added',
                      yaxis=dict(title='Reorder rate (%)'), yaxis2=dict(title='Items', overlaying='y', side='right', showgrid=False),
                      legend=dict(orientation='h', y=1.08))
    ui.chart(fig, height=440)
    a, b = df.iloc[0], df[df['cart_position'] == 20]
    ui.insight(f"Position 1 items are reorders <b>{a['reorder_pct']}%</b> of the time vs "
               f"<b>{b['reorder_pct'].iloc[0] if len(b) else 'n/a'}%</b> at position 20: shoppers grab known favourites first, "
               f"then explore. A strong feature for a “will this be reordered?” model.")
    _data(df, 'cart_position.csv', SQL['cart_position'])


def long_tail():
    _head('📉', 'The long tail of product demand', 'Pareto curve: what share of all purchases comes from the top X% of products?')
    items = run('product_curve')['items'].to_numpy()
    cum = np.cumsum(items) / items.sum() * 100
    pct = np.arange(1, len(items) + 1) / len(items) * 100
    step = max(1, len(items) // 800)
    curve = pd.DataFrame({'products_pct': pct[::step], 'items_pct': cum[::step]})
    fig = px.area(curve, x='products_pct', y='items_pct', labels={'products_pct': '% of products (most popular first)', 'items_pct': '% of all items bought'},
                  title='Cumulative share of purchases')
    fig.update_traces(line_color=ui.BLUE, fillcolor='rgba(76,110,245,.15)')
    at = lambda p: cum[max(0, int(len(items) * p / 100) - 1)]
    for p in (1, 10, 20):
        fig.add_scatter(x=[p], y=[at(p)], mode='markers+text', text=[f'top {p}% → {at(p):.0f}%'], textposition='middle right',
                        marker=dict(size=11, color=ui.PINK), showlegend=False)
    ui.chart(fig, height=440)
    once = int((items < 10).sum())
    ui.insight(f"The top <b>1%</b> of products drive <b>{at(1):.0f}%</b> of purchases and the top <b>20%</b> drive <b>{at(20):.0f}%</b> "
               f", a classic Pareto pattern. <b>{once:,}</b> products were bought fewer than 10 times (the long tail).")
    ui.show_sql(SQL['product_curve'])


def customer_distributions():
    _head('📦', 'Customer level distributions', 'One row per customer: how many orders, how big, how loyal.')
    df = run('customers')
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(df[df['orders'] <= 30], x='orders', nbins=30, title='Observed orders per customer',
                           labels={'orders': 'Orders'})
        fig.update_traces(marker_color=ui.BLUE)
        ui.chart(fig, height=340)
    with c2:
        fig = px.histogram(df[df['avg_basket'] <= 40], x='avg_basket', nbins=40, title='Average basket per customer',
                           labels={'avg_basket': 'Avg items per order'})
        fig.update_traces(marker_color=ui.ORANGE)
        ui.chart(fig, height=340)
    df['orders_band'] = pd.cut(df['orders'], [0, 1, 3, 6, 10, 1000], labels=['1', '2 to 3', '4 to 6', '7 to 10', '11+'])
    fig = px.box(df, x='orders_band', y='reorder_pct', points=False, color='orders_band',
                 labels={'orders_band': 'Orders observed', 'reorder_pct': 'Customer reorder rate (%)'},
                 title='Reorder rate distribution by customer frequency')
    fig.update_layout(showlegend=False)
    ui.chart(fig, height=380)
    corr = df[['orders', 'avg_basket', 'avg_days_between', 'reorder_pct']].corr(method='spearman').round(2)
    st.markdown('**Spearman correlation between customer features**')
    st.dataframe(corr, width='stretch')
    ui.insight(f"Median customer: <b>{df['orders'].median():.0f}</b> orders, <b>{df['avg_basket'].median():.1f}</b> items per order. "
               f"Order count vs reorder rate: Spearman ρ = <b>{corr.loc['orders','reorder_pct']}</b>; "
               f"vs days between orders: ρ = <b>{corr.loc['avg_days_between','reorder_pct']}</b>. Frequent, regular shoppers are the loyal ones.")
    ui.show_sql(SQL['customers'])


def lift_method():
    _head('🧮', 'Market basket analysis: how lift works', 'The method behind “What do people buy together?”.')
    st.latex(r'\text{lift}(A,B)=\frac{P(A \cap B)}{P(A)\,P(B)}=\frac{\text{orders with A and B}\times N}{\text{orders with A}\times\text{orders with B}}')
    st.markdown('Lift = 1 means independent; lift > 1 means the pair appears together more than chance. '
                'Only the 150 most popular products and pairs seen in ≥ 50 orders are scored, which keeps the self join on '
                '4.5M rows tractable and avoids noisy small sample lifts.')
    df = raw('SELECT product_a, product_b, co_orders, lift FROM mart_pairs')
    fig = px.scatter(df, x='co_orders', y='lift', log_x=True, opacity=.55, hover_data=['product_a', 'product_b'],
                     labels={'co_orders': 'Orders containing both (log)', 'lift': 'Lift'}, title=f'All {len(df):,} scored pairs')
    fig.update_traces(marker=dict(color=ui.PINK, size=6))
    fig.add_hline(y=1, line_dash='dash', line_color='#8A978E', annotation_text='chance')
    ui.chart(fig, height=440)
    ui.insight(f"<b>{100*(df['lift']>1).mean():.0f}%</b> of scored pairs have lift above 1. The highest lifts come from "
               f"near substitutes in the same aisle (flavours of sparkling water, types of peppers). High lift does not "
               f"always mean “complementary”, which is why both lift and support are shown.")
    ui.show_sql(MARTS['mart_pairs'])


def data_quality():
    _head('🧪', 'Data quality and cleaning', 'What was wrong with the raw files, what was fixed, and live integrity checks.')
    st.markdown('''
| Step | Issue found in the raw files | Fix applied |
|---|---|---|
| 1 | Files used `;` separators; orders file named `instacart_orders.csv` | Converted to standard CSV with expected names |
| 2 | 15 exact duplicate rows in orders | Removed duplicates (order_id is now unique) |
| 3 | 1,258 products with no name | Filled with `Unknown` (kept, so purchases still count) |
| 4 | 836 order lines with no cart position | Left as NULL (excluded from cart position averages only) |
| 5 | No `eval_set` column | Added; all rows treated as history (`prior`) |
| 6 | First order of each customer has no “days since prior” | Expected, left as NULL |
''')
    checks = raw('''SELECT
        (SELECT COUNT(*) FROM orders) AS orders_total,
        (SELECT COUNT(*) FROM basket_sizes) AS orders_with_items,
        (SELECT COUNT(*) FROM products WHERE product_name = 'Unknown') AS unnamed_products,
        (SELECT COUNT(*) FROM order_products__prior WHERE add_to_cart_order IS NULL) AS missing_cart_position,
        (SELECT COUNT(*) FROM orders WHERE days_since_prior_order IS NULL) AS first_orders''').iloc[0]
    cols = st.columns(5)
    for col, (label, key, color) in zip(cols, [('Orders in file', 'orders_total', ui.BLUE), ('Orders with items', 'orders_with_items', ui.GREEN),
                                               ('Unnamed products', 'unnamed_products', ui.ORANGE), ('Missing cart position', 'missing_cart_position', ui.PINK),
                                               ('First orders (no gap)', 'first_orders', ui.YELLOW)]):
        with col: ui.kpi('🔎', label, f'{int(checks[key]):,}', '', color)
    st.markdown(' ')
    if st.button('▶️ Run full integrity checks', type='primary', key='dq_run'):
        with st.spinner('Checking millions of rows…'):
            from src.data import check
            with connect(read_only=True) as conn: res = check(conn)
        out = pd.DataFrame([{'check': k, 'problems found': v, 'status': '✅ pass' if v == 0 else '❌ fail'} for k, v in res.items()])
        st.dataframe(out, hide_index=True, width='stretch')
    ui.insight(f"<b>{int(checks['orders_total'] - checks['orders_with_items']):,}</b> orders in the orders file have no products "
               f"in this sample. Dashboards count only orders with items, so they are never treated as empty baskets.")


def database_performance():
    _head('⚙️', 'Database design and performance', 'How the data is stored and why pages load fast.')
    sizes = raw('''SELECT c.relname AS table_name, c.reltuples::bigint AS approx_rows,
        pg_size_pretty(pg_total_relation_size(c.oid)) AS size_on_disk, pg_total_relation_size(c.oid) AS bytes
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY bytes DESC''')
    sizes['layer'] = np.where(sizes['table_name'].str.startswith('mart_'), 'Summary (mart)',
                              np.where(sizes['table_name'].isin(['order_items', 'basket_sizes']), 'Modeled', 'Raw'))
    fig = px.bar(sizes, x='table_name', y='bytes', color='layer', log_y=True,
                 color_discrete_map={'Raw': ui.BLUE, 'Modeled': ui.ORANGE, 'Summary (mart)': ui.GREEN},
                 labels={'table_name': '', 'bytes': 'Size in bytes (log)'}, title='Tables by layer and size')
    ui.chart(fig, height=420)
    st.dataframe(sizes.drop(columns='bytes'), hide_index=True, width='stretch')
    st.markdown('''**Design choices**
- **Raw layer:** the six CSVs loaded with PostgreSQL `COPY` in 1 MB chunks.
- **Modeled layer:** `order_items` joins orders, products, aisles and departments once, stored sorted by `order_id` with indexes; `basket_sizes` has one row per order.
- **Summary layer:** 11 `mart_*` tables summarise the expensive work (distinct counts, the product pair self join), so dashboards read hundreds of rows instead of millions.
- **Session tuning:** JIT disabled and `work_mem` raised for analytical aggregates.''')
    if st.button('⏱️ Race: raw table vs summary table', key='perf_race'):
        with connect(read_only=True) as conn:
            t = time.perf_counter(); conn.execute('SELECT department, COUNT(*), COUNT(DISTINCT order_id) FROM order_items GROUP BY 1').fetchall()
            slow = time.perf_counter() - t
            t = time.perf_counter(); conn.execute('SELECT department, items, orders FROM mart_department').fetchall()
            fast = time.perf_counter() - t
        c1, c2, c3 = st.columns(3)
        with c1: ui.kpi('🐢', 'Scan 4.5M rows', f'{slow*1000:,.0f} ms', 'Table order_items', ui.ORANGE)
        with c2: ui.kpi('⚡', 'Read summary', f'{fast*1000:,.1f} ms', 'Table mart_department', ui.GREEN)
        with c3: ui.kpi('🚀', 'Speed up', f'{slow/max(fast,1e-4):,.0f}×', 'Same answer', ui.BLUE)
    idx = raw("SELECT tablename AS table_name, indexname AS index_name FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2")
    with st.expander(f'🗂️ {len(idx)} indexes'):
        st.dataframe(idx, hide_index=True, width='stretch')


def department_affinity():
    _head('🧲', 'Department affinity matrix', 'Lift between departments: which departments share baskets more than chance?')
    df = run('dept_pairs')
    df = df[~df['dept_a'].isin(['missing', 'other', 'bulk']) & ~df['dept_b'].isin(['missing', 'other', 'bulk'])]
    full = pd.concat([df, df.rename(columns={'dept_a': 'dept_b', 'dept_b': 'dept_a'})])
    order = run('departments')['department']
    order = [d for d in order if d in set(full['dept_a'])]
    grid = full.pivot(index='dept_a', columns='dept_b', values='lift').reindex(index=order, columns=order)
    fig = px.imshow(grid.values, x=[f'{ui.dept_emoji(d)} {d}' for d in order], y=[f'{ui.dept_emoji(d)} {d}' for d in order],
                    color_continuous_scale='RdBu', color_continuous_midpoint=1.0, zmin=0.4, zmax=1.6, aspect='auto',
                    labels=dict(color='Lift'), title='Lift > 1 (blue) = bought together more than chance; < 1 (red) = less')
    fig.update_layout(font=dict(size=12))
    ui.chart(fig, height=640)
    top = df.sort_values('lift', ascending=False).head(3)
    low = df.sort_values('lift').head(2)
    ui.insight('Strongest department pairs: ' + '; '.join(f"<b>{ui.esc(r.dept_a)} + {ui.esc(r.dept_b)}</b> ({r.lift:.2f}×)" for r in top.itertuples())
               + '. Least likely together: ' + '; '.join(f"{ui.esc(r.dept_a)} + {ui.esc(r.dept_b)} ({r.lift:.2f}×)" for r in low.itertuples())
               + '. Lift is computed on distinct (order, department) pairs, so big baskets do not dominate.')
    _data(df, 'department_affinity.csv', MARTS['mart_department_pairs'])


TECHNICAL = {
    'volume': ('📈', 'Volume vs loyalty', 'Which departments are big and habitual, and which are big but switchy?', 'Statistics', volume_vs_loyalty),
    'sequence': ('🔁', 'Order sequence', 'How does reordering change from a customer’s 1st order to their 100th?', 'Behaviour', order_sequence),
    'cart': ('🛒', 'Cart position', 'Are items added earlier more likely to be repeat purchases?', 'Behaviour', cart_position),
    'pareto': ('📉', 'Long tail (Pareto)', 'What share of purchases comes from the top 1%, 10% and 20% of products?', 'Statistics', long_tail),
    'affinity': ('🧲', 'Department affinity', 'Which departments end up in the same basket more than chance?', 'Market basket', department_affinity),
    'customers': ('📦', 'Customer distributions', 'How are orders, basket size and loyalty spread across customers?', 'Statistics', customer_distributions),
    'lift': ('🧮', 'Lift method', 'How “bought together” scores are calculated, with the formula.', 'Market basket', lift_method),
    'quality': ('🧪', 'Data quality', 'What was wrong in the raw files, what was fixed, and live integrity checks.', 'Data engineering', data_quality),
    'performance': ('⚙️', 'Database and performance', 'How the data is stored and a live speed race between raw and summary tables.', 'Data engineering', database_performance),
}
TAG_COLORS = {'Statistics': ui.BLUE, 'Behaviour': ui.GREEN, 'Market basket': ui.PINK, 'Data engineering': ui.ORANGE}


def render():
    open_key = st.session_state.get('deep_open')
    if open_key in TECHNICAL:
        ui.back_button('deep_open', '← All deep dives')
        with st.container(border=True):
            TECHNICAL[open_key][4]()
    else:
        ui.page_header('🧪', 'Deep dives', f'{len(TECHNICAL)} technical analyses with methods, statistics and SQL. Pick one to open it.', ui.BLUE)
        ui.gallery([(k, e, t, q, tag, TAG_COLORS[tag]) for k, (e, t, q, tag, _) in TECHNICAL.items()], 'deep_open')
    ui.footer()
