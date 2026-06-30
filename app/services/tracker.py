from __future__ import annotations

from datetime import date

import pandas as pd

from app.analytics import portfolio_summary, today_change
from app.database import (
    fetch_all,
    latest_navs,
    log_update,
    peak_portfolio_value,
    previous_navs,
    save_nav_history,
    save_portfolio_snapshot,
    upsert_setting,
)
from app.services.nav_service import fetch_amfi_navs, find_nav_item
from app.services.notifications import evaluate_notifications, persist_notifications


def transactions_df() -> pd.DataFrame:
    return pd.DataFrame([dict(r) for r in fetch_all("transactions")])


def refresh_navs_for_portfolio() -> dict[str, float]:
    tx = transactions_df()
    if tx.empty:
        log_update("nav_refresh", "skipped", "No transactions to refresh.")
        return {}

    navs_raw = fetch_amfi_navs()
    items: list[dict] = []
    latest: dict[str, float] = {}
    for fund_name in sorted(tx["fund_name"].dropna().unique()):
        item = find_nav_item(fund_name, navs_raw)
        if item:
            items.append(
                {
                    "scheme_code": item.get("scheme_code"),
                    "fund_name": fund_name,
                    "nav": item["nav"],
                    "nav_date": item["date"],
                }
            )
            latest[fund_name] = float(item["nav"])

    saved = save_nav_history(items)
    upsert_setting("last_nav_refresh", str(date.today()))
    log_update("nav_refresh", "success", f"Matched {len(items)} funds and saved {saved} NAV rows.")
    return latest


def update_portfolio_tracking() -> dict:
    tx = transactions_df()
    navs = latest_navs() or refresh_navs_for_portfolio()
    summary = portfolio_summary(tx, navs)
    summary["today_change"] = today_change(tx, navs, previous_navs())
    save_portfolio_snapshot(date.today(), summary["total_invested"], summary["current_value"])
    peak_value = peak_portfolio_value()
    notes = evaluate_notifications(summary["total_invested"], summary["current_value"], peak_value, tx)
    persist_notifications(notes)
    log_update("portfolio_update", "success", "Portfolio value, snapshot, and notifications updated.")
    return summary
