'''Shared look and feel: page styling, chart theme, cards, and food "pictures" (emoji illustrations).'''
import html
import plotly.express as px
import plotly.io as pio
import streamlit as st

PROJECT_NAME = 'Instacart Grocery Basket Intelligence'

PALETTE = ['#0F9D58', '#FF7A1A', '#E5487F', '#4C6EF5', '#F2B705', '#12B5B0', '#8E5BD8', '#7CB518', '#F25C54', '#2D8CFF']
GREEN, ORANGE, PINK, BLUE, YELLOW = PALETTE[:5]

DEPARTMENT_EMOJI = {
    'produce': '🥦', 'dairy eggs': '🥚', 'snacks': '🍿', 'beverages': '🥤', 'frozen': '🧊', 'pantry': '🧂',
    'bakery': '🥖', 'canned goods': '🥫', 'deli': '🥪', 'dry goods pasta': '🍝', 'household': '🧽',
    'meat seafood': '🥩', 'breakfast': '🥣', 'personal care': '🧴', 'babies': '🍼', 'international': '🌮',
    'alcohol': '🍷', 'pets': '🐾', 'missing': '❓', 'other': '📦', 'bulk': '🌾',
}
DEPARTMENT_COLOR = {d: PALETTE[i % len(PALETTE)] for i, d in enumerate(DEPARTMENT_EMOJI)}

# Keyword -> emoji, checked in order, so specific words come before general ones.
PRODUCT_EMOJI = [
    ('watermelon', '🍉'), ('pineapple', '🍍'), ('banana', '🍌'), ('strawberr', '🍓'), ('blueberr', '🫐'),
    ('raspberr', '🫐'), ('blackberr', '🫐'), ('avocado', '🥑'), ('lemon', '🍋'), ('lime', '🍋'), ('apple', '🍎'),
    ('grape', '🍇'), ('orange', '🍊'), ('clementine', '🍊'), ('mandarin', '🍊'), ('peach', '🍑'), ('pear', '🍐'),
    ('cherr', '🍒'), ('melon', '🍈'), ('mango', '🥭'), ('coconut', '🥥'), ('kiwi', '🥝'), ('tomato', '🍅'),
    ('potato', '🥔'), ('onion', '🧅'), ('garlic', '🧄'), ('carrot', '🥕'), ('cucumber', '🥒'), ('pepper', '🫑'),
    ('corn', '🌽'), ('mushroom', '🍄'), ('broccoli', '🥦'), ('spinach', '🥬'), ('lettuce', '🥬'), ('kale', '🥬'),
    ('romaine', '🥬'), ('cilantro', '🌿'), ('parsley', '🌿'), ('basil', '🌿'), ('zucchini', '🥒'), ('ginger', '🫚'),
    ('chocolate', '🍫'), ('cookie', '🍪'), ('ice cream', '🍨'), ('chips', '🥔'), ('popcorn', '🍿'), ('beer', '🍺'),
    ('wine', '🍷'), ('juice', '🧃'), ('sparkling', '🫧'), ('seltzer', '🫧'), ('water', '💧'), ('coffee', '☕'),
    ('tea', '🍵'), ('milk', '🥛'), ('yogurt', '🥛'), ('cheese', '🧀'), ('butter', '🧈'), ('egg', '🥚'),
    ('bread', '🍞'), ('bagel', '🥯'), ('croissant', '🥐'), ('tortilla', '🌮'), ('pancake', '🥞'), ('waffle', '🧇'),
    ('cake', '🍰'), ('muffin', '🧁'), ('rice', '🍚'), ('pasta', '🍝'), ('spaghetti', '🍝'), ('pizza', '🍕'),
    ('honey', '🍯'), ('salt', '🧂'), ('bacon', '🥓'), ('sausage', '🌭'), ('hot dog', '🌭'), ('chicken', '🍗'),
    ('turkey', '🦃'), ('beef', '🥩'), ('steak', '🥩'), ('salmon', '🐟'), ('tuna', '🐟'), ('fish', '🐟'),
    ('shrimp', '🍤'), ('bean', '🫘'), ('hummus', '🫘'), ('almond', '🥜'), ('peanut', '🥜'), ('nut', '🥜'),
    ('oat', '🥣'), ('cereal', '🥣'), ('granola', '🥣'), ('soup', '🍲'), ('broth', '🍲'), ('sauce', '🥫'),
    ('diaper', '🍼'), ('baby', '🍼'), ('dog', '🐶'), ('cat ', '🐱'), ('paper towel', '🧻'), ('toilet', '🧻'),
    ('soap', '🧼'), ('detergent', '🧺'),
]


def product_emoji(name, department=None):
    lowered = f' {str(name).lower()} '
    for word, emoji in PRODUCT_EMOJI:
        if word in lowered: return emoji
    return DEPARTMENT_EMOJI.get(department, '🛒')


def dept_emoji(department):
    return DEPARTMENT_EMOJI.get(department, '🛒')


def setup_charts():
    template = pio.templates['plotly_white']
    template.layout.colorway = PALETTE
    template.layout.font = dict(family='Plus Jakarta Sans, sans-serif', color='#1E2A22', size=13)
    template.layout.title = dict(font=dict(family='Bricolage Grotesque, sans-serif', size=18), x=0, xanchor='left')
    template.layout.paper_bgcolor = 'rgba(0,0,0,0)'
    template.layout.plot_bgcolor = 'rgba(0,0,0,0)'
    template.layout.xaxis.gridcolor = template.layout.yaxis.gridcolor = '#E7EDE2'
    template.layout.hoverlabel = dict(bgcolor='white', font=dict(family='Plus Jakarta Sans'))
    template.layout.margin = dict(t=50, b=30, l=10, r=10)
    pio.templates['insta'] = template
    px.defaults.template = 'insta'
    px.defaults.color_discrete_sequence = PALETTE


CSS = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
.stApp { font-family: 'Plus Jakarta Sans', sans-serif; }
h1, h2, h3, h4 { font-family: 'Bricolage Grotesque', sans-serif !important; letter-spacing: -0.02em; }
.block-container { max-width: 1260px; margin: 0 auto; padding-top: 3.6rem; padding-bottom: 4rem; }
.stButton button, .stDownloadButton button, [data-testid="stPageLink"] a { border-radius: 999px !important; font-weight: 600; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { background: #EEF4EA; border-radius: 999px; padding: 8px 18px; font-weight: 600; }
.stTabs [aria-selected="true"] { background: #0F9D58; color: white !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

.hero { position: relative; overflow: hidden; border-radius: 28px; padding: 46px 48px; color: white;
  background: radial-gradient(circle at 85% 20%, rgba(255,255,255,.18) 0 120px, transparent 121px),
              linear-gradient(120deg, #0B7D46 0%, #0F9D58 38%, #3DBB6E 62%, #FFB547 100%);
  box-shadow: 0 18px 40px rgba(15,157,88,.25); margin-bottom: 22px; }
.hero h1 { color: white !important; font-size: 3rem; line-height: 1.05; margin: 0 0 12px 0; max-width: 640px; }
.hero p { font-size: 1.12rem; opacity: .95; max-width: 600px; margin: 0; }
.hero .chips { margin-top: 20px; display: flex; gap: 8px; flex-wrap: wrap; }
.hero .chip { background: rgba(255,255,255,.2); border: 1px solid rgba(255,255,255,.35); border-radius: 999px;
  padding: 6px 14px; font-size: .88rem; font-weight: 600; }
.hero .art { position: absolute; right: 36px; top: 50%; transform: translateY(-50%); display: grid;
  grid-template-columns: repeat(4, 74px); gap: 10px; }
.hero .art span { font-size: 42px; width: 74px; height: 74px; display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,.22); border-radius: 22px; backdrop-filter: blur(4px); }
.hero .art span:nth-child(odd) { transform: rotate(-6deg); } .hero .art span:nth-child(even) { transform: rotate(5deg); }
@media (max-width: 1000px) { .hero .art { display: none; } .hero h1 { font-size: 2.2rem; } .hero { padding: 32px 26px; } }

.page-head { display: flex; align-items: center; gap: 16px; margin: 4px 0 18px 0; }
.page-head .icon { font-size: 34px; width: 64px; height: 64px; border-radius: 20px; display: flex;
  align-items: center; justify-content: center; }
.page-head h2 { margin: 0; padding: 0; font-size: 2rem; }
.page-head p { margin: 2px 0 0 0; color: #5B6B60; }

.kpi { background: white; border: 1px solid #E5EBE0; border-radius: 22px; padding: 18px 20px;
  box-shadow: 0 6px 18px rgba(30,42,34,.05); height: 100%; }
.kpi .top { display: flex; align-items: center; gap: 10px; white-space: nowrap; color: #5B6B60; font-weight: 600; font-size: .9rem; }
.kpi .ico { width: 38px; height: 38px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.kpi { overflow: hidden; }
.kpi .val { font-family: 'Bricolage Grotesque', sans-serif; font-size: clamp(1.25rem, 1.75vw, 2rem); white-space: nowrap; font-weight: 800; margin-top: 8px; color: #1E2A22;
  overflow: hidden; text-overflow: ellipsis; }
.kpi .val.long { font-size: clamp(1rem, 1.25vw, 1.3rem); white-space: normal; line-height: 1.25; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.hero .brand { display: inline-flex; align-items: center; gap: 8px; background: rgba(255,255,255,.22); border: 1px solid rgba(255,255,255,.4);
  border-radius: 999px; padding: 6px 16px; font-weight: 700; font-size: .95rem; letter-spacing: .02em; margin-bottom: 16px; }
.gcard { background: white; border: 1px solid #E5EBE0; border-radius: 22px; padding: 18px 20px 12px 20px; min-height: 175px;
  box-shadow: 0 6px 18px rgba(30,42,34,.05); transition: transform .15s ease, box-shadow .15s ease; }
.gcard:hover { transform: translateY(-3px); box-shadow: 0 14px 28px rgba(30,42,34,.10); }
.gcard .emoji { font-size: 34px; }
.gcard h4 { margin: 8px 0 4px 0; font-size: 1.08rem; }
.gcard p { color: #5B6B60; margin: 0; font-size: .9rem; }
.gcard .tag { display: inline-block; margin-top: 10px; font-size: .75rem; font-weight: 700; border-radius: 999px; padding: 3px 10px; }
.answer { border-radius: 24px; padding: 24px 28px; color: white; margin: 6px 0 16px 0;
  background: linear-gradient(120deg, #2F4BD0, #4C6EF5 60%, #7C9BFF); box-shadow: 0 14px 30px rgba(76,110,245,.25); }
.answer .k { text-transform: uppercase; letter-spacing: .08em; font-size: .8rem; font-weight: 700; opacity: .85; }
.answer .a { font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.7rem; font-weight: 800; line-height: 1.2; margin: 6px 0; }
.answer .d { opacity: .92; font-size: .98rem; }
.kpi .sub { color: #7A897F; font-size: .82rem; }

.card { background: white; border: 1px solid #E5EBE0; border-radius: 22px; padding: 20px 22px;
  box-shadow: 0 6px 18px rgba(30,42,34,.05); height: 100%; }
.card h4 { margin: 8px 0 6px 0; font-size: 1.15rem; }
.card p { color: #5B6B60; margin: 0; font-size: .93rem; }
.card .emoji { font-size: 34px; }

.tile { border-radius: 22px; padding: 16px 16px 14px 16px; color: #1E2A22; min-height: 150px;
  border: 1px solid rgba(0,0,0,.04); transition: transform .15s ease, box-shadow .15s ease; }
.tile:hover { transform: translateY(-3px); box-shadow: 0 12px 26px rgba(30,42,34,.10); }
.tile .emoji { font-size: 40px; line-height: 1; }
.tile .name { font-weight: 700; text-transform: capitalize; margin-top: 8px; font-size: 1rem; }
.tile .stat { font-size: .82rem; color: #4A5A50; margin-top: 2px; }
.tile .bar { height: 6px; border-radius: 6px; background: rgba(0,0,0,.08); margin-top: 10px; overflow: hidden; }
.tile .bar div { height: 100%; border-radius: 6px; }

.insight { border-radius: 18px; padding: 14px 18px; background: #FFF3E6; border: 1px solid #FFD9B5;
  margin: 6px 0 14px 0; font-size: .97rem; }
.insight b { color: #B24D00; }
.note { color: #6C7B71; font-size: .85rem; }
.section-title { display: flex; align-items: center; gap: 10px; margin: 26px 0 6px 0; }
.section-title h3 { margin: 0; padding: 0; }
.section-title span.emoji { font-size: 26px; }
.sowhat { border-radius: 18px; padding: 14px 18px; background: #EAF0FF; border: 1px solid #C9D6FF;
  margin: 6px 0 14px 0; font-size: .97rem; }
.sowhat b { color: #2F4BD0; }
.badge { display: inline-block; background: white; border: 1px solid #E5EBE0; border-radius: 999px; padding: 6px 14px;
  margin: 4px 6px 4px 0; font-weight: 600; font-size: .88rem; }
.pipe { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 10px 0; }
.pipe .step { background: white; border: 1px solid #E5EBE0; border-radius: 14px; padding: 10px 14px; font-weight: 600;
  font-size: .9rem; box-shadow: 0 4px 12px rgba(30,42,34,.04); }
.pipe .arrow { color: #9AA89F; font-size: 1.2rem; }
.reveal { border-radius: 24px; padding: 22px 22px 16px 22px; color: white; min-height: 190px; position: relative; overflow: hidden; }
.reveal .num { position: absolute; right: 16px; top: 6px; font-family: 'Bricolage Grotesque', sans-serif; font-size: 4.2rem;
  font-weight: 800; opacity: .18; }
.reveal .emoji { font-size: 40px; }
.reveal h4 { color: white !important; margin: 10px 0 6px 0; font-size: 1.2rem; line-height: 1.25; }
.reveal p { margin: 0; opacity: .95; font-size: .92rem; }
.story-kicker { text-transform: uppercase; letter-spacing: .08em; font-size: .8rem; font-weight: 700; color: #0F9D58; margin-top: 4px; }
.story-title { font-family: 'Bricolage Grotesque', sans-serif; font-size: 2.1rem; font-weight: 800; line-height: 1.15; margin: 4px 0 6px 0; }
.story-sub { color: #5B6B60; font-size: 1.05rem; margin-bottom: 8px; }
.stTextArea textarea { font-family: ui-monospace, Consolas, "Cascadia Code", monospace !important; font-size: .88rem; }
.footer { text-align: center; color: #8A978E; font-size: .85rem; margin-top: 40px; }
</style>
'''


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text):
    return html.escape(str(text))


def hero(title, subtitle, chips=(), art=(), brand=None):
    chip_html = ''.join(f'<span class="chip">{esc(c)}</span>' for c in chips)
    art_html = ''.join(f'<span>{a}</span>' for a in art)
    brand_html = f'<div class="brand">{esc(brand)}</div>' if brand else ''
    st.markdown(f'''<div class="hero">{brand_html}<h1>{esc(title)}</h1><p>{esc(subtitle)}</p>
        <div class="chips">{chip_html}</div><div class="art">{art_html}</div></div>''', unsafe_allow_html=True)


def page_header(icon, title, subtitle, color=GREEN):
    st.markdown(f'''<div class="page-head"><div class="icon" style="background:{color}22">{icon}</div>
        <div><h2>{esc(title)}</h2><p>{esc(subtitle)}</p></div></div>''', unsafe_allow_html=True)


def kpi(icon, label, value, sub='', color=GREEN):
    long = ' long' if len(str(value)) > 14 else ''          # long text wraps at a smaller size instead of spilling out
    st.markdown(f'''<div class="kpi"><div class="top"><div class="ico" style="background:{color}22">{icon}</div>{esc(label)}</div>
        <div class="val{long}" title="{esc(value)}">{esc(value)}</div><div class="sub">{esc(sub)}</div></div>''', unsafe_allow_html=True)


def gallery(items, state_key, columns=3):
    '''Card grid; clicking a card's button stores its key in session state so the page can open that item.'''
    cols = st.columns(columns)
    for i, (key, emoji, title, text, tag, color) in enumerate(items):
        with cols[i % columns]:
            st.markdown(f'''<div class="gcard"><div class="emoji">{emoji}</div><h4>{esc(title)}</h4><p>{esc(text)}</p>
                <span class="tag" style="background:{color}1F;color:{color}">{esc(tag)}</span></div>''', unsafe_allow_html=True)
            st.button('Open →', key=f'{state_key}_{key}', on_click=lambda k=key: st.session_state.update({state_key: k}), width='stretch')
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)


def back_button(state_key, label='← Back to all'):
    st.button(label, key=f'{state_key}_back', on_click=lambda: st.session_state.update({state_key: None}))


def answer(kicker, headline, detail=''):
    st.markdown(f'<div class="answer"><div class="k">{esc(kicker)}</div><div class="a">{esc(headline)}</div>'
                f'<div class="d">{detail}</div></div>', unsafe_allow_html=True)


def card(emoji, title, text):
    st.markdown(f'''<div class="card"><div class="emoji">{emoji}</div><h4>{esc(title)}</h4><p>{esc(text)}</p></div>''',
                unsafe_allow_html=True)


def tile(emoji, name, stat, share, color):
    st.markdown(f'''<div class="tile" style="background:linear-gradient(160deg,{color}26,{color}0D)">
        <div class="emoji">{emoji}</div><div class="name">{esc(name)}</div><div class="stat">{esc(stat)}</div>
        <div class="bar"><div style="width:{max(3, min(100, share)):.0f}%;background:{color}"></div></div></div>''',
                unsafe_allow_html=True)


def insight(text_html):
    '''Callout for a key takeaway. Caller builds the HTML from escaped values.'''
    st.markdown(f'<div class="insight">💡 {text_html}</div>', unsafe_allow_html=True)


def so_what(text_html):
    '''Recommendation callout: what a business should do with the insight.'''
    st.markdown(f'<div class="sowhat">🎯 <b>So what?</b> {text_html}</div>', unsafe_allow_html=True)


def reveal(n, emoji, title, text, color):
    st.markdown(f'''<div class="reveal" style="background:linear-gradient(150deg,{color},{color}C0)"><div class="num">{n}</div>
        <div class="emoji">{emoji}</div><h4>{esc(title)}</h4><p>{esc(text)}</p></div>''', unsafe_allow_html=True)


def story_header(kicker, title, subtitle):
    st.markdown(f'<div class="story-kicker">{esc(kicker)}</div><div class="story-title">{esc(title)}</div>'
                f'<div class="story-sub">{esc(subtitle)}</div>', unsafe_allow_html=True)


def badges(items):
    st.markdown(''.join(f'<span class="badge">{esc(i)}</span>' for i in items), unsafe_allow_html=True)


def pipeline(steps):
    parts = '<span class="arrow">→</span>'.join(f'<span class="step">{esc(s)}</span>' for s in steps)
    st.markdown(f'<div class="pipe">{parts}</div>', unsafe_allow_html=True)


def section(emoji, title):
    st.markdown(f'<div class="section-title"><span class="emoji">{emoji}</span><h3>{esc(title)}</h3></div>',
                unsafe_allow_html=True)


def chart(fig, height=420):
    fig.update_layout(height=height)
    if any(getattr(t, 'orientation', None) == 'h' for t in fig.data) and fig.layout.yaxis.categoryorder is None:
        fig.update_yaxes(categoryorder='total ascending')
    st.plotly_chart(fig, width='stretch', config={'displaylogo': False})


def show_sql(sql):
    with st.expander('🧾 See the SQL behind this'):
        st.code(sql.strip(), language='sql')


def download(frame, name, label='⬇️ Download CSV'):
    st.download_button(label, frame.to_csv(index=False).encode(), name, mime='text/csv', key=f'dl_{name}')


def footer():
    st.markdown('<div class="footer">Built with PostgreSQL · Python · Streamlit · Plotly</div>', unsafe_allow_html=True)
