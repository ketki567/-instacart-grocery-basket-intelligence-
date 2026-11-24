"""Create a reproducible business review from the real database, never invented figures."""
from pathlib import Path
from datetime import datetime, timezone
from src.data import connect,check
from src import engine

def write():
    with connect(read_only=True) as conn:
        k=engine.overview(conn).iloc[0]
        depts=engine.comparison(conn,'department',100,30)
        hours=engine.trend(conn,'hour','All')
        segments=engine.basket_segments(conn)
        failed=check(conn)
    lines=['# Instacart Grocery Intelligence — Evidence-Based Business Review',
        f'Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',
        '', '> Based on the publicly released anonymized Instacart dataset, not official current company operations.',
        '', '## Executive overview',
        f'- Observed orders with product details: **{int(k["orders"]):,}**',
        f'- Observed purchasing customers: **{int(k["customers"]):,}**',
        f'- Product line items: **{int(k["items"]):,}**',
        f'- Item reorder share: **{float(k["reorder_rate_pct"]):.2f}%** (not customer retention)',
        '', '## Evidence-backed observations']
    if len(depts):
        high=depts.sort_values('item_purchases',ascending=False).iloc[0]
        repeat=depts[depts.item_purchases>=1000].sort_values('reorder_pct',ascending=False).iloc[0]
        lines += [f'- Highest item-volume department: **{high.segment}** with **{int(high.item_purchases):,}** item purchases.',
                  f'- Highest qualifying reorder share (minimum 1,000 line items): **{repeat.segment}**, **{float(repeat.reorder_pct):.2f}%**.',
                  '- **Business investigation:** compare high-volume and high-reorder departments for assortment and placement prioritization; this is not causal impact evidence.']
    if len(hours):
        peak=hours.sort_values('orders',ascending=False).iloc[0]
        lines += [f'- Peak *observed* order hour: **{int(peak.period):02d}:00** with **{int(peak.orders):,}** recorded orders.',
                  '- **Operational hypothesis:** demand concentration may inform capacity planning; validate with current operational data before staffing changes.']
    if len(segments):
        top=segments.sort_values('customers',ascending=False).iloc[0]
        lines += [f'- Most common observed frequency band: **{top.segment}**, **{int(top.customers):,}** customers.',
                  '- **Customer hypothesis:** compare assortment and reorder patterns across observed-frequency bands; incomplete histories limit retention inference.']
    lines+=['','## Integrity checks']+[f'- {name}: **{value}** violations' for name,value in failed.items()]
    lines+=['','## Metric and data limitations',
        'No revenue, prices, customer demographics, shipment outcomes, calendar months or true churn can be measured. The published dataset includes orders whose contents are not observed. Associations are not causal effects.',
        '', '## Recommended follow-up analysis',
        '1. Compare item-based reorder percentages with explicit denominator thresholds.',
        '2. Investigate whether high-frequency departments also have unusually high peak-hour demand.',
        '3. Inspect high-lift product pairs with reasonable support and test merchandising hypotheses separately.',
        '4. Independently reconcile the reported KPIs to SQL queries before adding numbers to a resume.']
    path=Path('reports/EXECUTIVE_FINDINGS.md');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8');print('Created',path)
if __name__=='__main__':write()
