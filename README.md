# Instacart Grocery Basket Intelligence

An interactive BI portfolio app that explores **real, anonymized Instacart grocery orders**. It combines an analyst dashboard, adjustable cohort/product investigations, purchase-affinity analysis, governed natural-language questions, local optional Ollama explanations, CSV exports, and data-quality checks.

> **Implementation status:** Application code and unit tests are included. The complete official dataset is **not distributed here**, and full PostgreSQL integration/runtime verification remains to be done locally. No business findings or performance statistics have been invented. The Streamlit BI app is the primary deliverable; a `.pbix` report is not included.

## 1. Where to get the actual data

**First choice (simpler dataset listing):** https://www.kaggle.com/datasets/psparks/instacart-market-basket-analysis

**Original Instacart Kaggle competition:** https://www.kaggle.com/competitions/instacart-market-basket-analysis/data

If Kaggle shows a sign-in wall, **log in or create a free account**. On the competition page you may also need to join/accept the terms before the Download option is enabled. The community dataset link is typically easier to navigate. Do not use `sample_submission.csv` as input.

Alternatively, with Kaggle CLI configured (https://github.com/Kaggle/kaggle-api):

```powershell
pip install kaggle
kaggle datasets download -d psparks/instacart-market-basket-analysis -p data --unzip
```

Place these files **directly** in `data/` (not an extra nested folder):

```
data/
  orders.csv
  order_products__prior.csv
  order_products__train.csv
  products.csv
  aisles.csv
  departments.csv
```

For a double-click check, open `data/` in File Explorer and confirm every exact filename. One of the large CSV files has tens of millions of rows; loading may require substantial storage and time.
<img width="775" height="470" alt="home page" src="https://github.com/user-attachments/assets/db4cbe2f-d399-44b6-8b65-92f353e2532e" />

<img width="843" height="470" alt="deep  dive" src="https://github.com/user-attachments/assets/4d6aa99c-98b2-4b86-8d59-1f79c7d069e8" />

## 2. Set up PostgreSQL on Windows

Download the free PostgreSQL server from https://www.postgresql.org/download/windows/. Open `psql` or pgAdmin and create a database:

```sql
CREATE DATABASE instacart_bi;
```

Set credentials in **PowerShell in the project folder**:

```powershell
$env:PGHOST='localhost'
$env:PGPORT='5432'
$env:PGDATABASE='instacart_bi'
$env:PGUSER='postgres'
$env:PGPASSWORD='YOUR_LOCAL_PASSWORD'
```

Environment variables only apply to the current PowerShell session. You may use `.env.example` as a reference, but `.env` is not automatically loaded by the application. Never commit passwords or `.env`.

## 3. Install, ingest, run

Python 3.10+ recommended; use a modern Windows machine with disk space for the data, PostgreSQL tables, and indexes.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`build.py` drops/rebuilds **six known Instacart tables** in the selected database. Only run it on your dedicated `instacart_bi` database; do not point it at a production database. It creates `order_items` and `basket_sizes` views and validates integrity.

The ingestion script reads local CSVs in chunks with PostgreSQL COPY; the Streamlit UI reads from PostgreSQL, not synthetic/demo data.

## 4. The application

Seven pages, navigated with buttons along the top:

- **🏠 Home:** what the project is about, headline numbers, "5 things this data reveals" (each opens its story) and where to go next.
- **💡 Insights (for anyone):** nine short stories, each with one clean chart, a takeaway and a "So what?" business recommendation. No SQL or jargon.
- **🧪 Deep dives (for analysts):** volume vs loyalty, order sequence, cart position, Pareto long tail, department affinity matrix, customer distributions and correlations, the lift method, data quality and cleaning log, database design with a live speed race. SQL shown for each.
- **🤖 Advanced:** lifecycle and pace **cohort analysis** (with survival analysis of the gap between orders), **customer segmentation** (k means on 16 behaviour features, 8 named personas with actions), a **reorder prediction model** (gradient boosting, evaluated on unseen customers against three simple rules, with feature importance, ROC, precision recall and calibration, and an interactive "Buy it again" demo) and **A/B test design** (sample size and power).
- **🔎 Look up:** search any product for its profile (rank, loyalty, when it sells, what it is bought with, similar products) or open a department scorecard.
- **💬 Ask the data:** a plain-English question builder for combinations the stories don't cover (department × time window × measure; allow-listed, parameterized SQL — no free-form AI-generated SQL), plus a **SQL Lab**: a read-only SQL editor with advanced examples (window functions, percentiles, regression slope, CTE market basket), a schema browser and automatic charts.
- **📚 Documentation:** project overview, datasets and data dictionary, data model and pipeline diagrams, and metric definitions.

`build.py` also creates 17 pre-aggregated `mart_*` summary tables (see `src/marts.py`) so pages load quickly. Rebuild only those with `python -m src.marts`, or a single one with `python -m src.marts mart_pairs`. It then trains the segmentation and reorder models (`src/ml.py`, about 2 minutes) and stores their results in `ml_*` tables. Retrain them alone with `python -m src.ml`.

### Optional free local LLM

Install Ollama from https://ollama.com/download, then in a separate terminal:

```powershell
ollama pull llama3.2:3b
ollama serve
```

If Ollama already runs in the background, you may not need `ollama serve`. Without Ollama, question interpretation and verified SQL analysis remain functional, with deterministic descriptions. Local LLM quality and speed depend on hardware. The model never gets write credentials or arbitrary SQL privileges.

### Architecture

`Official CSVs → Python COPY ingestion → PostgreSQL views → Streamlit dashboard / governed query compiler → parameterized SQL results → optional local LLM interpretation → Plotly charts + CSV export`

## 5. Generate your evidence-based findings report

```powershell
.\.venv\Scripts\python.exe generate_report.py
```

This creates `reports/EXECUTIVE_FINDINGS.md` only after querying the actual populated database. It documents numerical observations, hypotheses, and limitations. The generated report is initially ignored by Git; review it, then deliberately publish it if appropriate.

## 6. Power BI optional handoff

```powershell
.\.venv\Scripts\python.exe export_powerbi.py
```

Exports small reconciled reporting tables into `powerbi/exports/`. Follow `powerbi/README.md`. **No finished `.pbix` is included**; it requires creating the desktop report manually. The fully interactive dashboard is Streamlit.

## 7. Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover SQL guardrails and question routing logic. Because this package cannot include the dataset or launch a PostgreSQL server here, successful tests do **not** imply a verified full data run.

## 8. What not to claim

The Instacart dataset has no prices, revenue/profit, geography, shipment dates, or true calendar dates. `reordered` is a line-item repeat flag and not equivalent to customer retention. Orders with unobserved product baskets cannot be assumed to have zero items. Do not publish claimed sales uplift, retention impact, or AI answer accuracy until validated from real measurements.

## 9. GitHub publishing

Initialize a Git repository, commit only application source/docs and small metadata (the `.gitignore` excludes downloaded data, secrets, extracts). Publish screenshots **only after running against the actual dataset**. Include actual analysis findings, query evidence, and known limitations in your project description.

The app is a *portfolio demonstration* using publicly released anonymized data; it is not an Instacart internal product or official Instacart reporting system.
