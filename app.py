"""Instacart Grocery Basket Intelligence: interactive grocery analytics on PostgreSQL."""
import streamlit as st
from src import ui
from src.analytics import run
from src.nav import PAGES
from views import home, insights, deep_dives, advanced, lookup, ask, docs

st.set_page_config(page_title='Instacart Grocery Basket Intelligence', page_icon='🛒', layout='wide')
ui.setup_charts()
ui.inject_css()

try:
    run('kpis')
except Exception as exc:
    ui.hero('Almost there — the database isn’t ready', 'Load the data into PostgreSQL, then refresh this page.')
    st.error('PostgreSQL is not connected, or the data and summary tables have not been built yet.')
    st.code('python build.py\npython -m streamlit run app.py', language='bash')
    st.caption('Database settings come from the .env file next to app.py (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD).')
    st.caption(str(exc)[:300])
    st.stop()

PAGES.update({
    'home': st.Page(home.render, title='Home', icon='🏠', url_path='home', default=True),
    'insights': st.Page(insights.render, title='Insights', icon='💡', url_path='insights'),
    'deep': st.Page(deep_dives.render, title='Deep dives', icon='🧪', url_path='deep-dives'),
    'advanced': st.Page(advanced.render, title='Advanced', icon='🤖', url_path='advanced'),
    'lookup': st.Page(lookup.render, title='Look up', icon='🔎', url_path='lookup'),
    'ask': st.Page(ask.render, title='Ask the data', icon='💬', url_path='ask'),
    'docs': st.Page(docs.render, title='Documentation', icon='📚', url_path='docs'),
})
st.navigation(list(PAGES.values()), position='top').run()
