from __future__ import annotations
from app.config import DISCLAIMER
TOPICS = {
 "sip": "A SIP invests a fixed amount regularly, helping discipline and rupee-cost averaging. Returns are market-linked, not guaranteed.",
 "index": "Index funds try to mirror an index such as Nifty 50. They are usually diversified and low cost, but still fluctuate with markets.",
 "mutual": "A mutual fund pools investor money and invests according to its mandate. Check risk, category, costs, and time horizon.",
 "crash": "Market crashes are sharp declines. Long-term investors usually review goals, avoid panic decisions, and maintain emergency funds.",
 "risk": "Risk is uncertainty in returns, including volatility, concentration, liquidity, and behavior risk.",
 "diversification": "Diversification spreads money across funds/categories to reduce dependence on one holding.",
 "expense": "Expense ratio is the annual fund-management cost deducted from returns. Lower costs can help over long periods.",
 "tax": "Indian mutual fund taxation depends on asset class and holding period. Verify current rules with a tax professional.",
 "withdraw": "Plan withdrawals around goals, taxes, exit loads, and market conditions. Avoid withdrawing emergency money from volatile assets.",
 "long": "Long-term investing gives compounding more time, but outcomes are not guaranteed and require suitable asset allocation."
}

def answer(question: str) -> str:
    q = question.lower()
    for key, text in TOPICS.items():
        if key in q:
            return f"{text}\n\nSafety note: {DISCLAIMER}"
    return "I can explain SIPs, index funds, mutual funds, risk, diversification, crashes, expenses, taxes, withdrawals, and long-term investing in simple terms. I will not guarantee profits or tell you to place trades."
