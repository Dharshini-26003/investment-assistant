from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from app import ai_assistant
from app.analytics import monthly_growth, portfolio_summary, profit_history, risk_score, sip_projection, today_change
from app.config import APP_NAME, DEFAULT_INVESTMENT, DISCLAIMER, GOAL_AMOUNT
from app.database import (
    add_transaction,
    backup_database,
    delete_transaction,
    export_transactions,
    fetch_all,
    get_conn,
    get_setting,
    init_db,
    latest_navs,
    peak_portfolio_value,
    previous_navs,
    save_portfolio_snapshot,
)
from app.reports import generate_pdf_report
from app.services.notifications import evaluate_notifications
from app.services.tracker import refresh_navs_for_portfolio, update_portfolio_tracking

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def rows_df(table: str) -> pd.DataFrame:
    return pd.DataFrame([dict(r) for r in fetch_all(table)])


def load_summary() -> tuple[pd.DataFrame, dict]:
    tx = rows_df("transactions")
    latest = latest_navs()
    summary = portfolio_summary(tx, latest)
    summary["today_change"] = today_change(tx, latest, previous_navs())
    if not tx.empty:
        save_portfolio_snapshot(date.today(), summary["total_invested"], summary["current_value"])
    return tx, summary


def money(value: float) -> str:
    return f"₹{value:,.2f}"


def pct(value: float) -> str:
    return f"{value:,.2f}%"


@contextmanager
def page_guard(page_name: str):
    log.info("Rendering Streamlit page: %s", page_name)
    try:
        yield
        log.info("Rendered Streamlit page: %s", page_name)
    except Exception as exc:
        log.exception("Failed rendering Streamlit page: %s", page_name)
        st.error(f"{page_name} could not be rendered. The exception is shown below and logged.")
        st.exception(exc)


def render_dashboard(summary: dict) -> None:
    st.title("Dashboard")
    cols = st.columns(4)
    metrics = [
        ("Total Goal", GOAL_AMOUNT, money),
        ("Total Invested", summary["total_invested"], money),
        ("Current Portfolio Value", summary["current_value"], money),
        ("Today's Gain/Loss", summary["today_change"], money),
        ("Overall Gain/Loss", summary["unrealized_pl"], money),
        ("Overall Return", summary["return_pct"], pct),
        ("XIRR", summary["xirr"], pct),
        ("CAGR", summary["cagr"], pct),
        ("Total Units", summary["total_units"], lambda v: f"{v:,.4f}"),
        ("Number of Funds", summary["fund_count"], lambda v: f"{v:,.0f}"),
    ]
    for idx, (label, value, formatter) in enumerate(metrics):
        cols[idx % 4].metric(label, formatter(value))
    st.progress(min(summary["total_invested"] / GOAL_AMOUNT, 1.0), text=f"Progress toward {money(GOAL_AMOUNT)}")
    if summary["allocation"]:
        st.plotly_chart(
            px.pie(names=list(summary["allocation"].keys()), values=list(summary["allocation"].values()), title="Portfolio Allocation"),
            width="stretch",
        )
    st.info("The app tracks and educates only. It never buys or sells investments.")


def render_transactions(tx: pd.DataFrame) -> None:
    st.title("Investment Log")
    with st.form("tx_form"):
        c1, c2, c3 = st.columns(3)
        data = {
            "date": c1.date_input("Date", date.today()),
            "fund_name": c2.text_input("Fund Name"),
            "fund_category": c3.selectbox("Fund Category", ["Index Equity", "Equity", "Debt", "Hybrid", "Liquid", "Other"]),
            "amount": c1.number_input("Amount", min_value=0.0, value=DEFAULT_INVESTMENT),
            "nav": c2.number_input("NAV", min_value=0.01, value=100.0),
            "investment_type": c3.selectbox("SIP or One-Time", ["SIP", "One-Time"]),
            "notes": st.text_area("Notes"),
        }
        if st.form_submit_button("Add Investment") and data["fund_name"]:
            add_transaction(data)
            st.success("Investment recorded. Refreshing...")
            st.rerun()

    st.dataframe(tx, width="stretch")
    if not tx.empty:
        delete_id = st.number_input("Delete transaction ID", min_value=0, step=1)
        if st.button("Delete") and delete_id:
            delete_transaction(delete_id)
            st.rerun()
        try:
            csv_path = export_transactions(Path("data/transactions_export.csv"))
            st.download_button("Export CSV", csv_path.read_bytes(), "transactions.csv")
        except Exception as exc:
            log.exception("CSV export failed")
            st.error("CSV export failed.")
            st.exception(exc)

    upload = st.file_uploader("Import CSV", type="csv")
    if upload:
        try:
            from app.database import import_transactions

            path = Path("data/upload.csv")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(upload.getvalue())
            st.success(f"Imported {import_transactions(path)} rows")
            st.rerun()
        except Exception as exc:
            log.exception("CSV import failed")
            st.error("CSV import failed.")
            st.exception(exc)


def render_portfolio(summary: dict) -> None:
    st.title("Portfolio")
    st.dataframe(pd.DataFrame(summary.get("funds", [])), width="stretch")
    st.json({"average_purchase_price": summary["avg_nav"], "allocation": summary["allocation"]})


def render_analytics(tx: pd.DataFrame, summary: dict) -> None:
    st.title("Portfolio Analytics")
    mg = monthly_growth(tx)
    if not mg.empty:
        st.plotly_chart(px.bar(mg, x="month", y="amount", title="Monthly Investments"), width="stretch")

    snapshots = rows_df("portfolio_snapshots")
    ph = profit_history(snapshots)
    if not ph.empty:
        st.plotly_chart(px.line(ph, x="snapshot_date", y="current_value", title="Portfolio Value History"), width="stretch")
        st.plotly_chart(px.line(ph, x="snapshot_date", y="profit_loss", title="Profit/Loss History"), width="stretch")

    if summary["allocation"]:
        st.plotly_chart(
            px.bar(
                x=list(summary["allocation"].keys()),
                y=list(summary["allocation"].values()),
                labels={"x": "Fund", "y": "Allocation %"},
                title="Allocation by Fund",
            ),
            width="stretch",
        )
    cat_alloc = tx.groupby("fund_category")["amount"].sum().pipe(lambda s: (s / s.sum() * 100).to_dict()) if not tx.empty else {}
    st.write("Risk Analysis", risk_score(summary, cat_alloc))
    st.write("Diversification Score", summary["diversification_score"])


def render_goals() -> None:
    st.title("Goal Planner")
    st.dataframe(rows_df("goals"), width="stretch")
    target = st.number_input("Target Amount", value=GOAL_AMOUNT)
    monthly = st.number_input("Planned Monthly Investment", value=500.0)
    months = int(target / monthly) if monthly else 0
    st.info(f"Estimated completion: about {months} months (ignores returns).")


def render_sip_planner() -> None:
    st.title("SIP Planner")
    monthly = st.selectbox("Monthly SIP", [500, 1000, 2000, "Custom"])
    amount = st.number_input("Custom amount", value=500.0) if monthly == "Custom" else float(monthly)
    rate = st.slider("Assumed annual return (hypothetical, not guaranteed)", 0.0, 15.0, 10.0)
    st.dataframe(pd.DataFrame([sip_projection(amount, years, rate) for years in [5, 10, 15, 20]]), width="stretch")


def render_reports(tx: pd.DataFrame, summary: dict) -> None:
    st.title("Reports")
    period = st.selectbox("Report period", ["Monthly", "Quarterly", "Yearly"])
    if st.button("Generate PDF Report"):
        try:
            path = generate_pdf_report(summary, period)
            st.success(f"Report generated: {path}")
            st.download_button("Download", path.read_bytes(), path.name)
        except Exception as exc:
            log.exception("PDF report generation failed")
            st.error("PDF report generation failed.")
            st.exception(exc)
    st.subheader("Monthly Investment Summary")
    st.dataframe(monthly_growth(tx), width="stretch")


def render_watchlist() -> None:
    st.title("Watchlist")
    with get_conn() as conn:
        name = st.text_input("Fund name")
        code = st.text_input("Scheme code (optional)")
        if st.button("Add to Watchlist") and name:
            conn.execute("INSERT INTO watchlist(fund_name,scheme_code) VALUES(?,?)", (name, code))
            conn.commit()
            st.rerun()
    st.dataframe(rows_df("watchlist"), width="stretch")


def render_ai_assistant() -> None:
    st.title("AI Investment Assistant")
    question = st.text_input("Ask about SIPs, index funds, risk, taxes, diversification...")
    if question:
        try:
            st.write(ai_assistant.answer(question))
        except Exception as exc:
            log.exception("AI assistant response failed")
            st.error("AI assistant response failed.")
            st.exception(exc)


def render_settings() -> None:
    st.title("Settings")
    st.write("Currency: INR")
    st.toggle("Dark Mode preference", value=False)
    if st.button("Backup Database"):
        try:
            st.success(f"Backup created: {backup_database()}")
        except Exception as exc:
            log.exception("Database backup failed")
            st.error("Database backup failed.")
            st.exception(exc)
    st.subheader("Update Logs")
    st.dataframe(rows_df("update_logs"), width="stretch")
    st.warning("No banking passwords. No automated buy/sell/trade execution. Data stays local by default.")


def run_app() -> None:
    st.set_page_config(APP_NAME, page_icon="₹", layout="wide")
    init_db()

    st.sidebar.title("₹ Investment Assistant")
    page = st.sidebar.radio(
        "Pages",
        ["Dashboard", "Portfolio", "Transactions", "Goals", "SIP Planner", "Analytics", "Reports", "Watchlist", "AI Assistant", "Settings"],
    )
    st.sidebar.caption(DISCLAIMER)

    try:
        tx, summary = load_summary()
    except Exception as exc:
        log.exception("Failed loading portfolio summary")
        st.error("Portfolio summary could not be loaded. The exception is shown below and logged.")
        st.exception(exc)
        tx = pd.DataFrame()
        summary = portfolio_summary(tx)

    try:
        peak = peak_portfolio_value()
        for _, severity, note in evaluate_notifications(summary["total_invested"], summary["current_value"], peak, tx):
            getattr(st.sidebar, severity if severity in {"info", "success", "warning", "error"} else "info")(note)
    except Exception as exc:
        log.exception("Notification evaluation failed")
        st.sidebar.error("Notifications could not be evaluated.")
        st.sidebar.exception(exc)

    last_refresh = get_setting("last_nav_refresh", "Never")
    st.sidebar.caption(f"Last NAV refresh: {last_refresh}")
    if st.sidebar.button("Refresh NAVs now"):
        try:
            refresh_navs_for_portfolio()
            update_portfolio_tracking()
            st.sidebar.success("NAVs and portfolio tracking updated.")
            st.rerun()
        except Exception as exc:
            log.exception("Manual NAV refresh failed")
            st.sidebar.error("NAV refresh failed.")
            st.sidebar.exception(exc)

    with page_guard(page):
        if page == "Dashboard":
            render_dashboard(summary)
        elif page == "Transactions":
            render_transactions(tx)
        elif page == "Portfolio":
            render_portfolio(summary)
        elif page == "Analytics":
            render_analytics(tx, summary)
        elif page == "Goals":
            render_goals()
        elif page == "SIP Planner":
            render_sip_planner()
        elif page == "Reports":
            render_reports(tx, summary)
        elif page == "Watchlist":
            render_watchlist()
        elif page == "AI Assistant":
            render_ai_assistant()
        elif page == "Settings":
            render_settings()
        else:
            st.error(f"Unknown page: {page}")


if __name__ == "__main__":
    run_app()
