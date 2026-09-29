# AI-Based Investment Portfolio Management and Risk Analysis System

A web application for **educational portfolio analysis and risk monitoring**, built with Flask, SQLite and scikit-learn.

Users can register, record their investment holdings, and see genuinely calculated portfolio performance, asset allocation, concentration risk, drawdown, and machine-learning-based anomaly detection. An AI assistant answers questions about the user's own portfolio (via a controlled natural-language-to-SQL pipeline) and about financial concepts (via a RAG knowledge base).

> **Disclaimer:** This system is intended for educational portfolio analysis and risk monitoring. It does not guarantee investment returns and does not constitute personalized financial advice. It never buys or sells anything.

---

## 1. Project Overview

| Item | Detail |
|---|---|
| Project type | BCA 2nd-year IEEE project |
| Backend | Python 3.10+, Flask 3 |
| Database | SQLite via SQLAlchemy |
| Frontend | HTML, CSS, JavaScript, Bootstrap 5, Chart.js 4 |
| Data processing | Pandas, NumPy |
| Machine learning | scikit-learn (Isolation Forest, TF-IDF) |
| AI | Optional LLM API (key in `.env`), with documented offline fallback |

### Design principle followed throughout

**Working functionality over number of features.** Every button performs a real backend operation, and every number displayed is computed from the database at request time. There are no hard-coded portfolio values, charts, risk scores, alerts, or AI answers anywhere in the codebase.

---

## 2. Features

### Implemented and working

- **Authentication** — registration, login, logout, Flask-Login sessions, Werkzeug password hashing, duplicate-email and password-confirmation validation.
- **User isolation** — every query is filtered by `user_id`. User A cannot see User B's data through any page or through the AI assistant.
- **Holdings CRUD** — add, view, edit, delete. Data persists in SQLite across restarts. A `BUY` transaction is recorded automatically on add.
- **Portfolio calculations** — investment value, current value, profit/loss, and return %, per holding and in aggregate.
- **Market data layer** — 2 years of daily OHLCV data for 8 symbols, loaded into the `market_data` table. Clearly labelled as historical/sample data. An optional external API can be plugged in via `.env`, with graceful fallback if it fails.
- **Dashboard** — live totals, asset allocation doughnut, portfolio value line chart, holdings table, recent alerts.
- **Performance page** — portfolio value over time, investment vs current value by asset, return % by asset, P/L by asset. All Chart.js charts read from JSON APIs backed by real calculations.
- **Asset allocation** — by asset and by sector, computed as `asset value / total portfolio value × 100`.
- **Concentration risk** — flags sectors or single holdings at or above a configurable threshold (`CONCENTRATION_THRESHOLD_PERCENT`). Explains the condition; never recommends buying or selling.
- **Drawdown** — reconstructs a real portfolio value series from each holding's quantity and its symbol's daily closes, then computes current drawdown, maximum drawdown, and the previous peak.
- **Anomaly detection** — a real `IsolationForest` fitted on each held symbol's daily returns and 5-day rolling volatility. Flags statistically unusual observations without predicting direction.
- **Alert system** — a real service that runs all of the above checks and writes concentration, drawdown, anomaly, and market-data alerts into the `alerts` table, with per-day de-duplication. View, mark read, mark all read, and re-run checks on demand.
- **AI assistant** — routes each question to NL-to-SQL, RAG, or both, and stores chat history.
- **NL-to-SQL** — intent classification → whitelisted parameterized SQL template → independent SQL validator → read-only, user-scoped execution.
- **RAG knowledge base** — 6 financial documents → chunking → TF-IDF vector space → cosine-similarity retrieval → grounded answer. The knowledge page shows the actual retrieved chunks and their similarity scores.
- **Validation and error handling** — server-side validation on every input; friendly error pages; no Python stack traces shown to users.

### Deliberately left out (documented as future scope)

These were excluded rather than faked:

- Live real-time market data (the integration point exists and is documented; no key is bundled).
- SELL transactions and partial position exits.
- Sharpe ratio, beta, and VaR.
- Portfolio rebalancing suggestions (deliberately out of scope — the system explains conditions, it does not advise).
- A persistent vector database such as FAISS or Chroma (the TF-IDF index is rebuilt in memory at startup).

---

## 3. Architecture

```
Browser (HTML/JS/Chart.js)
        │  HTTP + JSON
        ▼
Flask routes (blueprints)     ← authentication guard on every protected route
        │
        ▼
Services layer                ← all business logic lives here
  portfolio · performance · risk · anomaly · alert · sql · rag · ai · market_data
        │
        ▼
SQLAlchemy models → SQLite (database/portfolio.db)
```

Routes stay thin: they handle HTTP, call one service, and render. This keeps the logic testable and easy to explain in a viva.

### Folder structure

```
AI_Investment_Portfolio_Management/
├── app.py                      # application factory + entry point
├── config.py                   # all configuration, read from .env
├── seed_data.py                # optional: create demo user + sample holdings
├── smoke_test.py               # end-to-end automated test script
├── requirements.txt
├── .env.example
├── README.md
├── TESTING.md
│
├── database/
│   ├── __init__.py
│   ├── database.py             # the single shared SQLAlchemy instance
│   ├── models.py               # all 7 tables
│   └── portfolio.db            # created on first run
│
├── routes/
│   ├── __init__.py
│   ├── auth.py                 # register / login / logout
│   ├── portfolio.py            # dashboard, holdings CRUD, transactions, settings
│   ├── analytics.py            # performance page + chart JSON APIs
│   ├── risk.py                 # risk page + risk JSON APIs
│   ├── alerts.py               # alerts page + actions
│   ├── ai.py                   # AI assistant page + ask API
│   └── knowledge.py            # knowledge page + search API
│
├── services/
│   ├── market_data_service.py  # CSV → DB loading, price lookup, API fallback
│   ├── portfolio_service.py    # holdings CRUD + input validation
│   ├── performance_service.py  # all portfolio calculations
│   ├── risk_service.py         # concentration risk + drawdown
│   ├── anomaly_service.py      # Isolation Forest orchestration
│   ├── alert_service.py        # real alert generation + persistence
│   ├── sql_service.py          # controlled NL-to-SQL with validator
│   ├── rag_service.py          # chunking, TF-IDF index, retrieval, answers
│   ├── ai_service.py           # question router (SQL / RAG / hybrid)
│   └── ai_client.py            # LLM API wrapper with graceful fallback
│
├── models/
│   └── anomaly_model.py        # the IsolationForest model itself
│
├── scripts/
│   └── generate_market_data.py # regenerates data/market_data.csv
│
├── data/
│   ├── market_data.csv         # 4,032 rows: 8 symbols × ~2 years
│   └── sample_data.csv         # 6 sample holdings for the demo user
│
├── knowledge_base/documents/   # 6 .txt financial education documents
│
├── templates/                  # 14 Jinja2 templates
└── static/css, js, images
```

---

## 4. Installation

### Prerequisites

- Python 3.10 or newer
- VS Code (or any editor)

### Step-by-step

```bash
# 1. Open the project folder
cd AI_Investment_Portfolio_Management

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create your .env from the template
# Windows:
copy .env.example .env
# macOS / Linux:
cp .env.example .env
```

Open `.env` and set `SECRET_KEY` to any random string. Everything else can stay blank — the app runs fully without any API key.

---

## 5. Database initialization

**No manual step is required.** On first run, `app.py` automatically:

1. Creates `database/portfolio.db` and all 7 tables.
2. Loads `data/market_data.csv` into the `market_data` table (4,032 rows).
3. Chunks and indexes the 6 knowledge base documents.

To start completely fresh at any time, delete the database file and re-run:

```bash
# Windows:
del database\portfolio.db
# macOS / Linux:
rm database/portfolio.db

python app.py
```

### Optional: load a demo portfolio

```bash
python seed_data.py
```

Creates a demo account with 6 sample holdings across 5 sectors, which is enough to trigger concentration risk, drawdown, and anomaly detection immediately:

- **Email:** `demo@example.com`
- **Password:** `demo1234`

---

## 6. Running the application

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in a browser.

In VS Code you can also press **F5** (select "Python File") with `app.py` open.

---

## 7. Environment variables

All are defined in `.env.example`. None are required for the application to run.

| Variable | Required? | Purpose |
|---|---|---|
| `SECRET_KEY` | Recommended | Flask session signing. Use any random string. |
| `DATABASE_URL` | No | Defaults to `database/portfolio.db`. |
| `LLM_API_KEY` | No | Enables LLM-generated answers in the AI assistant and RAG. Without it, the app uses a documented extractive fallback. |
| `LLM_API_URL` | No | Defaults to the Anthropic Messages endpoint. |
| `LLM_MODEL` | No | Model name for the above. |
| `MARKET_DATA_API_KEY` | No | Enables live pricing. Without it, bundled historical data is used and labelled as such. |
| `MARKET_DATA_API_URL` | No | Endpoint for the above. |
| `CONCENTRATION_THRESHOLD_PERCENT` | No | Default `40`. |
| `DRAWDOWN_ALERT_THRESHOLD_PERCENT` | No | Default `-10`. |
| `ANOMALY_CONTAMINATION` | No | Default `0.05` (expected proportion of anomalies). |

**API keys are only ever read by the backend.** They are never sent to the browser and never appear in any template or JavaScript file.

---

## 8. AI setup

### Without an API key (default)

Everything works. The AI assistant answers portfolio questions through NL-to-SQL, and knowledge questions through RAG retrieval plus an **extractive** answer built from the actual retrieved chunks. The response is clearly labelled so nobody mistakes it for LLM-generated text.

### With an API key

Add to `.env`:

```
LLM_API_KEY=your-key-here
```

The same retrieval runs, but the retrieved context is passed to the LLM with a system prompt instructing it to answer *only* from that context, in plain language, with no personalized advice or guaranteed returns. If the API call fails, the app logs the failure and falls back — it does not crash and does not fabricate a response.

---

## 9. RAG setup

The knowledge base lives in `knowledge_base/documents/` as `.txt` files. Six are included: diversification, asset allocation, portfolio risk, drawdown, volatility, and stocks/bonds/ETFs.

**To add your own document:** drop a `.txt` file into that folder. Start it with a `Title:` line, for example:

```
Title: Compound Interest

Compound interest is ...
```

Then click **Re-index Documents** on the Knowledge Base page, or restart the app. The pipeline is:

```
.txt files → title extraction → 120-word chunks (20-word overlap)
  → TF-IDF vectorization (unigrams + bigrams, title-weighted)
  → cosine similarity search → top chunks → answer generation
```

The Knowledge Base page displays the retrieved chunks with their similarity scores, so the retrieval step is visible rather than hidden — useful for demonstrating that RAG is genuinely running.

---

## 10. Testing

An automated end-to-end script covers the main flows:

```bash
python smoke_test.py
```

It exercises registration, duplicate-email rejection, wrong-password rejection, login, all 10 protected pages, add/edit/delete holding, invalid-input rejection, the chart JSON APIs, concentration risk, alert generation, all three AI routing paths, knowledge search, and user isolation.

See **TESTING.md** for the full manual test-case table with expected and actual results.

---

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | The virtual environment isn't active. Re-run the activate command, then `pip install -r requirements.txt`. |
| `unable to open database file` | Make sure you run `python app.py` from the project root, and that the `database/` folder exists. |
| Charts are blank | You have no holdings yet. Add one, or run `python seed_data.py`. |
| "N/A" in the current price column | That symbol isn't in `data/market_data.csv`. Use one of: TCS, INFY, HDFCBANK, RELIANCE, NIFTYBEES, GOLDBEES, SBIN, TATAMOTORS. |
| No alerts appear | Click **Run Alert Check** on the Alerts page. If no thresholds are breached, no alerts are created — that is correct behaviour, not a bug. |
| AI answers say "No LLM API key configured" | Expected without a key. Set `LLM_API_KEY` in `.env` to enable LLM answers. |
| Port 5000 already in use | Change the port in the last line of `app.py`. |
| Want to start over | Delete `database/portfolio.db` and re-run `python app.py`. |

---

## 12. Known limitations

1. **Market data is historical/sample, not live.** It is generated by a seeded random walk in `scripts/generate_market_data.py` and labelled "historical" in the UI. The service layer has a documented integration point for a real API.
2. **Anomaly detection flags statistical deviation only.** Isolation Forest with `contamination=0.05` will always flag roughly 5% of observations by construction. It says nothing about future direction, and the UI says so explicitly.
3. **NL-to-SQL uses whitelisted templates, not free-form LLM SQL generation.** This was a deliberate security decision: it makes unsafe queries structurally impossible rather than relying on a model to behave. Questions outside the supported intents return a helpful message instead of a guessed query.
4. **RAG uses TF-IDF vectors, not neural embeddings.** This keeps the pipeline fully offline and reproducible with no embedding API. Retrieval quality is good for a small, well-separated corpus but would not scale to thousands of documents.
5. **The vector index is in-memory** and rebuilt at startup, so it is not shared across multiple worker processes.
6. **Drawdown is reconstructed from current holdings**, applied backwards over historical prices. It does not account for positions bought and sold in the past.
7. **No SELL transactions** — the transactions table supports the type, but the UI only creates BUY records when a holding is added.
8. **Development server only.** `app.run(debug=True)` is for local demonstration, not production deployment.

---

## 13. IEEE demonstration procedure

A 10-minute walkthrough that shows the functionality is real:

**Setup (before the demo)**

```bash
rm database/portfolio.db     # start clean
python seed_data.py          # demo@example.com / demo1234
python app.py
```

**1. Authentication is real (1 min)**
Register a brand-new account live. Try a mismatched password confirmation and a duplicate email to show validation. Log in.

**2. Data persistence is real (2 min)**
Add a holding: `TCS`, quantity `10`, buy price `3550`, sector `Technology`. Show the dashboard totals change. **Stop the server (Ctrl+C), restart it, log back in** — the holding is still there. This is the clearest proof the SQLite database is genuinely being written to.

**3. Calculations are real (1 min)**
On the Portfolio page, pick any row and verify by hand: `quantity × buy_price = investment value`, `quantity × current price = current value`, and the difference is the P/L shown. Edit the quantity and watch every dependent figure update.

**4. User isolation is real (1 min)**
Log out, log in as the demo account, show a completely different portfolio. Emphasise that every query is filtered by `user_id`.

**5. Risk engine is real (2 min)**
On the Risk Analysis page, show the concentration breach on Technology (40.67% against a 40% threshold). Then change `CONCENTRATION_THRESHOLD_PERCENT=25` in `.env`, restart, and reload — more sectors now breach. This proves the threshold is configuration-driven, not hard-coded. Show current drawdown, maximum drawdown, and the drawdown chart. Show the Isolation Forest anomaly results per symbol.

**6. Alerts are real (1 min)**
Go to Alerts, click **Run Alert Check**, and show alerts appearing that correspond exactly to the risk conditions from the previous step. Mark one as read.

**7. AI assistant is real (2 min)**
Ask three questions and point out the **route** label on each answer:
- "What is my total investment?" → route `sql` — cross-check the figure against the dashboard.
- "What is diversification?" → route `rag`.
- "Why is diversification relevant to my portfolio?" → route `hybrid` — the answer combines the user's actual sector concentration with retrieved knowledge.

**8. Safety is real (30 sec)**
On the Knowledge Base page, run a search and show the retrieved chunks with their similarity scores — proof that retrieval happened. Point out the disclaimer in the header, and explain the NL-to-SQL validator: SELECT-only, whitelisted tables, mandatory `user_id` filter.

**Anticipated question — "Is the market data live?"**
Answer honestly: no. It is bundled historical data, labelled as such in the UI, with a documented integration point in `market_data_service.py` for a real API. Faking it would have been the easier and worse choice.

---

## 14. Academic integrity note

Read the code before you present it. The viva questions will be about *why* the design choices were made — why whitelisted SQL templates instead of free-form LLM generation, why TF-IDF instead of neural embeddings, why thresholds live in configuration. Those rationales are documented in the docstrings at the top of each service file.
