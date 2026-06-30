# AI Personal Investment Assistant

A local-first Streamlit application for Indian mutual fund and index fund investors who want to invest toward a ₹30,000 goal in flexible ₹500 contributions or planned SIPs.

> Safety: this app never places trades, never stores banking passwords, and never guarantees profits. It analyzes, educates, tracks, reminds, and assists only.

## Features

- Dashboard with total goal, invested amount, current value, today's gain/loss, overall gain/loss, XIRR, CAGR, units, funds, allocation, and progress bar.
- Investment log with add, delete, CSV export, and CSV import support.
- Portfolio analytics: average buy NAV, units, current value, gain/loss, allocation, diversification score, monthly growth, SIP projections, and simple risk scoring.
- Market data service that fetches AMFI NAV data, caches it locally once daily, stores NAV history, snapshots portfolio value, and logs all refreshes.
- Notifications for missed monthly ₹500 investment reminders, 10% portfolio drawdowns from peak, and each ₹5,000 invested milestone.
- AI education assistant for SIPs, index funds, mutual funds, risk, diversification, taxes, withdrawals, crashes, and long-term investing.
- Goal planner, SIP planner, watchlist, PDF reports, settings, local SQLite storage, database backup/restore helpers.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Tests

```bash
pytest
```

## Architecture

```text
app/
  analytics.py          # Portfolio, SIP, XIRR, CAGR, and risk calculations
  ai_assistant.py       # Rule-based educational assistant with safety guardrails
  config.py             # App constants and paths
  database.py           # SQLite schema, CRUD, CSV, backup/restore
  main.py               # Streamlit UI pages
  models.py             # Dataclasses
  reports.py            # PDF report generation
  scheduler.py          # APScheduler daily update entry point
  services/tracker.py   # NAV refresh, snapshots, update logs, notifications
  services/nav_service.py # AMFI NAV fetch/cache helper
```

Data is stored locally in `data/investment_assistant.sqlite3`; generated reports go to `reports/`; backups go to `backups/`.

## Daily automation

Run a one-off update:

```bash
python -c "from app.scheduler import run_daily_update; run_daily_update()"
```

Or import `start_background_scheduler()` from `app.scheduler` in a long-running process to refresh NAVs daily at 18:00 Asia/Kolkata. The Streamlit sidebar also has a manual `Refresh NAVs now` button.

## Phased roadmap

1. Core portfolio tracker and transactions.
2. Analytics, goals, SIP planner, and watchlist.
3. AI educational assistant and smart notification rules.
4. Richer PDF reports, screenshots, and automated local backups.

## Security boundaries

- No brokerage integrations.
- No automated trade execution.
- No banking passwords.
- Personal data remains local by default.
