'''Insights: nine plain-English stories, one clean chart each, with a takeaway and a "So what?" recommendation.'''
import numpy as np
import plotly.express as px
import streamlit as st
from src import ui
from src.analytics import run, DAY_NAMES, hour_label
from src.nav import PAGES


def df_total_products():
    return int(run('kpis').iloc[0]['products'])


def _bar_h(df, x, y, title, color=ui.GREEN, highlight_first=True, height=440, xlabel=''):
    colors = [ui.ORANGE if (highlight_first and i == 0) else color for i in range(len(df))]
    fig = px.bar(df, x=x, y=y, orientation='h', title=title, labels={x: xlabel, y: ''}, text=x)
    fig.update_traces(marker_color=colors, texttemplate='%{text:,.0f}', textposition='outside', cliponaxis=False)
    fig.update_layout(font=dict(size=14), xaxis=dict(showgrid=False, showticklabels=False, range=[0, df[x].max() * 1.15]))
    ui.chart(fig, height=height)


def everyday_basket():
    df = run('top_products', dept='All', n=10)
    total = run('kpis').iloc[0]['items']
    share = 100 * df['items'].sum() / total
    produce = (df['department'] == 'produce').sum()
    ui.story_header('Story 1 · What people buy', f'{produce} of the top 10 products are fresh produce',
                    'The ten most purchased products across all orders.')
    df['label'] = [f'{ui.product_emoji(n)}  {n}' for n in df['product_name']]
    _bar_h(df, 'items', 'label', 'Times bought', xlabel='Times bought')
    ui.insight(f"<b>{ui.esc(df.iloc[0]['product_name'])}</b> tops the list, bought {df['items'].iloc[0]:,.0f} times. "
               f"Out of {df_total_products():,} products, these 10 alone are <b>{share:.1f}%</b> of every item bought. "
               f"The everyday basket is fruit, veg and organic staples.")
    ui.so_what('Never let these run out of stock, and put them on the home screen. They are what customers came for.')


def where_volume_is():
    d = run('departments')
    share = 100 * d['items'] / d['items'].sum()
    ui.story_header('Story 2 · Where the volume is', f'Produce and dairy make up {share.iloc[:2].sum():.0f}% of everything sold',
                    'Every department ranked by items bought. Pick one below to see its biggest aisles.')
    d = d.assign(label=[f'{ui.dept_emoji(x)}  {x}' for x in d['department']], share=share.round(1))
    fig = px.bar(d, x='share', y='label', orientation='h', text='share', labels={'share': '% of items', 'label': ''},
                 title='Share of all items bought, by department')
    fig.update_traces(marker_color=[ui.DEPARTMENT_COLOR.get(x, ui.GREEN) for x in d['department']],
                      texttemplate='%{text:.1f}%', textposition='outside', cliponaxis=False)
    fig.update_layout(font=dict(size=13), xaxis=dict(showgrid=False, showticklabels=False, range=[0, d['share'].max() * 1.12]))
    ui.chart(fig, height=620)
    pick = st.pills('Open a department', d['department'].tolist(), default=d['department'].iloc[0], key='ins_dept',
                    format_func=lambda x: f'{ui.dept_emoji(x)} {x}') or d['department'].iloc[0]
    aisles = run('aisles')
    aisles = aisles[aisles['department'] == pick].head(10).copy()
    aisles['share'] = 100 * aisles['items'] / aisles['items'].sum()
    _bar_h(aisles, 'items', 'aisle', f'Top aisles in {pick}', color=ui.DEPARTMENT_COLOR.get(pick, ui.GREEN),
           height=max(300, 40 * len(aisles) + 80), xlabel='Items bought')
    ui.insight(f"In <b>{ui.esc(pick)}</b>, the biggest aisle is <b>{ui.esc(aisles.iloc[0]['aisle'])}</b> "
               f"({aisles.iloc[0]['share']:.0f}% of the department).")
    ui.so_what('Give the biggest departments the most visible space, and use their top aisles as entry points to the rest of the store.')


def rush_hour():
    hd = run('hour_day')
    grid = hd.pivot(index='order_dow', columns='order_hour_of_day', values='orders').fillna(0)
    peak = hd.sort_values('orders', ascending=False).iloc[0]
    ui.story_header('Story 3 · When people shop', f'Rush hour: {DAY_NAMES[int(peak.order_dow)]} at {hour_label(peak.order_hour_of_day)}',
                    'Orders by day of week and hour. Darker = busier.')
    fig = px.imshow(grid.loc[:, 6:23].values, x=[hour_label(h) for h in range(6, 24)], y=[DAY_NAMES[int(d)] for d in grid.index],
                    color_continuous_scale=['#F4FAF1', '#BFE8CF', '#3DBB6E', '#0B7D46'], aspect='auto', labels=dict(color='Orders'))
    fig.update_layout(font=dict(size=14), coloraxis_showscale=False)
    fig.update_xaxes(side='top')
    ui.chart(fig, height=420)
    by_hour = hd.groupby('order_hour_of_day')['orders'].sum()
    day_share = 100 * by_hour.loc[9:17].sum() / by_hour.sum()
    by_day = hd.groupby('order_dow')['orders'].sum()
    weekend = 100 * by_day.loc[[0, 1]].sum() / by_day.sum()
    ui.insight(f"<b>{day_share:.0f}%</b> of orders are placed between 9 am and 6 pm, and the first two days of the week "
               f"take <b>{weekend:.0f}%</b> of all orders. Nights (midnight to 6 am) are almost silent. "
               f"<span class='note'>(Day names assume day 0 is Sunday.)</span>")
    ui.so_what('Staff up and open the most delivery slots on Sunday and Monday late mornings. Send promotions just before that peak.')


def weekly_habit():
    df = run('days_between')
    total = df['orders'].sum()
    week = 100 * df[df['days'] == 7]['orders'].sum() / total
    thirty = 100 * df[df['days'] == 30]['orders'].sum() / total
    ui.story_header('Story 4 · How often people return', 'Shoppers come back on a weekly rhythm or drift away',
                    'Days since the customer’s previous order.')
    colors = [ui.PINK if d in (7, 14, 21) else ui.ORANGE if d == 30 else '#9DB8F2' for d in df['days']]
    fig = px.bar(df, x='days', y='orders', labels={'days': 'Days since previous order', 'orders': 'Orders'})
    fig.update_traces(marker_color=colors)
    fig.add_annotation(x=7, y=df.set_index('days').loc[7, 'orders'], text='one week', showarrow=True, arrowhead=0, ay=-35)
    fig.add_annotation(x=30, y=df.set_index('days').loc[30, 'orders'], text='30+ days', showarrow=True, arrowhead=0, ay=-35)
    fig.update_layout(font=dict(size=14))
    ui.chart(fig, height=420)
    ui.insight(f"The tallest regular spike is at <b>exactly 7 days</b> ({week:.0f}% of repeat orders), with smaller bumps at 14 and 21. "
               f"The bar at 30 (<b>{thirty:.0f}%</b>) means “30 days or more”. These customers are slipping away.")
    ui.so_what('Send a reminder around day 6, and a win back offer to anyone who passes 3 weeks without ordering.')


def top_ups():
    df = run('basket_size')
    expanded = np.repeat(df['basket_size'].values, df['orders'].values)
    median = float(np.median(expanded))
    small = 100 * df[df['basket_size'] <= 10]['orders'].sum() / df['orders'].sum()
    ui.story_header('Story 5 · Basket size', f'{small:.0f}% of orders have 10 items or fewer',
                    'How many items go into one order.')
    show = df[df['basket_size'] <= 40]
    fig = px.bar(show, x='basket_size', y='orders', labels={'basket_size': 'Items in the order', 'orders': 'Orders'})
    fig.update_traces(marker_color=[ui.ORANGE if b <= 10 else '#FFD3AE' for b in show['basket_size']])
    fig.add_vline(x=median, line_dash='dash', line_color=ui.GREEN, annotation_text=f'median: {median:.0f} items', annotation_font_size=14)
    fig.update_layout(font=dict(size=14))
    ui.chart(fig, height=420)
    ui.insight(f"The typical order has <b>{median:.0f} items</b> and the most common size is just "
               f"<b>{int(df.sort_values('orders').iloc[-1]['basket_size'])}</b>. Most trips are quick top ups, not big weekly hauls.")
    ui.so_what('Make reordering a short list effortless with one tap “buy again”, and use free delivery thresholds to grow small baskets.')


def loyalty_staples():
    df = run('loyal_products', dept='All', min_items=1000, n=10)
    df['label'] = [f'{ui.product_emoji(n, d)}  {n}' for n, d in zip(df['product_name'], df['department'])]
    ui.story_header('Story 6 · Loyalty', 'Loyalty lives in staples like milk and water',
                    'Products bought at least 1,000 times, ranked by how often buyers reorder them.')
    fig = px.bar(df, x='reorder_pct', y='label', orientation='h', text='reorder_pct', labels={'reorder_pct': 'Reorder rate', 'label': ''})
    fig.update_traces(marker_color=[ui.DEPARTMENT_COLOR.get(d, ui.GREEN) for d in df['department']],
                      texttemplate='%{text:.0f}%', textposition='outside', cliponaxis=False)
    fig.update_layout(font=dict(size=14), xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False))
    ui.chart(fig, height=440)
    avg = run('kpis').iloc[0]['reorder_pct']
    ui.insight(f"<b>{ui.esc(df.iloc[0]['product_name'])}</b> is reordered <b>{df.iloc[0]['reorder_pct']:.0f}%</b> of the time, "
               f"against a store average of {avg}%. Habit products like milk, water and eggs are bought on autopilot.")
    ui.so_what('Offer subscriptions or automatic reorders on these products. They are the most predictable demand in the store.')


def organic_loyal():
    df = run('organic').set_index('type')
    share_items = 100 * df.loc['Organic', 'items'] / df['items'].sum()
    share_products = 100 * df.loc['Organic', 'products'] / df['products'].sum()
    ui.story_header('Story 7 · Organic', f'Organic is {share_products:.0f}% of products but {share_items:.0f}% of purchases',
                    'Products with “organic” in the name versus everything else.')
    c1, c2, c3 = st.columns(3)
    with c1: ui.kpi('🌱', 'Organic share of items', f'{share_items:.0f}%', f'From only {share_products:.0f}% of products', ui.GREEN)
    with c2: ui.kpi('🔁', 'Organic reorder rate', f"{df.loc['Organic','reorder_pct']:.1f}%", 'Items bought again', ui.GREEN)
    with c3: ui.kpi('🏷️', 'Conventional reorder rate', f"{df.loc['Conventional','reorder_pct']:.1f}%", 'Items bought again', ui.ORANGE)
    by = run('organic_by_dept').head(8)
    by['label'] = [f'{ui.dept_emoji(d)}  {d}' for d in by['department']]
    _bar_h(by, 'organic_share', 'label', 'Most organic departments (% of items)', height=380)
    ui.insight(f"Organic items are reordered <b>{df.loc['Organic','reorder_pct'] - df.loc['Conventional','reorder_pct']:.1f} points</b> "
               f"more often than conventional ones. Organic shoppers are a loyal group that knows what it wants.")
    ui.so_what('Widen the organic range in produce and dairy first, and target organic buyers with loyalty perks.')


def natural_pairs():
    df = run('pairs', min_co=500, n=40, by_lift=False)
    df = df[df['lift'] > 1].head(8)
    ui.story_header('Story 8 · Bought together', 'Some products are natural pairs',
                    'Popular products that land in the same basket more often than chance.')
    cols = st.columns(4)
    for i, (_, r) in enumerate(df.iterrows()):
        with cols[i % 4]:
            st.markdown(f'''<div class="tile" style="background:linear-gradient(160deg,{ui.PINK}1F,#ffffff);min-height:150px">
                <div class="emoji">{ui.product_emoji(r['product_a'])} + {ui.product_emoji(r['product_b'])}</div>
                <div class="name" style="text-transform:none;font-size:.95rem">{ui.esc(r['product_a'])} + {ui.esc(r['product_b'])}</div>
                <div class="stat"><b>{int(r['co_orders']):,}</b> baskets together · <b>{r['lift']:.1f}×</b> chance</div></div>''',
                        unsafe_allow_html=True)
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    top = df.iloc[0]
    ui.insight(f"<b>{ui.esc(top['product_a'])}</b> and <b>{ui.esc(top['product_b'])}</b> share {int(top['co_orders']):,} baskets. "
               f"“Lift” shows how many times more often a pair appears than if people chose products at random.")
    ui.so_what('Use these pairs for “frequently bought together” suggestions and bundle discounts.')


def loyal_core():
    df = run('customer_segments')
    heavy = df[df['sort_key'] >= 4]
    c_share = 100 * heavy['customers'].sum() / df['customers'].sum()
    i_share = 100 * heavy['items'].sum() / df['items'].sum()
    ui.story_header('Story 9 · Customers', f'{c_share:.0f}% of shoppers buy {i_share:.0f}% of the items',
                    'Customers grouped by how many orders we see for them.')
    long = df.melt(id_vars='segment', value_vars=['customers', 'items'], var_name='measure', value_name='value')
    long['pct'] = long.groupby('measure')['value'].transform(lambda v: 100 * v / v.sum())
    long['measure'] = long['measure'].map({'customers': 'Share of shoppers', 'items': 'Share of items bought'})
    fig = px.bar(long, x='pct', y='measure', color='segment', orientation='h', text='pct',
                 category_orders={'segment': df['segment'].tolist()}, labels={'pct': '%', 'measure': '', 'segment': 'Orders seen'})
    fig.update_traces(texttemplate='%{text:.0f}%', textposition='inside', insidetextanchor='middle')
    fig.update_layout(barmode='stack', font=dict(size=14), legend=dict(orientation='h', y=-0.25), xaxis=dict(showticklabels=False, showgrid=False))
    ui.chart(fig, height=320)
    ui.insight(f"Customers with 4 or more orders are only <b>{c_share:.0f}%</b> of shoppers but buy <b>{i_share:.0f}%</b> of items, "
               f"and they reorder far more ({heavy['reorder_pct'].mean():.0f}% vs {df[df['sort_key'] < 4]['reorder_pct'].mean():.0f}%). "
               f"<span class='note'>(Sample data. Some customer histories are incomplete.)</span>")
    ui.so_what('Turn second time buyers into regulars. The jump from 1 to 3 orders to 4 or more is where value multiplies.')


STORIES = {
    'basket': ('🍌', 'Everyday basket', everyday_basket), 'volume': ('🏬', 'Where the volume is', where_volume_is),
    'rush': ('⏰', 'Rush hour', rush_hour), 'habit': ('📅', 'Weekly habit', weekly_habit), 'topups': ('🧺', 'Quick trips', top_ups),
    'loyal': ('💚', 'Loyal staples', loyalty_staples), 'organic': ('🌱', 'Organic', organic_loyal),
    'pairs': ('🤝', 'Natural pairs', natural_pairs), 'core': ('👥', 'Loyal core', loyal_core),
}
KEYS = list(STORIES)


def _go(step):
    i = KEYS.index(st.session_state.get('story_pick') or KEYS[0])
    st.session_state['story_pick'] = KEYS[(i + step) % len(KEYS)]


def render():
    ui.page_header('💡', 'Insights', 'Nine short stories from the data. No jargon, one chart each, and what to do about it.')
    if st.session_state.get('open_story') in KEYS:
        st.session_state['story_pick'] = st.session_state.pop('open_story')
    st.session_state.setdefault('story_pick', KEYS[0])
    key = st.pills('Stories', KEYS, key='story_pick', label_visibility='collapsed',
                   format_func=lambda k: f'{STORIES[k][0]} {STORIES[k][1]}') or KEYS[0]
    with st.container(border=True):
        STORIES[key][2]()
    i = KEYS.index(key)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: st.button(f'← {STORIES[KEYS[i - 1]][1]}', on_click=_go, args=(-1,), width='stretch', key='prev_story')
    with c2: st.markdown(f"<p class='note' style='text-align:center;margin-top:8px'>Story {i + 1} of {len(KEYS)} · "
                         f"Want the methods? See Deep dives</p>", unsafe_allow_html=True)
    with c3: st.button(f'{STORIES[KEYS[(i + 1) % len(KEYS)]][1]} →', on_click=_go, args=(1,), width='stretch', type='primary', key='next_story')
    if 'deep' in PAGES: st.page_link(PAGES['deep'], label='How were these calculated? Open the technical deep dives', icon='🧪')
    ui.footer()
