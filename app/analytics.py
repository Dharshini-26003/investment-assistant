from __future__ import annotations
from datetime import datetime
import numpy as np
import pandas as pd
from scipy.optimize import newton


def xirr(cashflows: list[tuple[str, float]]) -> float:
    if len(cashflows) < 2: return 0.0
    dates = [datetime.fromisoformat(d).date() for d, _ in cashflows]
    start = dates[0]
    def npv(rate: float) -> float:
        return sum(v / ((1 + rate) ** ((d - start).days / 365.0)) for d, (_, v) in zip(dates, cashflows))
    try: return float(newton(npv, 0.1))
    except Exception: return 0.0


def cagr(initial: float, final: float, years: float) -> float:
    if initial <= 0 or final <= 0 or years <= 0: return 0.0
    return (final / initial) ** (1 / years) - 1


def _weighted_average_nav(nav_values: pd.Series, units: pd.Series) -> float:
    total_units = float(units.sum())
    if total_units <= 0:
        return float(nav_values.mean()) if not nav_values.empty else 0.0
    return float(np.average(nav_values, weights=units))

def portfolio_summary(transactions: pd.DataFrame, navs: dict[str, float] | None = None) -> dict:
    if transactions.empty:
        return {"total_invested":0,"current_value":0,"unrealized_pl":0,"realized_pl":0,"return_pct":0,"today_change":0,"total_units":0,"fund_count":0,"allocation":{},"avg_nav":{},"diversification_score":0}
    navs = navs or {}
    df = transactions.copy(); df["amount"] = pd.to_numeric(df["amount"]); df["units"] = pd.to_numeric(df["units"]); df["nav"] = pd.to_numeric(df["nav"])
    grouped = df.groupby("fund_name").agg(
        amount=("amount", "sum"),
        units=("units", "sum"),
        category=("fund_category", "last"),
        avg_nav=("nav", lambda s: _weighted_average_nav(s, df.loc[s.index, "units"])),
    ).reset_index()
    grouped["current_nav"] = grouped.apply(lambda r: float(navs.get(r["fund_name"], r["avg_nav"])), axis=1)
    grouped["current_value"] = grouped["units"] * grouped["current_nav"]
    total_invested = float(grouped["amount"].sum()); current_value = float(grouped["current_value"].sum())
    allocation = (grouped.set_index("fund_name")["current_value"] / current_value * 100).round(2).to_dict() if current_value else {}
    concentration = max(allocation.values()) if allocation else 0
    score = max(0, min(100, 100 - concentration + min(len(allocation)*8, 40)))
    return {"total_invested":total_invested,"current_value":current_value,"unrealized_pl":current_value-total_invested,"realized_pl":0.0,"return_pct":((current_value-total_invested)/total_invested*100 if total_invested else 0),"today_change":0.0,"total_units":float(grouped["units"].sum()),"fund_count":int(grouped.shape[0]),"allocation":allocation,"avg_nav":grouped.set_index("fund_name")["avg_nav"].round(4).to_dict(),"diversification_score":round(score, 1),"funds":grouped.to_dict("records")}


def monthly_growth(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty: return pd.DataFrame(columns=["month","amount"])
    df=transactions.copy(); df["date"]=pd.to_datetime(df["date"]); df["month"]=df["date"].dt.to_period("M").astype(str)
    return df.groupby("month", as_index=False)["amount"].sum()


def sip_projection(monthly: float, years: int, annual_return: float) -> dict:
    months=years*12; r=annual_return/12/100
    fv = monthly*months if r == 0 else monthly*(((1+r)**months-1)/r)*(1+r)
    return {"years":years,"invested":monthly*months,"projected_value":fv,"estimated_gain":fv-monthly*months}


def risk_score(summary: dict, category_allocation: dict[str, float]) -> dict:
    equity = sum(v for k,v in category_allocation.items() if "equity" in k.lower() or "index" in k.lower())
    debt = sum(v for k,v in category_allocation.items() if "debt" in k.lower() or "liquid" in k.lower())
    concentration = max(summary.get("allocation", {}).values(), default=0)
    score = min(100, concentration*0.5 + equity*0.4 + (100-summary.get("diversification_score",0))*0.3)
    return {"concentration":concentration,"equity_allocation":equity,"debt_allocation":debt,"volatility_score":round(equity*0.8+concentration*0.2,1),"risk_score":round(score,1)}
