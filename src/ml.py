'''Machine learning layer: customer segmentation (k-means) and a "buy it again" reorder prediction model.

Results are written to ml_* tables so the app only reads small tables. Run after build.py with:  python -m src.ml
'''
import io
import time
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve, silhouette_score
from sklearn.preprocessing import StandardScaler
from .data import connect
from .query import query_dataframe

SEED = 42

# ---------------------------------------------------------------- helpers

def write_table(cur, name, df):
    '''Replace a table with the contents of a DataFrame using COPY.'''
    types = {'int64': 'BIGINT', 'int32': 'INTEGER', 'float64': 'DOUBLE PRECISION', 'bool': 'BOOLEAN'}
    cols = ', '.join(f'"{c}" {types.get(str(t), "TEXT")}' for c, t in df.dtypes.items())
    cur.execute(f'DROP TABLE IF EXISTS {name}')
    cur.execute(f'CREATE TABLE {name} ({cols})')
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    with cur.copy(f'COPY {name} FROM STDIN WITH (FORMAT CSV)') as copy:
        copy.write(buf.read())


# ---------------------------------------------------------------- customer segmentation

SEGMENT_FEATURES = {
    'orders': 'Observed orders',
    'deepest_order': 'Lifetime depth (highest order number)',
    'avg_basket': 'Average basket size',
    'avg_days_between': 'Average days between orders',
    'reorder_pct': 'Reorder rate (%)',
    'organic_share': 'Organic share of items (%)',
    'produce_share': 'Produce share (%)',
    'dairy_share': 'Dairy and eggs share (%)',
    'snacks_share': 'Snacks share (%)',
    'beverages_share': 'Beverages share (%)',
    'frozen_share': 'Frozen share (%)',
    'pantry_share': 'Pantry share (%)',
    'household_share': 'Household and personal care share (%)',
    'baby_share': 'Babies share (%)',
    'alcohol_share': 'Alcohol share (%)',
    'avg_hour': 'Average order hour',
}

SEGMENT_SQL = '''
WITH items AS (
  SELECT i.user_id, COUNT(*) AS n,
    AVG(CASE WHEN p.is_organic THEN 1.0 ELSE 0 END) AS organic_share,
    AVG(CASE WHEN i.department = 'produce' THEN 1.0 ELSE 0 END) AS produce_share,
    AVG(CASE WHEN i.department = 'dairy eggs' THEN 1.0 ELSE 0 END) AS dairy_share,
    AVG(CASE WHEN i.department = 'snacks' THEN 1.0 ELSE 0 END) AS snacks_share,
    AVG(CASE WHEN i.department = 'beverages' THEN 1.0 ELSE 0 END) AS beverages_share,
    AVG(CASE WHEN i.department = 'frozen' THEN 1.0 ELSE 0 END) AS frozen_share,
    AVG(CASE WHEN i.department IN ('pantry', 'canned goods', 'dry goods pasta') THEN 1.0 ELSE 0 END) AS pantry_share,
    AVG(CASE WHEN i.department IN ('household', 'personal care') THEN 1.0 ELSE 0 END) AS household_share,
    AVG(CASE WHEN i.department = 'babies' THEN 1.0 ELSE 0 END) AS baby_share,
    AVG(CASE WHEN i.department = 'alcohol' THEN 1.0 ELSE 0 END) AS alcohol_share
  FROM order_items i JOIN mart_product p USING (product_id) GROUP BY i.user_id),
baskets AS (
  SELECT user_id, MAX(order_number) AS deepest_order, AVG(order_hour_of_day) AS avg_hour FROM basket_sizes GROUP BY user_id)
SELECT c.user_id, c.orders, b.deepest_order, c.avg_basket, c.avg_days_between, c.reorder_pct, b.avg_hour,
  100 * items.organic_share AS organic_share, 100 * items.produce_share AS produce_share, 100 * items.dairy_share AS dairy_share,
  100 * items.snacks_share AS snacks_share, 100 * items.beverages_share AS beverages_share, 100 * items.frozen_share AS frozen_share,
  100 * items.pantry_share AS pantry_share, 100 * items.household_share AS household_share, 100 * items.baby_share AS baby_share,
  100 * items.alcohol_share AS alcohol_share, items.n AS items
FROM mart_customer c JOIN items USING (user_id) JOIN baskets b USING (user_id)
'''


def _name_segment(z):
    '''Readable persona name from a cluster centre's most distinctive features (z scores vs the average customer).'''
    if z['baby_share'] > 1.5: return '👶 Young families'
    if z['alcohol_share'] > 1.5: return '🍷 Party planners'
    if z['household_share'] > 1.5: return '🧽 Household essentials'
    if z['beverages_share'] > 1.5: return '🥤 Drinks first'
    if z['snacks_share'] > 0.8 and z['frozen_share'] > 0.5: return '🍿 Snacks and frozen'
    if z['snacks_share'] > 0.8: return '🍿 Snack lovers'
    if z['deepest_order'] > 0.8 and z['reorder_pct'] > 0.4: return '💚 Loyal regulars'
    if z['organic_share'] > 0.5 and z['produce_share'] > 0.5: return '🥬 Fresh and organic'
    if z['reorder_pct'] < -0.4 and z['deepest_order'] < -0.4: return '🌱 New explorers'
    if z['avg_basket'] > 0.8: return '🧺 Big basket shoppers'
    return '🛒 Everyday mainstream'


def build_segments(cur, conn):
    t0 = time.time()
    df = query_dataframe(conn, SEGMENT_SQL)
    feats = list(SEGMENT_FEATURES)
    X = df[feats].astype(float).copy()
    X['avg_days_between'] = X['avg_days_between'].fillna(X['avg_days_between'].median())
    for col in ('orders', 'deepest_order', 'avg_basket'):
        X[col] = np.log1p(X[col])
    scaler = StandardScaler().fit(X)
    Z = scaler.transform(X)
    rng = np.random.default_rng(SEED)
    sample = rng.choice(len(Z), size=min(20000, len(Z)), replace=False)
    scores = []
    for k in range(4, 9):
        km = KMeans(n_clusters=k, n_init=5, random_state=SEED).fit(Z[sample])
        scores.append({'k': k, 'silhouette': float(silhouette_score(Z[sample], km.labels_, sample_size=8000, random_state=SEED)),
                       'inertia': float(km.inertia_)})
    best_k = max(scores, key=lambda s: s['silhouette'])['k']
    km = KMeans(n_clusters=best_k, n_init=10, random_state=SEED).fit(Z)
    df['cluster'] = km.labels_
    centres = pd.DataFrame(km.cluster_centers_, columns=feats)
    names, used = {}, {}
    for c in range(best_k):
        name = _name_segment(centres.loc[c])
        used[name] = used.get(name, 0) + 1
        names[c] = name if used[name] == 1 else f'{name} {used[name]}'
    df['segment'] = df['cluster'].map(names)
    profile = df.groupby('segment').agg(customers=('user_id', 'count'), items=('items', 'sum'),
                                        **{f: (f, 'mean') for f in feats}).reset_index()
    profile['customer_share'] = 100 * profile['customers'] / profile['customers'].sum()
    profile['item_share'] = 100 * profile['items'] / profile['items'].sum()
    z = centres.copy(); z['segment'] = [names[c] for c in range(best_k)]
    write_table(cur, 'ml_segments', df[['user_id', 'segment']])
    write_table(cur, 'ml_segment_profiles', profile.round(3))
    write_table(cur, 'ml_segment_centres', z.round(3))
    write_table(cur, 'ml_segment_k', pd.DataFrame(scores).round(4))
    print(f'Built customer segments: k={best_k}, {len(df):,} customers in {time.time() - t0:.0f}s', flush=True)


# ---------------------------------------------------------------- reorder prediction

REORDER_SQL = '''
WITH target AS (       -- each customer's latest observed order is the one we try to predict
  SELECT DISTINCT ON (user_id) user_id, order_id AS target_order, order_number AS target_number,
    days_since_prior_order AS target_gap, order_dow AS target_dow, order_hour_of_day AS target_hour
  FROM basket_sizes WHERE user_id IN (SELECT user_id FROM basket_sizes GROUP BY user_id HAVING COUNT(*) >= 2)
  ORDER BY user_id, order_number DESC),
history AS (           -- everything the customer bought before that order
  SELECT i.* FROM order_items i JOIN target t USING (user_id) WHERE i.order_number < t.target_number),
user_hist AS (
  SELECT user_id, COUNT(DISTINCT order_id) AS hist_orders, COUNT(*)::float / COUNT(DISTINCT order_id) AS hist_basket,
    AVG(reordered) AS user_reorder_rate, MAX(order_number) AS last_hist_number FROM history GROUP BY user_id),
product_stats AS (     -- product popularity and loyalty measured on history rows only (no peeking at targets)
  SELECT product_id, COUNT(*) AS product_buys, AVG(reordered) AS product_reorder_rate,
    AVG(add_to_cart_order) AS product_cart_pos FROM history GROUP BY product_id),
cand AS (
  SELECT h.user_id, h.product_id, COUNT(*) AS times_bought, MAX(h.order_number) AS last_bought_number,
    MIN(h.order_number) AS first_bought_number, AVG(h.add_to_cart_order) AS user_cart_pos, MAX(h.reordered) AS was_reorder,
    MIN(h.department) AS department
  FROM history h GROUP BY h.user_id, h.product_id)
SELECT c.user_id, c.product_id, c.department, c.times_bought, c.user_cart_pos, c.was_reorder,
  t.target_number - c.last_bought_number AS orders_since_bought, t.target_number - c.first_bought_number AS orders_since_first,
  c.times_bought::float / u.hist_orders AS share_of_history, u.hist_orders, u.hist_basket, u.user_reorder_rate,
  t.target_number, t.target_gap, t.target_dow, t.target_hour,
  COALESCE(ps.product_buys, 0) AS product_buys, ps.product_reorder_rate, ps.product_cart_pos,
  (c.last_bought_number = u.last_hist_number)::int AS in_last_basket,
  (EXISTS (SELECT 1 FROM order_items x WHERE x.order_id = t.target_order AND x.product_id = c.product_id))::int AS label
FROM cand c JOIN target t USING (user_id) JOIN user_hist u USING (user_id) LEFT JOIN product_stats ps USING (product_id)
'''

FEATURES = {
    'times_bought': 'How many earlier orders contained the product',
    'share_of_history': 'Share of the customer’s earlier orders that contained it',
    'orders_since_bought': 'Orders since the customer last bought it',
    'orders_since_first': 'Orders since the customer first bought it',
    'in_last_basket': 'Was it in the customer’s most recent order',
    'was_reorder': 'Had the customer already reordered it before',
    'user_cart_pos': 'Where the customer usually puts it in the cart',
    'hist_orders': 'Number of earlier orders we see for the customer',
    'hist_basket': 'Customer’s typical basket size',
    'user_reorder_rate': 'How often the customer reorders in general',
    'target_number': 'How far into their lifetime the customer is',
    'target_gap': 'Days since the customer’s previous order',
    'target_dow': 'Day of week of the new order',
    'target_hour': 'Hour of the new order',
    'product_buys': 'How popular the product is',
    'product_reorder_rate': 'How often everyone reorders the product',
    'product_cart_pos': 'Where people usually put the product in the cart',
}


def _per_user_f1(df, pred_col):
    g = df.assign(tp=df['label'] * df[pred_col]).groupby('user_id').agg(tp=('tp', 'sum'), pred=(pred_col, 'sum'), actual=('label', 'sum'))
    p = np.where(g['pred'] > 0, g['tp'] / g['pred'].clip(lower=1), 0)
    r = np.where(g['actual'] > 0, g['tp'] / g['actual'].clip(lower=1), 0)
    den = p + r
    f1 = np.divide(2 * p * r, den, out=np.zeros_like(den, dtype=float), where=den > 0)
    f1 = np.where((g['actual'] == 0) & (g['pred'] == 0), 1.0, f1)   # correctly predicting "nothing" counts as perfect
    return float(f1.mean()), float(p[g['pred'] > 0].mean()), float(r[g['actual'] > 0].mean())


def _hit_rate_at_k(df, score_col, k=5):
    ranked = df.sort_values(['user_id', score_col], ascending=[True, False])
    top = ranked.groupby('user_id').head(k)
    users = top.groupby('user_id')['label'].agg(['sum', 'count'])
    return float((users['sum'] / users['count']).mean())


def build_reorder_model(cur, conn):
    t0 = time.time()
    df = query_dataframe(conn, REORDER_SQL)
    feats = list(FEATURES)
    df[feats] = df[feats].astype(float)
    test_mask = (df['user_id'] % 5) == 0                    # split by customer so no customer is in both sets
    train, test = df[~test_mask], df[test_mask].copy()
    val_mask = (train['user_id'] % 10) == 1
    fit, val = train[~val_mask], train[val_mask]
    model = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06, max_leaf_nodes=48, l2_regularization=1.0,
                                           early_stopping=True, validation_fraction=0.1, random_state=SEED)
    model.fit(fit[feats], fit['label'])
    val_scores = model.predict_proba(val[feats])[:, 1]
    thresholds = np.linspace(0.05, 0.6, 23)
    val_f1 = [(t, _per_user_f1(val.assign(pred=(val_scores >= t).astype(int)), 'pred')[0]) for t in thresholds]
    best_t = max(val_f1, key=lambda x: x[1])[0]
    test['score'] = model.predict_proba(test[feats])[:, 1]
    test['model_pred'] = (test['score'] >= best_t).astype(int)
    test['base_last'] = test['in_last_basket'].astype(int)               # baseline 1: repeat their most recent order
    test['base_all'] = 1                                                   # baseline 2: everything they bought before
    test['base_freq'] = (test['times_bought'] >= 2).astype(int)            # baseline 3: anything bought at least twice
    test['base_score'] = test['share_of_history'] + 0.001 * test['in_last_basket']

    rows = []
    for name, col in [('Model (gradient boosting)', 'model_pred'), ('Repeat last order', 'base_last'),
                      ('Bought 2 or more times', 'base_freq'), ('Everything bought before', 'base_all')]:
        f1, prec, rec = _per_user_f1(test, col)
        rows.append({'approach': name, 'mean_f1': f1, 'precision': prec, 'recall': rec})
    metrics = pd.DataFrame(rows)
    auc = roc_auc_score(test['label'], test['score'])
    ap = average_precision_score(test['label'], test['score'])
    info = pd.DataFrame([
        ('roc_auc', auc), ('pr_auc', ap), ('base_rate', test['label'].mean()), ('threshold', best_t),
        ('hit_rate_at_5_model', _hit_rate_at_k(test, 'score')), ('hit_rate_at_5_baseline', _hit_rate_at_k(test, 'base_score')),
        ('train_rows', len(fit)), ('validation_rows', len(val)), ('test_rows', len(test)),
        ('train_customers', fit['user_id'].nunique()), ('test_customers', test['user_id'].nunique()),
        ('iterations', model.n_iter_), ('seconds', 0.0)], columns=['key', 'value'])

    sample = test.sample(min(60000, len(test)), random_state=SEED)
    imp = permutation_importance(model, sample[feats], sample['label'], scoring='roc_auc', n_repeats=3, random_state=SEED)
    importance = pd.DataFrame({'feature': feats, 'importance': imp.importances_mean, 'std': imp.importances_std,
                               'meaning': [FEATURES[f] for f in feats]}).sort_values('importance', ascending=False)

    fpr, tpr, _ = roc_curve(test['label'], test['score'])
    prec_c, rec_c, _ = precision_recall_curve(test['label'], test['score'])
    pick = lambda a: np.linspace(0, len(a) - 1, min(150, len(a))).astype(int)
    curves = pd.concat([pd.DataFrame({'curve': 'roc', 'x': fpr[pick(fpr)], 'y': tpr[pick(tpr)]}),
                        pd.DataFrame({'curve': 'pr', 'x': rec_c[pick(rec_c)], 'y': prec_c[pick(prec_c)]})])

    bins = pd.cut(test['score'], np.linspace(0, 1, 11), include_lowest=True)
    calib = test.groupby(bins, observed=True).agg(predicted=('score', 'mean'), actual=('label', 'mean'), rows=('label', 'size')).reset_index(drop=True)

    names = query_dataframe(conn, 'SELECT product_id, product_name FROM products')
    users = test.groupby('user_id').filter(lambda g: g['label'].sum() >= 2 and len(g) >= 8)['user_id'].drop_duplicates()
    users = users.sample(min(150, len(users)), random_state=SEED)
    ex = test[test['user_id'].isin(users)].sort_values(['user_id', 'score'], ascending=[True, False]).groupby('user_id').head(10)
    ex = ex.merge(names, on='product_id')[['user_id', 'product_name', 'department', 'score', 'label', 'times_bought', 'hist_orders']]
    ex['rank'] = ex.groupby('user_id')['score'].rank(ascending=False, method='first').astype(int)

    info.loc[info['key'] == 'seconds', 'value'] = time.time() - t0
    write_table(cur, 'ml_reorder_metrics', metrics.round(4))
    write_table(cur, 'ml_reorder_info', info)
    write_table(cur, 'ml_reorder_importance', importance.round(5))
    write_table(cur, 'ml_reorder_curves', curves.round(4))
    write_table(cur, 'ml_reorder_calibration', calib.round(4))
    write_table(cur, 'ml_reorder_examples', ex.round(4))
    print(f'Built reorder model: AUC {auc:.3f}, {len(df):,} candidate rows in {time.time() - t0:.0f}s', flush=True)


def build_ml(cur, conn):
    build_segments(cur, conn)
    build_reorder_model(cur, conn)


if __name__ == '__main__':
    import sys
    with connect() as conn:
        with conn.cursor() as cur:
            if not sys.argv[1:] or 'segments' in sys.argv: build_segments(cur, conn)
            if not sys.argv[1:] or 'reorder' in sys.argv: build_reorder_model(cur, conn)
