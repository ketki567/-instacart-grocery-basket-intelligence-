'''Home: what the project is about, big numbers, five revelations, and where to go next.'''
import streamlit as st
from src import ui
from src.analytics import run, DAY_NAMES, hour_label
from src.nav import PAGES


def _open_story(key):
    st.session_state['open_story'] = key


def render():
    k = run('kpis').iloc[0]
    ui.hero('What 450,000 grocery orders reveal about the people who shop',
            'A study of real customer shopping behavior. It answers what people buy, when they shop, '
            'what they buy together and who keeps coming back.',
            chips=['Customer behavior', 'Shopping patterns', 'PostgreSQL', 'Python', 'SQL Lab'],
            art=['🥑', '🍌', '🥛', '🥖', '🍓', '🧀', '🥦', '🍿', '🥚', '☕', '🍋', '🥕'], brand=f'🛒 {ui.PROJECT_NAME}')

    cols = st.columns(4)
    for col, (icon, label, value, sub, color) in zip(cols, [
            ('🧾', 'Orders', f"{int(k['orders']):,}", 'Analysed', ui.GREEN),
            ('👥', 'Shoppers', f"{int(k['customers']):,}", 'Anonymized customers', ui.BLUE),
            ('🛒', 'Items bought', f"{int(k['items']):,}", 'Purchase lines', ui.ORANGE),
            ('🏷️', 'Products', f"{int(k['products']):,}", 'Across 21 departments', ui.PINK)]):
        with col: ui.kpi(icon, label, value, sub, color)

    ui.section('✨', '5 things this data reveals')
    top = run('top_products', dept='All', n=1).iloc[0]
    hd = run('hour_day').sort_values('orders', ascending=False).iloc[0]
    days = run('days_between')
    week = 100 * days[days['days'] == 7]['orders'].sum() / days['orders'].sum()
    org = run('organic').set_index('type')
    seg = run('customer_segments')
    heavy = seg[seg['sort_key'] >= 4]
    reveals = [
        ('basket', ui.product_emoji(top['product_name']), f"{top['product_name']} is the #1 product",
         f"Bought {int(top['items']):,} times, and most of the top 10 are fresh produce.", ui.ORANGE),
        ('rush', '⏰', f"{DAY_NAMES[int(hd['order_dow'])]} {hour_label(hd['order_hour_of_day'])} is rush hour",
         'Shopping is concentrated in late mornings early in the week.', ui.GREEN),
        ('habit', '📅', 'Shoppers run on a 7 day clock', f'The biggest regular spike is exactly one week after the last order ({week:.0f}%).', ui.PINK),
        ('organic', '🌱', 'Organic buyers are more loyal',
         f"Reordered {org.loc['Organic','reorder_pct']:.0f}% vs {org.loc['Conventional','reorder_pct']:.0f}% for conventional items.", ui.PALETTE[5]),
        ('core', '👥', f"{100*heavy['customers'].sum()/seg['customers'].sum():.0f}% of shoppers buy {100*heavy['items'].sum()/seg['items'].sum():.0f}% of items",
         'A small group of regulars drives most of the volume.', ui.BLUE),
    ]
    cols = st.columns(5)
    for i, (col, (key, emoji, title, text, color)) in enumerate(zip(cols, reveals), start=1):
        with col:
            ui.reveal(i, emoji, title, text, color)
            if st.button('Read the story →', key=f'reveal_{key}', on_click=_open_story, args=(key,), width='stretch'):
                st.switch_page(PAGES['insights'])

    ui.section('🧭', 'Where to next?')
    cols = st.columns(5)
    for col, (emoji, title, text, key) in zip(cols, [
            ('💡', 'Insights', 'Nine short stories with one chart each, written for anyone.', 'insights'),
            ('🧪', 'Deep dives', 'Methods, statistics, data quality and SQL for analysts.', 'deep'),
            ('🤖', 'Advanced', 'Cohorts, customer segments, a reorder prediction model and A/B test design.', 'advanced'),
            ('🔎', 'Look up', 'Search any product or department and get its profile.', 'lookup'),
            ('💬', 'Ask the data', 'Build your own question, or write SQL in the SQL Lab.', 'ask')]):
        with col:
            ui.card(emoji, title, text)
            st.page_link(PAGES[key], label=f'Open {title}', icon='➡️')
    ui.footer()
