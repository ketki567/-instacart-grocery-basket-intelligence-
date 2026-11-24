'''Advanced analytics: lifecycle and pace cohorts, customer segmentation, a reorder prediction model, and experiment design.'''
from statistics import NormalDist
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src import ui
from src.analytics import raw, run
from src.marts import MARTS


def _info():
    return raw('SELECT key, value FROM ml_reorder_info').set_index('key')['value']


# ---------------------------------------------------------------- cohorts

def cohorts():
    ui.story_header('Cohort analysis', 'Customers change as they stay',
                    'Orders grouped by where they fall in the customer’s lifetime (1st order, orders 2 to 3, and so on).')
    st.info('This sample holds a few scattered orders per customer, so calendar cohorts (by signup month) are not possible. '
            'Instead, cohorts use two fields that stay true even when orders are missing: the order’s position in the '
            'customer’s lifetime, and the real number of days since their previous order.', icon='ℹ️')
    life = raw('SELECT * FROM mart_lifecycle ORDER BY stage_sort')
    org = raw('SELECT stage, organic_share FROM mart_lifecycle_organic')
    life = life.merge(org, on='stage')
    c1, c2, c3, c4 = st.columns(4)
    first, late = life.iloc[1], life.iloc[-1]
    with c1: ui.kpi('🔁', 'Reorder rate', f"{first['reorder_pct']:.0f}% → {late['reorder_pct']:.0f}%", 'Orders 2 to 3 vs 51 to 100', ui.GREEN)
    with c2: ui.kpi('📅', 'Days between orders', f"{first['avg_days_between']:.0f} → {late['avg_days_between']:.0f}", 'Shrinks as habits form', ui.BLUE)
    with c3: ui.kpi('🌱', 'Organic share', f"{life.iloc[0]['organic_share']:.0f}% → {late['organic_share']:.0f}%", 'Grows with tenure', ui.PINK)
    with c4: ui.kpi('🧺', 'Basket size', f"{life.iloc[0]['avg_basket']:.1f} → {late['avg_basket']:.1f}", 'Stays flat', ui.ORANGE)
    st.markdown(' ')
    fig = go.Figure()
    fig.add_bar(x=life['stage'], y=life['avg_days_between'], name='Days between orders', marker_color='#C9D6FF', yaxis='y2')
    fig.add_scatter(x=life['stage'], y=life['reorder_pct'], name='Reorder rate %', mode='lines+markers', line=dict(color=ui.GREEN, width=4))
    fig.add_scatter(x=life['stage'], y=life['organic_share'], name='Organic share %', mode='lines+markers', line=dict(color=ui.PINK, width=3, dash='dot'))
    fig.update_layout(title='Lifecycle cohorts', yaxis=dict(title='%'), yaxis2=dict(title='Days', overlaying='y', side='right', showgrid=False),
                      legend=dict(orientation='h', y=-0.18), font=dict(size=13))
    ui.chart(fig, height=440)
    ui.insight(f"Between the early orders and orders 51 to 100, the reorder rate climbs from <b>{first['reorder_pct']:.0f}%</b> to "
               f"<b>{late['reorder_pct']:.0f}%</b> and the gap between orders shrinks from <b>{first['avg_days_between']:.0f}</b> to "
               f"<b>{late['avg_days_between']:.0f}</b> days, while basket size barely moves. Long term customers do not buy more per trip, "
               f"they come back more often and buy the same things. Part of this is survivorship: slower customers drop out before order 50.")
    ui.so_what('Growth comes from frequency, not bigger baskets. Invest in getting customers from order 3 to order 10 (reminders, '
               'saved lists, subscriptions) rather than in basket size promotions.')

    ui.section('🧭', 'Pace cohorts: weekly vs monthly shoppers')
    pace = raw('SELECT * FROM mart_pace_cohorts WHERE pace <> \'Unknown pace\' ORDER BY pace_sort, stage_sort')
    grid = pace.pivot(index='pace', columns='stage', values='reorder_pct')
    grid = grid.reindex(index=pace.drop_duplicates('pace')['pace'], columns=life['stage'])
    counts = pace.pivot(index='pace', columns='stage', values='customers').reindex_like(grid)
    text = [[f'<b>{v:.0f}%</b><br>{int(n):,} customers' if pd.notna(v) and pd.notna(n) and n >= 50 else ''
             for v, n in zip(rv, rn)] for rv, rn in zip(grid.values, counts.values)]
    shown = grid.where(counts >= 50)
    fig = go.Figure(go.Heatmap(z=shown.values, x=list(grid.columns), y=list(grid.index), text=text, texttemplate='%{text}', textfont=dict(size=13, color='#1E2A22'),
                               colorscale=[[0, '#FFF3E6'], [0.5, '#BFE8CF'], [1, '#0B7D46']], showscale=False,
                               hovertemplate='%{y} · %{x}<br>Reorder rate %{z:.1f}%<extra></extra>'))
    fig.update_layout(title='Reorder rate by shopping pace (rows) and lifecycle stage (columns)', font=dict(size=13))
    fig.update_yaxes(autorange='reversed')
    ui.chart(fig, height=380)
    w = pace[(pace['pace'] == 'Weekly') & (pace['stage_sort'] == 4)]['reorder_pct']
    m = pace[(pace['pace'] == 'Monthly or slower') & (pace['stage_sort'] == 4)]['reorder_pct']
    reach = pace.groupby('pace', sort=False).apply(lambda g: g.loc[g['customers'] >= 50, 'stage'].iloc[-1], include_groups=False)
    ui.insight(f"At the same lifecycle stage (orders 11 to 20), weekly shoppers reorder <b>{w.iloc[0]:.0f}%</b> of items vs "
               f"<b>{m.iloc[0]:.0f}%</b> for monthly shoppers. Monthly shoppers also rarely reach later stages "
               f"(they fade out around <b>{reach.get('Monthly or slower', 'n/a')}</b>). Cells with under 50 customers are hidden.")
    ui.so_what('Pace is an early warning signal. A customer whose gaps stretch from weekly toward monthly is drifting, '
               'and is the right target for a win back message before they disappear.')

    ui.section('⏳', 'Time to next order (survival analysis)')
    days = run('days_between').sort_values('days')
    at_risk = days['orders'][::-1].cumsum()[::-1]
    days['hazard'] = 100 * days['orders'] / at_risk
    days['still_waiting'] = 100 * (at_risk - days['orders']) / days['orders'].sum()
    show = days[days['days'] < 30]
    fig = go.Figure()
    fig.add_bar(x=show['days'], y=show['hazard'], name='Chance of ordering that day (hazard)', marker_color=ui.ORANGE)
    fig.add_scatter(x=show['days'], y=show['still_waiting'], name='Share not yet back (survival)', yaxis='y2', line=dict(color=ui.BLUE, width=3))
    fig.update_layout(title='Hazard and survival of the gap between orders', xaxis_title='Days since previous order',
                      yaxis=dict(title='Hazard %'), yaxis2=dict(title='Survival %', overlaying='y', side='right', showgrid=False),
                      legend=dict(orientation='h', y=-0.2), font=dict(size=13))
    ui.chart(fig, height=420)
    half = int(show[show['still_waiting'] <= 50]['days'].iloc[0])
    ui.insight(f"Half of all repeat orders arrive within <b>{half} days</b>. The hazard spikes every 7 days (weekly routines) and "
               f"then flattens: once a customer passes about 3 weeks, the daily chance of a return keeps dropping. "
               f"Gaps are capped at 30 days by Instacart, so day 30 is left out here.")

    ui.section('📉', 'Department mix by lifecycle stage')
    mix = raw('SELECT stage_sort, stage, department, items FROM mart_lifecycle_department')
    mix['share'] = 100 * mix['items'] / mix.groupby('stage')['items'].transform('sum')
    top = mix.groupby('department')['items'].sum().sort_values(ascending=False).head(10).index
    base = mix[mix['stage_sort'] == 1].set_index('department')['share']
    mix = mix[mix['department'].isin(top)].copy()
    mix['change'] = mix['share'] - mix['department'].map(base)
    g = mix.pivot(index='department', columns='stage', values='change').reindex(index=top, columns=life['stage'])
    fig = px.imshow(g.values, x=list(g.columns), y=[f'{ui.dept_emoji(d)} {d}' for d in g.index], text_auto='+.1f',
                    color_continuous_scale='RdBu', color_continuous_midpoint=0, aspect='auto',
                    labels=dict(color='Points vs 1st order'), title='Change in department share vs the 1st order (percentage points)')
    fig.update_layout(font=dict(size=13), coloraxis_showscale=False)
    ui.chart(fig, height=440)
    gain = g.iloc[:, -1].sort_values()
    ui.insight(f"Compared with first orders, long term customers spend a bigger share on <b>{ui.esc(gain.index[-1])}</b> "
               f"({gain.iloc[-1]:+.1f} points) and less on <b>{ui.esc(gain.index[0])}</b> ({gain.iloc[0]:+.1f} points).")
    ui.show_sql(MARTS['mart_lifecycle'] + '\n\n' + MARTS['mart_pace_cohorts'])


# ---------------------------------------------------------------- segments

ACTIONS = {
    '💚 Loyal regulars': 'Protect them: subscriptions, early access, never let their favourites go out of stock.',
    '🌱 New explorers': 'Onboard them: a second order incentive and a saved shopping list after the first order.',
    '🥬 Fresh and organic': 'Lead with quality: freshness guarantees and organic range expansion.',
    '🍿 Snacks and frozen': 'Bundle deals and multi buy offers on snacks and frozen meals.',
    '🥤 Drinks first': 'Bulk drink packs and cross sell snacks with their usual beverages.',
    '🧽 Household essentials': 'Replenishment reminders timed to how long a pack lasts.',
    '👶 Young families': 'Baby essentials subscriptions and family size bundles.',
    '🍷 Party planners': 'Weekend and evening promotions, pairings with snacks and mixers.',
    '🛒 Everyday mainstream': 'Personalised “buy it again” lists to build habits.',
    '🧺 Big basket shoppers': 'Delivery slot priority and volume based rewards.',
}


def segments():
    ui.story_header('Customer segmentation', 'Eight kinds of shoppers', 'K means clustering on 16 behaviour features for every customer.')
    prof = raw('SELECT * FROM ml_segment_profiles ORDER BY item_share DESC')
    centres = raw('SELECT * FROM ml_segment_centres').set_index('segment')
    from src.ml import SEGMENT_FEATURES
    cols = st.columns(4)
    for i, (_, r) in enumerate(prof.iterrows()):
        z = centres.loc[r['segment']].drop(labels=[c for c in centres.columns if c not in SEGMENT_FEATURES])
        traits = [SEGMENT_FEATURES[f].split(' (')[0] + (' ↑' if z[f] > 0 else ' ↓') for f in z.abs().sort_values(ascending=False).index[:3]]
        color = ui.PALETTE[i % len(ui.PALETTE)]
        with cols[i % 4]:
            st.markdown(f'''<div class="tile" style="background:linear-gradient(160deg,{color}26,#ffffff);min-height:250px">
                <div class="name" style="text-transform:none;font-size:1.1rem">{ui.esc(r['segment'])}</div>
                <div class="stat" style="margin-top:6px"><b>{r['customer_share']:.0f}%</b> of customers · <b>{r['item_share']:.0f}%</b> of items</div>
                <div class="stat">Reorder {r['reorder_pct']:.0f}% · basket {r['avg_basket']:.1f} · every {r['avg_days_between']:.0f} days</div>
                <div class="stat" style="margin-top:6px">{ui.esc(' · '.join(traits))}</div>
                <div class="stat" style="margin-top:8px;color:#2F4BD0">🎯 {ui.esc(ACTIONS.get(r['segment'], ''))}</div></div>''',
                        unsafe_allow_html=True)
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    long = prof.melt(id_vars='segment', value_vars=['customer_share', 'item_share'], var_name='measure', value_name='pct')
    long['measure'] = long['measure'].map({'customer_share': 'Share of customers', 'item_share': 'Share of items bought'})
    fig = px.bar(long, x='pct', y='segment', color='measure', orientation='h', barmode='group', text='pct',
                 color_discrete_map={'Share of customers': '#9DB8F2', 'Share of items bought': ui.GREEN},
                 category_orders={'segment': prof['segment'].tolist()}, labels={'pct': '%', 'segment': '', 'measure': ''},
                 title='Who drives the volume')
    fig.update_traces(texttemplate='%{text:.0f}%', textposition='outside', cliponaxis=False)
    fig.update_layout(font=dict(size=13), legend=dict(orientation='h', y=-0.12), xaxis=dict(range=[0, long['pct'].max() * 1.15]))
    fig.update_yaxes(categoryorder='array', categoryarray=prof['segment'].tolist()[::-1])
    ui.chart(fig, height=520)
    loyal = prof.iloc[0]
    ui.insight(f"<b>{ui.esc(loyal['segment'])}</b> are {loyal['customer_share']:.0f}% of customers but buy <b>{loyal['item_share']:.0f}%</b> "
               f"of all items. Where the green bar is longer than the blue one, a segment buys more than its share.")
    feats = [f for f in SEGMENT_FEATURES if f in centres.columns]
    fig = px.imshow(centres[feats].T.values, x=list(centres.index), y=[SEGMENT_FEATURES[f] for f in feats], color_continuous_scale='RdBu',
                    color_continuous_midpoint=0, zmin=-2, zmax=2, aspect='auto', text_auto='.1f',
                    title='Segment fingerprints (standard deviations from the average customer)')
    fig.update_layout(font=dict(size=12), coloraxis_showscale=False)
    ui.chart(fig, height=620)
    k = raw('SELECT * FROM ml_segment_k ORDER BY k')
    with st.expander('🔬 How the segments were built'):
        st.markdown('- One row per customer with 16 features: frequency, lifetime depth, basket size, pace, reorder rate, '
                    'organic share, department mix and typical order hour.\n'
                    '- Skewed counts are log transformed, then every feature is standardised.\n'
                    '- K from 4 to 8 was compared with the silhouette score on a 20,000 customer sample; the best K was used on all customers.\n'
                    '- Names come from each cluster’s most distinctive features.')
        fig = px.line(k, x='k', y='silhouette', markers=True, title='Silhouette score by number of clusters')
        ui.chart(fig, height=300)
        st.caption(f"Silhouette scores around {k['silhouette'].max():.2f} are typical for behavioural data, where customers sit on a "
                   f"continuum rather than in tight groups. The segments are useful for targeting, not hard boundaries.")
        ui.show_sql(__import__('src.ml', fromlist=['SEGMENT_SQL']).SEGMENT_SQL)


# ---------------------------------------------------------------- reorder model

def reorder_model():
    info = _info()
    metrics = raw('SELECT * FROM ml_reorder_metrics')
    ui.story_header('Machine learning', 'Predicting what each customer will buy again',
                    'For each customer’s latest order: which of the products they bought before will be in it?')
    model_f1 = float(metrics.loc[metrics['approach'].str.startswith('Model'), 'mean_f1'].iloc[0])
    best_base = metrics[~metrics['approach'].str.startswith('Model')].sort_values('mean_f1', ascending=False).iloc[0]
    c = st.columns(4)
    with c[0]: ui.kpi('📈', 'ROC AUC', f"{info['roc_auc']:.3f}", 'Ranking quality (0.5 = random)', ui.GREEN)
    with c[1]: ui.kpi('🎯', 'Mean F1 per customer', f'{model_f1:.3f}', f"vs {best_base['mean_f1']:.3f} best simple rule", ui.BLUE)
    with c[2]: ui.kpi('🚀', 'Improvement', f"+{100 * (model_f1 / best_base['mean_f1'] - 1):.0f}%", f"over “{best_base['approach'].lower()}”", ui.ORANGE)
    with c[3]: ui.kpi('🛒', 'Top 5 hit rate', f"{100 * info['hit_rate_at_5_model']:.0f}%", f"vs {100 * info['hit_rate_at_5_baseline']:.0f}% for most bought", ui.PINK)
    st.markdown(' ')
    ui.insight(f"If Instacart’s shopping app shows a 5 item “Buy it again” list, the model gets <b>{100 * info['hit_rate_at_5_model']:.0f}%</b> of them right "
               f"versus <b>{100 * info['hit_rate_at_5_baseline']:.0f}%</b> for simply showing each customer’s most bought products: "
               f"<b>{100 * (info['hit_rate_at_5_model'] / info['hit_rate_at_5_baseline'] - 1):.0f}% more correct suggestions</b> on the same screen space.")
    long = metrics.melt(id_vars='approach', value_vars=['mean_f1', 'precision', 'recall'], var_name='metric')
    long['metric'] = long['metric'].map({'mean_f1': 'Mean F1', 'precision': 'Precision', 'recall': 'Recall'})
    fig = px.bar(long, x='metric', y='value', color='approach', barmode='group', text='value',
                 color_discrete_sequence=[ui.GREEN, '#9DB8F2', '#FFC48A', '#D6D6D6'], labels={'value': '', 'metric': '', 'approach': ''},
                 title='Model vs simple rules (test customers never seen in training)')
    fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    fig.update_layout(legend=dict(orientation='h', y=-0.15), font=dict(size=13), yaxis=dict(range=[0, 1.1]))
    ui.chart(fig, height=440)

    ui.section('🛒', 'Try it: a customer’s “Buy it again” list')
    ex = raw('SELECT * FROM ml_reorder_examples ORDER BY user_id, rank')
    users = ex['user_id'].drop_duplicates().tolist()
    st.session_state.setdefault('ml_user_idx', 0)
    b1, b2 = st.columns([1, 4], vertical_alignment='center')
    with b1:
        if st.button('🎲 Another customer', width='stretch', key='ml_shuffle'):
            st.session_state['ml_user_idx'] = (st.session_state['ml_user_idx'] + 1) % len(users)
    uid = users[st.session_state['ml_user_idx']]
    rows = ex[ex['user_id'] == uid]
    with b2: st.caption(f"Test customer #{uid} · {int(rows['hist_orders'].iloc[0])} earlier orders seen · "
                        f"{int(rows['label'].sum())} of these 10 were in their next order")
    cols = st.columns(5)
    for i, (_, r) in enumerate(rows.iterrows()):
        hit = bool(r['label'])
        with cols[i % 5]:
            st.markdown(f'''<div class="tile" style="background:{'#E3F6EA' if hit else '#FFFFFF'};min-height:150px;border:1px solid {'#7CCB98' if hit else '#E5EBE0'}">
                <div class="emoji">{ui.product_emoji(r['product_name'], r['department'])}</div>
                <div class="name" style="text-transform:none;font-size:.9rem">#{int(r['rank'])} {ui.esc(r['product_name'])}</div>
                <div class="stat">{100 * r['score']:.0f}% likely · {'✅ bought' if hit else '❌ not bought'}</div>
                <div class="bar"><div style="width:{100 * r['score']:.0f}%;background:{ui.GREEN if hit else '#C9D6C2'}"></div></div></div>''',
                        unsafe_allow_html=True)
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    ui.section('🔍', 'What drives the predictions')
    imp = raw('SELECT * FROM ml_reorder_importance ORDER BY importance DESC').head(10)
    fig = px.bar(imp.iloc[::-1], x='importance', y='meaning', orientation='h', error_x='std',
                 labels={'importance': 'Drop in AUC when the feature is shuffled', 'meaning': ''}, title='Permutation importance (top 10)')
    fig.update_traces(marker_color=ui.BLUE)
    fig.update_layout(font=dict(size=13))
    ui.chart(fig, height=460)
    ui.insight(f"The strongest signals are <b>{ui.esc(imp.iloc[0]['meaning'].lower())}</b> and "
               f"<b>{ui.esc(imp.iloc[1]['meaning'].lower())}</b>: habits and naturally habitual products predict best.")

    curves = raw('SELECT * FROM ml_reorder_curves')
    calib = raw('SELECT * FROM ml_reorder_calibration')
    c1, c2, c3 = st.columns(3)
    with c1:
        r = curves[curves['curve'] == 'roc']
        fig = px.area(r, x='x', y='y', labels={'x': 'False positive rate', 'y': 'True positive rate'}, title=f"ROC curve (AUC {info['roc_auc']:.2f})")
        fig.add_shape(type='line', x0=0, y0=0, x1=1, y1=1, line=dict(dash='dot', color='#B8C4B2'))
        fig.update_traces(line_color=ui.GREEN, fillcolor='rgba(15,157,88,.12)')
        ui.chart(fig, height=330)
    with c2:
        r = curves[curves['curve'] == 'pr']
        fig = px.line(r, x='x', y='y', labels={'x': 'Recall', 'y': 'Precision'}, title=f"Precision vs recall (AP {info['pr_auc']:.2f})")
        fig.add_hline(y=info['base_rate'], line_dash='dot', line_color='#B8C4B2', annotation_text='random')
        fig.update_traces(line_color=ui.ORANGE)
        ui.chart(fig, height=330)
    with c3:
        fig = px.scatter(calib, x='predicted', y='actual', size='rows', labels={'predicted': 'Predicted probability', 'actual': 'Actual rate'},
                         title='Calibration')
        fig.add_shape(type='line', x0=0, y0=0, x1=1, y1=1, line=dict(dash='dot', color='#B8C4B2'))
        fig.update_traces(marker_color=ui.PINK)
        ui.chart(fig, height=330)
    st.caption('Points on the calibration diagonal mean a predicted 30% really happens about 30% of the time, so scores can be used as probabilities.')
    with st.expander('🔬 How the model was built'):
        from src.ml import REORDER_SQL
        st.markdown(f'''
- **Target:** for every customer with at least 2 orders in the data, the latest order is held out. Candidates are the products they bought in earlier orders; the label is whether each one appears in the held out order.
- **Features ({len(raw('SELECT feature FROM ml_reorder_importance'))}):** customer × product habits (how often and how recently), customer habits (pace, basket size, reorder tendency) and product popularity and loyalty, all computed only from earlier orders so nothing leaks from the answer.
- **Split by customer:** {int(info['train_customers']):,} customers for training, a separate validation set to tune the decision threshold ({info['threshold']:.2f}), and {int(info['test_customers']):,} unseen customers for every number on this page.
- **Model:** scikit learn HistGradientBoostingClassifier on {int(info['train_rows']):,} rows, trained in {info['seconds']:.0f} seconds.
- **Metric:** mean F1 per customer, the metric used in Instacart’s original competition, compared against three simple rules.
- **Limit:** only products seen in this sample’s earlier orders can be predicted, so recall is capped by how much history the sample holds.''')
        ui.show_sql(REORDER_SQL)


# ---------------------------------------------------------------- experiment design

def experiment():
    ui.story_header('Experiment design', 'How we would prove a recommendation works',
                    'Every “So what?” in this dashboard is a hypothesis. This is how to test one with an A/B test before rolling it out.')
    days = run('days_between')
    base = 100 * days[days['days'] <= 7]['orders'].sum() / days['orders'].sum()
    st.markdown('**Hypothesis:** a reminder on day 6 after an order increases the share of customers who order again within 7 days.')
    c1, c2, c3, c4 = st.columns(4)
    with c1: p1 = st.number_input('Current rate (%)', 1.0, 99.0, round(base, 1), 0.5, help='From this data: share of repeat orders placed within 7 days.')
    with c2: lift = st.slider('Smallest lift worth detecting (relative %)', 1, 30, 5)
    with c3: alpha = st.select_slider('Significance level', [0.01, 0.05, 0.10], 0.05)
    with c4: power = st.select_slider('Power', [0.8, 0.9, 0.95], 0.8)
    pa, pb = p1 / 100, p1 / 100 * (1 + lift / 100)
    z = NormalDist()
    za, zb = z.inv_cdf(1 - alpha / 2), z.inv_cdf(power)
    pbar = (pa + pb) / 2
    n = ((za * np.sqrt(2 * pbar * (1 - pbar)) + zb * np.sqrt(pa * (1 - pa) + pb * (1 - pb))) ** 2) / (pb - pa) ** 2
    weekly = st.number_input('Customers you can include per week (your assumption)', 1000, 5_000_000, 50_000, 5000)
    k1, k2, k3 = st.columns(3)
    with k1: ui.kpi('👥', 'Customers per group', f'{int(np.ceil(n)):,}', 'Control and reminder', ui.BLUE)
    with k2: ui.kpi('🎯', 'Detects', f'{100 * pa:.1f}% → {100 * pb:.1f}%', f'{lift}% relative lift', ui.GREEN)
    with k3: ui.kpi('⏱️', 'Approximate duration', f'{max(1, int(np.ceil(2 * n / weekly)))} week(s)', f'At {weekly:,} customers a week', ui.ORANGE)
    st.markdown(' ')
    lifts = np.arange(1, 31)
    sizes = [((za * np.sqrt(2 * ((pa + pa * (1 + l / 100)) / 2) * (1 - (pa + pa * (1 + l / 100)) / 2))
               + zb * np.sqrt(pa * (1 - pa) + pa * (1 + l / 100) * (1 - pa * (1 + l / 100)))) ** 2) / (pa * l / 100) ** 2 for l in lifts]
    fig = px.line(x=lifts, y=sizes, log_y=True, markers=True, labels={'x': 'Relative lift to detect (%)', 'y': 'Customers per group (log)'},
                  title='Smaller effects need far bigger tests')
    fig.add_vline(x=lift, line_dash='dot', line_color=ui.ORANGE)
    fig.update_traces(line_color=ui.BLUE)
    ui.chart(fig, height=360)
    st.markdown('''
**Test plan**
- **Randomise by customer** into control (no reminder) and treatment (day 6 reminder), so one person never sees both.
- **Primary metric:** ordered again within 7 days. **Guardrails:** unsubscribe rate, basket size, order cancellations.
- **Decide before looking:** sample size and duration are fixed up front; no stopping early on a lucky day.
- **Analyse:** two proportion z test (or a logistic regression controlling for segment), report the lift with a confidence interval.
- **Then segment:** check whether the effect differs for New explorers vs Loyal regulars before scaling it to everyone.''')
    st.caption('Sample size uses the standard two proportion formula with a two sided test. Weekly traffic is your own input, not a figure from the data.')


TABS = {
    'cohorts': ('🧬', 'Cohort analysis', 'How customers change from their 1st order to their 100th, weekly vs monthly shoppers, and time to next order.', 'Cohorts', ui.GREEN, cohorts),
    'segments': ('👥', 'Customer segments', 'Eight kinds of shoppers found with k means clustering, each with a recommended action.', 'Clustering', ui.BLUE, segments),
    'model': ('🔮', 'Reorder prediction', 'A machine learning model that predicts what each customer will buy again, tested against simple rules.', 'Machine learning', ui.PINK, reorder_model),
    'experiment': ('🧪', 'Experiment design', 'How to prove a recommendation works with an A/B test, including sample size and power.', 'Experimentation', ui.ORANGE, experiment),
}


def render():
    try:
        raw('SELECT 1 FROM ml_reorder_info LIMIT 1')
    except Exception:
        ui.page_header('🤖', 'Advanced analytics', 'Cohorts, customer segmentation, a machine learning model and experiment design.', ui.PALETTE[6])
        st.warning('The machine learning tables have not been built yet. Run `python -m src.ml` (about 2 minutes), then refresh.')
        return
    open_key = st.session_state.get('adv_open')
    if open_key in TABS:
        ui.back_button('adv_open', '← All advanced analyses')
        with st.container(border=True):
            TABS[open_key][5]()
    else:
        ui.page_header('🤖', 'Advanced analytics', 'Cohorts, customer segmentation, a machine learning model and experiment design. Pick one to open it.', ui.PALETTE[6])
        ui.gallery([(k, e, t, d, tag, c) for k, (e, t, d, tag, c, _) in TABS.items()], 'adv_open', columns=2)
    ui.footer()
