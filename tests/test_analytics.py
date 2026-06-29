import pandas as pd
from app.analytics import portfolio_summary, sip_projection, xirr

def test_portfolio_summary_basic():
    df = pd.DataFrame([
        {"date":"2026-01-01","fund_name":"Fund A","fund_category":"Index Equity","amount":500,"nav":100,"units":5,"investment_type":"SIP"},
        {"date":"2026-02-01","fund_name":"Fund A","fund_category":"Index Equity","amount":500,"nav":125,"units":4,"investment_type":"SIP"},
    ])
    s = portfolio_summary(df, {"Fund A":150})
    assert s["total_invested"] == 1000
    assert s["current_value"] == 1350
    assert round(s["return_pct"], 2) == 35.0

def test_sip_projection_no_return():
    assert sip_projection(500, 5, 0)["invested"] == 30000
    assert sip_projection(500, 5, 0)["projected_value"] == 30000

def test_xirr_empty_safe():
    assert xirr([]) == 0.0

def test_portfolio_summary_zero_unit_fund_uses_mean_nav_safely():
    df = pd.DataFrame([
        {"date":"2026-01-01","fund_name":"Zero Unit Fund","fund_category":"Other","amount":0,"nav":100,"units":0,"investment_type":"One-Time"},
        {"date":"2026-02-01","fund_name":"Zero Unit Fund","fund_category":"Other","amount":0,"nav":120,"units":0,"investment_type":"One-Time"},
    ])
    s = portfolio_summary(df)
    assert s["avg_nav"]["Zero Unit Fund"] == 110
    assert s["current_value"] == 0
