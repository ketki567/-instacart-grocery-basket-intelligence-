'''Ask the data: plain-English question builder (governed SQL) and a read-only SQL Lab for analysts.'''
import plotly.express as px
import streamlit as st
from src import sql_lab, ui
from src.sql_examples import EXAMPLES
from src.analytics import raw, run, DAY_NAMES, hour_label
from src.llm import explain, installed, route
from src.query import MEASURES, Spec, compile_query, interpret_question

DIMENSION_LABELS = {'department': '🏬 Department', 'aisle': '🛤️ Aisle', 'product': '🏷️ Product',
                    'hour': '⏰ Hour of day', 'day': '📅 Day of week', 'order_number': '🔢 Order number'}
MEASURE_LABELS = {'items': '🛒 Items bought', 'orders': '🧾 Orders', 'customers': '👥 Shoppers',
                  'reorder_rate': '🔁 Reorder rate %', 'avg_cart_position': '📍 Avg cart position'}

# Combinations of department × time window × measure that the Insights stories don't cover.
COMBOS = [
    ('Late night snack favourites (8 pm to midnight)', Spec('product', 'items', department='snacks', hour_start=20, hour_end=23)),
    ('Early morning beverages (5 to 8 am)', Spec('product', 'items', department='beverages', hour_start=5, hour_end=8, min_items=20)),
    ('Least reordered aisles in frozen', Spec('aisle', 'reorder_rate', department='frozen', descending=False)),
    ('Which pantry aisles reach the most shoppers?', Spec('aisle', 'customers', department='pantry')),
    ('Most loyal personal care products', Spec('product', 'reorder_rate', department='personal care', min_items=200)),
    ('When do people buy alcohol?', Spec('hour', 'items', department='alcohol', min_items=0, limit=24, descending=None)),
    ('Which departments go into the cart first?', Spec('department', 'avg_cart_position', descending=False)),
    ('Baby products: what do parents buy most?', Spec('product', 'items', department='babies')),
    ('Busiest days for the deli', Spec('day', 'orders', department='deli', min_items=0, limit=7, descending=None)),
    ('Lunchtime (11 am to 2 pm) top products', Spec('product', 'items', hour_start=11, hour_end=14)),
]


def _set_question(text, spec, warning=None):
    # A fresh version number gives the filter widgets new keys, so they show this question's settings.
    version = st.session_state.get('ask', {}).get('version', 0) + 1
    st.session_state['ask'] = {'question': text, 'spec': Spec(**vars(spec)) if spec else None, 'warning': warning, 'version': version}


MEASURE_WORDS = {'items': ('times bought', 'most bought', 'least bought'), 'orders': ('orders', 'most orders', 'fewest orders'),
                 'customers': ('shoppers', 'most shoppers', 'fewest shoppers'),
                 'reorder_rate': ('% reordered', 'most reordered', 'least reordered'),
                 'avg_cart_position': ('average cart position', 'added to the cart latest', 'added to the cart earliest')}
DIM_WORDS = {'department': 'department', 'aisle': 'aisle', 'product': 'product', 'hour': 'hour', 'day': 'day', 'order_number': 'order number'}


def _question_box():
    st.markdown('<div class="story-title" style="font-size:1.6rem;margin-top:4px">What do you want to know?</div>', unsafe_allow_html=True)
    with st.form('ask_form', clear_on_submit=False, border=False):
        c1, c2 = st.columns([5, 1], vertical_alignment='bottom')
        with c1: text = st.text_input('Your question', placeholder='e.g. Which aisles have the highest reorder rate?', label_visibility='collapsed')
        with c2: go = st.form_submit_button('Ask ✨', type='primary', width='stretch')
    if go and text.strip():
        spec, warning = route(text) if installed() else interpret_question(text)
        _set_question(text.strip(), spec, warning)
    st.markdown('<p class="note" style="margin-bottom:4px">Or try one of these:</p>', unsafe_allow_html=True)
    with st.container(horizontal=True):
        for i, (text, spec) in enumerate(COMBOS[:6]):
            st.button(text, key=f'combo_{i}', on_click=_set_question, args=(text, spec))


def _controls(spec, v):
    st.caption('Every change reruns the question instantly.')
    spec.dimension = st.pills('Group by', list(DIMENSION_LABELS), default=spec.dimension,
                              format_func=DIMENSION_LABELS.get, key=f'ask_dim_{v}') or spec.dimension
    spec.measure = st.pills('Measure', list(MEASURE_LABELS), default=spec.measure,
                            format_func=MEASURE_LABELS.get, key=f'ask_measure_{v}') or spec.measure
    depts = ['All'] + run('departments')['department'].tolist()
    a, b = st.columns(2)
    with a:
        spec.department = st.selectbox('Department', depts, index=depts.index(spec.department) if spec.department in depts else 0,
                                       format_func=lambda x: x if x == 'All' else f'{ui.dept_emoji(x)} {x}', key=f'ask_dept_{v}')
    with b:
        spec.hour_start, spec.hour_end = st.select_slider('Hours of the day', options=list(range(24)),
                                                          value=(spec.hour_start, spec.hour_end), format_func=hour_label, key=f'ask_hours_{v}')
    c, d, e = st.columns(3)
    with c:
        order_options = ['Highest first', 'Lowest first', 'Natural order']
        current = 'Natural order' if spec.descending is None else ('Highest first' if spec.descending else 'Lowest first')
        choice = st.segmented_control('Sort', order_options, default=current, key=f'ask_sort_{v}') or current
        spec.descending = None if choice == 'Natural order' else choice == 'Highest first'
    with d:
        spec.limit = st.slider('Rows to show', 5, 50 if spec.dimension not in ('hour', 'day', 'order_number') else 100,
                               min(int(spec.limit), 50), key=f'ask_limit_{v}')
    with e:
        spec.min_items = st.number_input('Skip groups with fewer items than', 0, 1_000_000, int(spec.min_items), step=100, key=f'ask_min_{v}')
    return spec


@st.cache_data(show_spinner='Querying PostgreSQL…')
def _execute(spec_items):
    spec = Spec(**dict(spec_items))
    natural = spec.descending is None
    if natural: spec.descending = True
    sql, params = compile_query(spec)
    if natural:
        sql = sql.replace('ORDER BY metric DESC NULLS LAST', 'ORDER BY 1')
    return raw(sql, params), sql, params


def _pretty(df, dimension):
    out = df.copy()
    key = out.columns[0]
    if dimension == 'hour': out[key] = [hour_label(h) for h in out[key]]
    elif dimension == 'day': out[key] = [DAY_NAMES[int(v)] for v in out[key]]
    elif dimension == 'order_number': out[key] = [f'#{int(v)}' for v in out[key]]
    elif dimension == 'product': out[key] = [f'{ui.product_emoji(v)} {v}' for v in out[key]]
    elif dimension == 'department': out[key] = [f'{ui.dept_emoji(v)} {v}' for v in out[key]]
    return out


def _fmt(v):
    return f'{float(v):,.2f}'.rstrip('0').rstrip('.')


def _plain_english():
    _question_box()
    state = st.session_state.get('ask')
    if not state:
        _set_question(*COMBOS[0])
        state = st.session_state['ask']
    st.markdown(f'### ❓ {ui.esc(state["question"])}')
    if state['warning']:
        st.warning(f'🙅 {state["warning"]} Try one of the suggested questions instead.')
        return
    answer_box, chart_box = st.container(), st.container()      # filled after the filters below are read
    with st.expander('🎛️ Adjust the question (group by, measure, department, hours, sort)'):
        spec = _controls(Spec(**vars(state['spec'])), state['version'])
    df, sql, params = _execute(tuple(sorted(vars(spec).items(), key=lambda kv: kv[0])))
    if df.empty:
        answer_box.warning('No rows matched. Open “Adjust the question” and lower the minimum or widen the hours.')
        return
    shown = _pretty(df, spec.dimension)
    key = shown.columns[0]
    unit, most, least = MEASURE_WORDS[spec.measure]
    measure_name = MEASURE_LABELS[spec.measure][2:]
    lowest = spec.descending is False
    best = shown.sort_values('metric', ascending=lowest).iloc[0]
    scope = [f'in {spec.department}' if spec.department != 'All' else 'across all departments']
    if (spec.hour_start, spec.hour_end) != (0, 23):
        scope.append(f'between {hour_label(spec.hour_start)} and {hour_label((spec.hour_end + 1) % 24)}')
    with answer_box:
        ui.answer(f'{"Lowest" if lowest else "Top"} {DIM_WORDS[spec.dimension]} · {least if lowest else most}', str(best[key]),
                  f'<b>{_fmt(best["metric"])}</b> {ui.esc(unit)} {ui.esc(" ".join(scope))}. '
                  f'Based on {int(df["supporting_items"].sum()):,} purchase lines.')
    with chart_box:
        if spec.dimension in ('hour', 'day', 'order_number') and spec.descending is None:
            fig = px.area(shown, x=key, y='metric', markers=True, labels={'metric': measure_name, key: ''})
            fig.update_traces(line=dict(color=ui.BLUE, width=3), fillcolor='rgba(76,110,245,.12)', marker=dict(size=8, color=ui.ORANGE))
            ui.chart(fig, height=400)
        else:
            show = shown.head(15)
            fig = px.bar(show, x='metric', y=key, orientation='h', text='metric', labels={'metric': measure_name, key: ''})
            fig.update_traces(marker_color=[ui.ORANGE if i == 0 else '#9DB8F2' for i in range(len(show))],
                              texttemplate='%{text:,.4~g}', textposition='outside', cliponaxis=False)
            fig.update_layout(xaxis=dict(showgrid=False, showticklabels=False, range=[0, show['metric'].max() * 1.15]), font=dict(size=13))
            fig.update_yaxes(categoryorder='array', categoryarray=show[key].tolist()[::-1])
            ui.chart(fig, height=max(320, 30 * len(show) + 60))
            if len(shown) > 15: st.caption(f'Showing the first 15 of {len(shown)} rows. See all of them in the table below.')
        if installed():
            ui.insight(ui.esc(explain(state['question'], shown, MEASURES[spec.measure][1])))
    with st.expander('📋 See the table'):
        st.dataframe(shown.rename(columns={'metric': measure_name, 'supporting_items': 'Purchase lines'}), hide_index=True, width='stretch')
        ui.download(df, 'question_results.csv')
    with st.expander('🧾 See the SQL'):
        st.code(sql.strip(), language='sql')
        st.caption(f'Bound parameters: {params}. Grouping and measure come from a fixed list and every value is a parameter, '
                   f'so no free text SQL is ever executed.')


def _load_example(name):
    st.session_state['lab_sql'] = EXAMPLES[name]
    st.session_state['lab_example'] = name
    st.session_state.pop('lab_result', None)


def _run_lab():
    try:
        df, elapsed, truncated = sql_lab.execute(st.session_state.get('lab_sql', ''))
        st.session_state['lab_result'] = {'df': df, 'elapsed': elapsed, 'truncated': truncated, 'error': None}
    except Exception as exc:
        st.session_state['lab_result'] = {'error': str(exc).split('\n')[0]}


def _auto_chart(df):
    numeric = [c for c in df.columns if str(df[c].dtype).startswith(('int', 'float'))]
    if len(df) < 2 or not numeric or len(df.columns) < 2: return
    with st.container(border=True):
        st.markdown('**📈 Chart the result**')
        c1, c2, c3 = st.columns(3)
        with c1: x = st.selectbox('X axis', list(df.columns), index=0, key='lab_x')
        y_options = [c for c in numeric if c != x] or numeric
        with c2: y = st.selectbox('Y axis', y_options, index=len(y_options) - 1, key='lab_y')
        others = [c for c in df.columns if c not in (x, y) and c not in numeric]
        kinds = ['Bar', 'Line', 'Heatmap'] if others else ['Bar', 'Line']
        default = 'Line' if x in numeric else 'Bar'
        with c3: kind = st.segmented_control('Chart type', kinds, default=default, key='lab_kind') or default
        color = others[0] if others and kind != 'Heatmap' else None
        if kind == 'Heatmap':
            grid = df.pivot_table(index=others[0], columns=x, values=y, aggfunc='sum')
            fig = px.imshow(grid, aspect='auto', color_continuous_scale=['#F4FAF1', ui.GREEN])
        elif kind == 'Line':
            fig = px.line(df, x=x, y=y, color=color, markers=True)
        else:
            fig = px.bar(df.head(60), x=x, y=y, color=color)
        ui.chart(fig, height=420)


def _sql_lab():
    st.markdown('A read only SQL editor on the real PostgreSQL database. Load an advanced example, edit it, or write your own.')
    left, right = st.columns([1, 2.2])
    with left:
        with st.container(border=True):
            st.markdown('**🧠 Advanced examples**')
            for name in EXAMPLES:
                st.button(name, key=f'ex_{name}', on_click=_load_example, args=(name,), width='stretch',
                          type='primary' if st.session_state.get('lab_example') == name else 'secondary')
        with st.expander('🗂️ Tables and columns'):
            sch = raw('''SELECT table_name, column_name, data_type FROM information_schema.columns
                         WHERE table_schema = 'public' ORDER BY table_name, ordinal_position''')
            table = st.selectbox('Table', sch['table_name'].unique().tolist(), key='lab_table')
            st.dataframe(sch[sch['table_name'] == table][['column_name', 'data_type']], hide_index=True, width='stretch')
    with right:
        st.session_state.setdefault('lab_sql', EXAMPLES[list(EXAMPLES)[0]])
        st.text_area('SQL', key='lab_sql', height=340, label_visibility='collapsed')
        c1, c2 = st.columns([1, 3], vertical_alignment='center')
        with c1: st.button('▶ Run query', type='primary', on_click=_run_lab, width='stretch', key='lab_run')
        with c2: st.caption(f'Safe mode: one SELECT or WITH statement · read only · {sql_lab.TIMEOUT_MS // 1000}s limit · '
                            f'first {sql_lab.MAX_ROWS:,} rows.')
    res = st.session_state.get('lab_result')
    if not res: return
    if res['error']:
        st.error(f'🚫 {res["error"]}')
        return
    df = res['df']
    k1, k2, k3 = st.columns(3)
    with k1: ui.kpi('📏', 'Rows', f'{len(df):,}{"+" if res["truncated"] else ""}', 'Capped at 1,000' if res['truncated'] else 'Returned', ui.BLUE)
    with k2: ui.kpi('🧱', 'Columns', f'{len(df.columns)}', ', '.join(map(str, df.columns[:3])) + ('…' if len(df.columns) > 3 else ''), ui.GREEN)
    with k3: ui.kpi('⏱️', 'Run time', f'{res["elapsed"] * 1000:,.0f} ms', 'On PostgreSQL', ui.ORANGE)
    st.markdown(' ')
    st.dataframe(df, hide_index=True, width='stretch', height=min(420, 38 + 35 * len(df)))
    ui.download(df, 'sql_lab_result.csv')
    _auto_chart(df)


def render():
    ui.page_header('💬', 'Ask the data', 'Plain English questions for everyone, and a SQL Lab for analysts.', ui.BLUE)
    plain, lab = st.tabs(['💬 Ask a question', '🧑‍💻 SQL Lab (for analysts)'])
    with plain: _plain_english()
    with lab: _sql_lab()
    ui.footer()
