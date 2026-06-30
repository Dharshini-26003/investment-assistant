from __future__ import annotations
from datetime import date
import pandas as pd
from app.database import get_conn

def evaluate_notifications(total_invested: float, current_value: float, peak_value: float | None = None, transactions: pd.DataFrame | None = None) -> list[tuple[str, str, str]]:
    messages: list[tuple[str, str, str]] = []
    today = date.today()
    monthly_done = False
    if transactions is not None and not transactions.empty:
        tx = transactions.copy()
        tx["date"] = pd.to_datetime(tx["date"])
        monthly_done = not tx[(tx["date"].dt.year == today.year) & (tx["date"].dt.month == today.month)].empty
    if today.day >= 25 and not monthly_done:
        messages.append((f"monthly-{today:%Y-%m}", "warning", "Monthly ₹500 investment reminder: no investment is logged for this month."))
    milestone = int(total_invested // 5000) * 5000
    if milestone and total_invested >= milestone:
        messages.append((f"milestone-{milestone}", "success", f"Goal milestone reached: ₹{milestone:,.0f} invested."))
    if peak_value and current_value > peak_value:
        messages.append((f"peak-{today:%Y-%m-%d}", "success", "Portfolio reached a new all-time high."))
    if peak_value and peak_value > 0:
        drawdown = (peak_value - current_value) / peak_value
        if drawdown >= 0.10:
            messages.append((f"drawdown-{today:%Y-%m-%d}", "warning", f"Portfolio is down {drawdown:.1%} from its peak. Review calmly; this is not a trade instruction."))
    return messages

def persist_notifications(messages: list[tuple[str, str, str]]) -> None:
    with get_conn() as conn:
        for key, severity, message in messages:
            conn.execute("INSERT OR IGNORE INTO notifications(message,severity,notification_key) VALUES(?,?,?)", (message, severity, key))
