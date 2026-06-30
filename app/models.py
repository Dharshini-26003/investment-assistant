from __future__ import annotations
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class Transaction:
    id: int | None
    date: date
    fund_name: str
    fund_category: str
    amount: float
    nav: float
    units: float
    investment_type: str
    notes: str = ""

@dataclass(frozen=True)
class Goal:
    id: int | None
    name: str
    target_amount: float
    monthly_investment: float
    current_amount: float = 0.0

@dataclass(frozen=True)
class WatchlistItem:
    id: int | None
    fund_name: str
    scheme_code: str | None = None
    category: str = "Mutual Fund"

@dataclass(frozen=True)
class PortfolioSnapshot:
    id: int | None
    snapshot_date: date
    total_invested: float
    current_value: float
    profit_loss: float
