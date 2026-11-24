'''Look up: search any product or department and get its profile: rank, loyalty, timing, and what it is bought with.'''
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src import ui
from src.analytics import raw, run, SQL, DAY_NAMES, hour_label


@st.cache_data(show_spinner=False)
def _catalog():
    df = raw('SELECT * FROM mart_product ORDER BY items DESC')
    df['rank'] = range(1, len(df) + 1)
    return df


def _banner(emoji, title, subtitle, chips, color):
    chip_html = ''.join(f'<span class="chip">{ui.esc(c)}</span>' for c in chips)
    st.markdown(f'''<div class="hero" style="background:linear-gradient(120deg,{color},{color}B3 55%,#FFE7C2);padding:28px 34px">
        <div style="display:flex;align-items:center;gap:22px"><div style="font-size:78px;line-height:1">{emoji}</div>
        <div><h1 style="font-size:2.3rem;margin-bottom:6px">{ui.esc(title)}</h1><p>{ui.esc(subtitle)}</p>
        <div class="chips">{chip_html}</div></div></div></div>''', unsafe_allow_html=True)


def _hour_profile(own, title, color):
    store = run('dept_time', dept='All').groupby('order_hour_of_day', as_index=False)['items'].sum()
    own = own.set_index(own.columns[0])['items'].reindex(range(24), fill_value=0)
    fig = go.Figure()
    fig.add_scatter(x=list(range(24)), y=100 * store['items'] / store['items'].sum(), name='Whole store',
                    line=dict(color='#B8C4B2', width=3, dash='dot'))
    fig.add_scatter(x=list(range(24)), y=100 * own / max(own.sum(), 1), name=title,
                    line=dict(color=color, width=4), fill='tozeroy', fillcolor='rgba(15,157,88,.08)')
    fig.update_layout(title='When it sells (share of its day, by hour)', yaxis_title='% of items', legend=dict(orientation='h', y=-0.2),
                      font=dict(size=13), xaxis=dict(tickvals=list(range(0, 24, 3)), ticktext=[hour_label(h) for h in range(0, 24, 3)]))
    ui.chart(fig, height=380)
    store_share = store.set_index('order_hour_of_day')['items'] / store['items'].sum()
    index = (own / max(own.sum(), 1)) / store_share
    return int(index[own > own.sum() * 0.04].idxmax())  # only hours with a meaningful share of its sales


def _product_cards(df, color, sub):
    cols = st.columns(4)
    for i, (_, p) in enumerate(df.iterrows()):
        with cols[i % 4]:
            st.markdown(f'''<div class="tile" style="background:linear-gradient(160deg,{color}22,#ffffff);min-height:150px">
                <div class="emoji">{ui.product_emoji(p['product_name'], p.get('department'))}</div>
                <div class="name" style="text-transform:none;font-size:.95rem">{ui.esc(p['product_name'])}</div>
                <div class="stat">{sub(p)}</div></div>''', unsafe_allow_html=True)
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)


def _pick_product(name):
    st.session_state['lookup_product'] = name


def product_profile():
    cat = _catalog()
    st.markdown('**Popular picks**')
    with st.container(horizontal=True):
        for name in cat.head(8)['product_name']:
            st.button(f'{ui.product_emoji(name)} {name}', key=f'pick_{name}', on_click=_pick_product, args=(name,))
    search = st.text_input('🔎 Search any of the products', placeholder='Type a few letters, e.g. "almond milk", "chips", "salmon"',
                           key='lookup_search')
    matches = run('product_search', search=f'%{search.strip()}%') if search.strip() else cat.head(25)
    if matches.empty:
        st.info('No product matches that search.'); return
    names = matches['product_name'].tolist()
    current = st.session_state.get('lookup_product')
    if current not in names: current = names[0]
    name = st.selectbox(f'{len(names)} matches. Pick one', names, index=names.index(current),
                        format_func=lambda n: f'{ui.product_emoji(n)}  {n}')
    p = cat[cat['product_name'] == name].iloc[0]
    color = ui.DEPARTMENT_COLOR.get(p['department'], ui.GREEN)
    store_reorder = float(run('kpis').iloc[0]['reorder_pct'])
    _banner(ui.product_emoji(name, p['department']), name, f"{p['aisle']} aisle · {p['department']} department",
            [f"#{int(p['rank']):,} of {len(cat):,} products", f"Top {100 * p['rank'] / len(cat):.1f}%",
             'Organic' if p['is_organic'] else 'Conventional'], color)
    k = st.columns(5)
    with k[0]: ui.kpi('🛒', 'Times bought', f"{int(p['items']):,}", 'Purchase lines', ui.GREEN)
    with k[1]: ui.kpi('👥', 'Shoppers', f"{int(p['customers']):,}", 'Different customers', ui.BLUE)
    with k[2]: ui.kpi('🔁', 'Reorder rate', f"{p['reorder_pct']:.0f}%", f"Store average {store_reorder:.0f}%", ui.PINK)
    with k[3]: ui.kpi('🥇', 'Added first', f"{100 * p['first_in_cart'] / p['items']:.0f}%", 'Of its baskets', ui.ORANGE)
    with k[4]: ui.kpi('📍', 'Cart position', f"{p['avg_cart_position']:.1f}", 'Average', ui.YELLOW)
    st.markdown(' ')
    c1, c2 = st.columns([1.5, 1])
    with c1: peak = _hour_profile(run('product_hours', pid=int(p['product_id'])), name, color)
    with c2:
        days = run('product_days', pid=int(p['product_id']))
        days['day'] = [DAY_NAMES[int(d)] for d in days['order_dow']]
        fig = px.bar(days, x='day', y='items', title='Day of week', labels={'day': '', 'items': 'Times bought'})
        fig.update_traces(marker_color=color)
        ui.chart(fig, height=380)
    ui.insight(f"<b>{ui.esc(name)}</b> sells most above the store average at <b>{hour_label(peak)}</b> compared with the whole store, "
               f"and is reordered {'more' if p['reorder_pct'] > store_reorder else 'less'} than the average product "
               f"({p['reorder_pct']:.0f}% vs {store_reorder:.0f}%).")
    ui.section('🤝', 'Usually bought with')
    with st.spinner('Looking through its baskets…'):
        pairs = run('bought_with', pid=int(p['product_id']))
    if pairs.empty:
        st.caption('Not enough baskets to find reliable companions for this product.')
    else:
        _product_cards(pairs.head(8), ui.PINK, lambda r: f"In <b>{r['pct_of_baskets']:.0f}%</b> of its baskets · {r['lift']:.1f}× chance")
        ui.show_sql(SQL['bought_with'])
    ui.section('🛤️', f"Other popular products in {p['aisle']}")
    same = cat[(cat['aisle'] == p['aisle']) & (cat['product_name'] != name)].head(8)
    st.dataframe(same.assign(picture=[ui.product_emoji(n) for n in same['product_name']])
                 [['picture', 'product_name', 'items', 'reorder_pct', 'rank']], hide_index=True, width='stretch',
                 column_config={'picture': st.column_config.TextColumn('', width='small'), 'product_name': 'Product',
                                'items': st.column_config.NumberColumn('Times bought', format='%d'),
                                'reorder_pct': st.column_config.ProgressColumn('Reorder rate', format='%.0f%%', min_value=0, max_value=100),
                                'rank': st.column_config.NumberColumn('Overall rank', format='#%d')})


def department_profile():
    depts = run('departments')
    names = depts['department'].tolist()
    if st.session_state.get('explore_dept') in names:
        st.session_state['lookup_dept'] = st.session_state.pop('explore_dept')
    st.session_state.setdefault('lookup_dept', names[0])
    dept = st.pills('Department', names, key='lookup_dept', label_visibility='collapsed',
                    format_func=lambda d: f'{ui.dept_emoji(d)} {d}') or names[0]
    d = depts.set_index('department').loc[dept]
    color = ui.DEPARTMENT_COLOR.get(dept, ui.GREEN)
    total = depts['items'].sum()
    _banner(ui.dept_emoji(dept), dept.title(), f"#{names.index(dept) + 1} of {len(names)} departments",
            [f"{100 * d['items'] / total:.1f}% of all items", f"{int(d['products']):,} products", f"{int(d['customers']):,} shoppers"], color)
    k = st.columns(4)
    with k[0]: ui.kpi('🛒', 'Items bought', f"{int(d['items']):,}", '', ui.GREEN)
    with k[1]: ui.kpi('🧾', 'Orders', f"{int(d['orders']):,}", 'Containing this department', ui.BLUE)
    with k[2]: ui.kpi('🔁', 'Reorder rate', f"{d['reorder_pct']:.0f}%", f"Rank #{int(depts['reorder_pct'].rank(ascending=False)[names.index(dept)])} of {len(names)}", ui.PINK)
    with k[3]: ui.kpi('📍', 'Cart position', f"{d['avg_cart_position']:.1f}", 'Lower means grabbed earlier', ui.ORANGE)
    st.markdown(' ')
    aisles = run('aisles')
    aisles = aisles[aisles['department'] == dept].head(10)
    c1, c2 = st.columns([1.2, 1])
    with c1:
        fig = px.bar(aisles, x='items', y='aisle', orientation='h', text='items', title='Biggest aisles', labels={'items': '', 'aisle': ''})
        fig.update_traces(marker_color=color, texttemplate='%{text:,}', textposition='outside', cliponaxis=False)
        fig.update_layout(font=dict(size=13), xaxis=dict(showticklabels=False, showgrid=False, range=[0, aisles['items'].max() * 1.2]))
        ui.chart(fig, height=max(320, 40 * len(aisles) + 80))
    with c2:
        own = run('dept_time', dept=dept).groupby('order_hour_of_day', as_index=False)['items'].sum()
        _hour_profile(own, dept, color)
    ui.section('⭐', f'Best sellers in {dept}')
    top = run('top_products', dept=dept, n=8)
    _product_cards(top, color, lambda r: f"<b>{int(r['items']):,}</b> bought · <b>{r['reorder_pct']:.0f}%</b> reordered")
    ui.section('🧲', 'Departments it shares baskets with')
    pairs = run('dept_pairs')
    mine = pairs[(pairs['dept_a'] == dept) | (pairs['dept_b'] == dept)].copy()
    mine['other'] = [b if a == dept else a for a, b in zip(mine['dept_a'], mine['dept_b'])]
    mine = mine[~mine['other'].isin(['missing', 'other'])].sort_values('lift', ascending=False).head(6)
    cols = st.columns(len(mine)) if len(mine) else []
    for col, r in zip(cols, mine.itertuples()):
        with col: ui.tile(ui.dept_emoji(r.other), r.other, f'{r.lift:.2f}× chance', min(100, r.lift * 50), ui.DEPARTMENT_COLOR.get(r.other, ui.GREEN))


def render():
    ui.page_header('🔎', 'Look up', 'Search any product or department and get its full profile.', ui.ORANGE)
    if st.session_state.get('explore_dept'):
        st.session_state['lookup_mode'] = '🏬 A department'
    st.session_state.setdefault('lookup_mode', '🏷️ A product')
    mode = st.segmented_control('What do you want to look up?', ['🏷️ A product', '🏬 A department'], key='lookup_mode') or '🏷️ A product'
    if mode.endswith('product'): product_profile()
    else: department_profile()
    ui.footer()
