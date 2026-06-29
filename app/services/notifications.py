from __future__ import annotations
from datetime import date
from app.database import get_conn

def evaluate_notifications(total_invested: float, current_value: float, peak_value: float | None = None) -> list[str]:
    messages: list[str] = []
    today = date.today()
    if today.day >= 25:
        messages.append("Monthly SIP review is due. Add your planned investment only if you choose to invest.")
    if total_invested and int(total_invested // 5000) > int((total_invested - 500) // 5000):
        messages.append("Goal milestone reached: another ₹5,000 milestone has been crossed.")
    if peak_value and current_value > peak_value:
        messages.append("Portfolio reached a new all-time high.")
    if peak_value and peak_value > 0:
        drawdown = (peak_value - current_value) / peak_value
        for threshold in (0.10, 0.20, 0.30):
            if drawdown >= threshold:
                messages.append(f"Portfolio is down {threshold:.0%} from its peak. Review calmly; this is not a trade instruction.")
                break
    if today.month == 12:
        messages.append("Annual portfolio review is due: revisit goals, allocation, risk, and tax records.")
    return messages

def persist_notifications(messages: list[str]) -> None:
    with get_conn() as conn:
        for message in messages:
            conn.execute("INSERT INTO notifications(message,severity) VALUES(?,?)", (message, "info"))
