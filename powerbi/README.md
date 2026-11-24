# Power BI Desktop handoff

Run `python export_powerbi.py` after `python build.py`. Load CSVs in `powerbi/exports/` using **Get Data → Text/CSV**. Create measures in Power BI; do not sum percentages.

Recommended pages:
1. Executive: observed orders, items, customers, item reorder %, department volume
2. Customers: user frequency segments, reorder % by order sequence
3. Demand: orders by hour, department purchase patterns

Cross-check every KPI against the exported CSV. The repository does NOT falsely claim a completed .pbix; a Power BI Desktop report must be authored on Windows and can be saved locally. Streamlit is the complete interactive dashboard.
