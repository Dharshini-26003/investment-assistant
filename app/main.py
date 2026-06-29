from __future__ import annotations
import logging
from datetime import date
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from app import ai_assistant
from app.analytics import monthly_growth, portfolio_summary, risk_score, sip_projection
from app.config import APP_NAME, DEFAULT_INVESTMENT, DISCLAIMER, GOAL_AMOUNT
from app.database import add_transaction, backup_database, delete_transaction, export_transactions, fetch_all, get_conn, init_db
from app.reports import generate_pdf_report
from app.services.nav_service import fetch_amfi_navs, find_nav
from app.services.notifications import evaluate_notifications

logging.basicConfig(level=logging.INFO)
st.set_page_config(APP_NAME, page_icon="₹", layout="wide")
init_db()

def rows_df(table: str) -> pd.DataFrame:
    return pd.DataFrame([dict(r) for r in fetch_all(table)])

def load_summary() -> tuple[pd.DataFrame, dict]:
    tx = rows_df("transactions")
    navs_raw = fetch_amfi_navs()
    latest = {f: find_nav(f, navs_raw) for f in tx.get("fund_name", pd.Series(dtype=str)).unique()} if not tx.empty else {}
    latest = {k:v for k,v in latest.items() if v}
    return tx, portfolio_summary(tx, latest)

def money(v: float) -> str: return f"₹{v:,.2f}"

st.sidebar.title("₹ Investment Assistant")
page = st.sidebar.radio("Pages", ["Dashboard","Portfolio","Transactions","Goals","SIP Planner","Analytics","Reports","Watchlist","AI Assistant","Settings"])
st.sidebar.caption(DISCLAIMER)

tx, summary = load_summary()
for note in evaluate_notifications(summary["total_invested"], summary["current_value"]):
    st.sidebar.info(note)

if page == "Dashboard":
    st.title("Dashboard")
    cols = st.columns(4)
    metrics = [("Total Goal", GOAL_AMOUNT),("Total Invested", summary["total_invested"]),("Remaining Goal", max(GOAL_AMOUNT-summary["total_invested"],0)),("Current Portfolio Value", summary["current_value"]),("Unrealized P/L", summary["unrealized_pl"]),("Realized P/L", summary["realized_pl"]),("Overall Return %", summary["return_pct"]),("Today's Change", summary["today_change"]),("Total Units", summary["total_units"]),("Number of Funds", summary["fund_count"])]
    for i,(label,val) in enumerate(metrics): cols[i%4].metric(label, f"{val:,.2f}" if "%" in label or "Units" in label or "Funds" in label else money(val))
    st.progress(min(summary["total_invested"] / GOAL_AMOUNT, 1.0), text=f"Progress toward {money(GOAL_AMOUNT)}")
    if summary["allocation"]: st.plotly_chart(px.pie(names=list(summary["allocation"].keys()), values=list(summary["allocation"].values()), title="Portfolio Allocation"), use_container_width=True)
    st.info("The app tracks and educates only. It never buys or sells investments.")

elif page == "Transactions":
    st.title("Investment Log")
    with st.form("tx_form"):
        c1,c2,c3 = st.columns(3)
        data = {"date": c1.date_input("Date", date.today()), "fund_name": c2.text_input("Fund Name"), "fund_category": c3.selectbox("Fund Category", ["Index Equity","Equity","Debt","Hybrid","Liquid","Other"]), "amount": c1.number_input("Amount", min_value=0.0, value=DEFAULT_INVESTMENT), "nav": c2.number_input("NAV", min_value=0.01, value=100.0), "investment_type": c3.selectbox("SIP or One-Time", ["SIP","One-Time"]), "notes": st.text_area("Notes")}
        if st.form_submit_button("Add Investment") and data["fund_name"]:
            add_transaction(data); st.success("Investment recorded. Refreshing..."); st.rerun()
    st.dataframe(tx, use_container_width=True)
    if not tx.empty:
        delete_id = st.number_input("Delete transaction ID", min_value=0, step=1)
        if st.button("Delete") and delete_id: delete_transaction(delete_id); st.rerun()
        csv_path = export_transactions(Path("data/transactions_export.csv")); st.download_button("Export CSV", csv_path.read_bytes(), "transactions.csv")
    upload = st.file_uploader("Import CSV", type="csv")
    if upload:
        p=Path("data/upload.csv"); p.write_bytes(upload.getvalue()); from app.database import import_transactions; st.success(f"Imported {import_transactions(p)} rows"); st.rerun()

elif page == "Portfolio":
    st.title("Portfolio")
    st.dataframe(pd.DataFrame(summary.get("funds", [])), use_container_width=True)
    st.json({"average_buy_nav": summary["avg_nav"], "allocation": summary["allocation"]})

elif page == "Analytics":
    st.title("Portfolio Analytics")
    mg = monthly_growth(tx)
    if not mg.empty: st.plotly_chart(px.bar(mg, x="month", y="amount", title="Monthly Investments"), use_container_width=True)
    cat_alloc = tx.groupby("fund_category")["amount"].sum().pipe(lambda s: (s/s.sum()*100).to_dict()) if not tx.empty else {}
    st.write("Risk Analysis", risk_score(summary, cat_alloc))
    st.write("Diversification Score", summary["diversification_score"])

elif page == "Goals":
    st.title("Goal Planner")
    goals = rows_df("goals"); st.dataframe(goals, use_container_width=True)
    target = st.number_input("Target Amount", value=GOAL_AMOUNT); monthly = st.number_input("Planned Monthly Investment", value=500.0)
    months = int(target / monthly) if monthly else 0; st.info(f"Estimated completion: about {months} months (ignores returns).")

elif page == "SIP Planner":
    st.title("SIP Planner")
    monthly = st.selectbox("Monthly SIP", [500,1000,2000,"Custom"]); amount = st.number_input("Custom amount", value=500.0) if monthly == "Custom" else float(monthly)
    rate = st.slider("Assumed annual return (hypothetical, not guaranteed)", 0.0, 15.0, 10.0)
    st.dataframe(pd.DataFrame([sip_projection(amount, y, rate) for y in [5,10,15,20]]), use_container_width=True)

elif page == "Reports":
    st.title("Reports")
    period = st.selectbox("Report period", ["Monthly","Quarterly","Yearly"])
    if st.button("Generate PDF Report"):
        path = generate_pdf_report(summary, period); st.success(f"Report generated: {path}"); st.download_button("Download", path.read_bytes(), path.name)

elif page == "Watchlist":
    st.title("Watchlist")
    with get_conn() as conn:
        name = st.text_input("Fund name"); code = st.text_input("Scheme code (optional)")
        if st.button("Add to Watchlist") and name:
            conn.execute("INSERT INTO watchlist(fund_name,scheme_code) VALUES(?,?)", (name, code))
            conn.commit()
            st.rerun()
    wl = rows_df("watchlist"); st.dataframe(wl, use_container_width=True)

elif page == "AI Assistant":
    st.title("AI Investment Assistant")
    q = st.text_input("Ask about SIPs, index funds, risk, taxes, diversification...")
    if q: st.write(ai_assistant.answer(q))

elif page == "Settings":
    st.title("Settings")
    st.write("Currency: INR")
    st.toggle("Dark Mode preference", value=False)
    if st.button("Backup Database"): st.success(f"Backup created: {backup_database()}")
    st.warning("No banking passwords. No automated buy/sell/trade execution. Data stays local by default.")
