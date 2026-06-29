from __future__ import annotations
import csv, shutil, sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator
from app.config import BACKUP_DIR, DATA_DIR, DB_PATH, GOAL_AMOUNT

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS transactions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, fund_name TEXT NOT NULL,
 fund_category TEXT NOT NULL, amount REAL NOT NULL CHECK(amount>=0), nav REAL NOT NULL CHECK(nav>0),
 units REAL NOT NULL CHECK(units>=0), investment_type TEXT NOT NULL CHECK(investment_type IN ('SIP','One-Time')),
 notes TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS goals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, target_amount REAL NOT NULL,
 monthly_investment REAL NOT NULL DEFAULT 500, current_amount REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS watchlist (
 id INTEGER PRIMARY KEY AUTOINCREMENT, fund_name TEXT NOT NULL, scheme_code TEXT, category TEXT DEFAULT 'Mutual Fund');
CREATE TABLE IF NOT EXISTS nav_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, scheme_code TEXT, fund_name TEXT NOT NULL, nav REAL NOT NULL, nav_date TEXT NOT NULL,
 UNIQUE(fund_name, nav_date));
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'info', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, read_at TEXT);
"""

def init_db(db_path: Path = DB_PATH) -> None:
    DATA_DIR.mkdir(exist_ok=True); BACKUP_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.execute("INSERT OR IGNORE INTO goals(name,target_amount,monthly_investment) VALUES(?,?,?)", ("₹30,000 Goal", GOAL_AMOUNT, 500))
        for name in ["Emergency Fund","House","Retirement","Education","Vacation"]:
            conn.execute("INSERT OR IGNORE INTO goals(name,target_amount,monthly_investment) VALUES(?,?,?)", (name, GOAL_AMOUNT, 1000))
        conn.commit()

@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    init_db(db_path)
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    try:
        yield conn; conn.commit()
    finally:
        conn.close()

def add_transaction(data: dict) -> None:
    units = float(data["amount"]) / float(data["nav"])
    with get_conn() as conn:
        conn.execute("""INSERT INTO transactions(date,fund_name,fund_category,amount,nav,units,investment_type,notes)
        VALUES(?,?,?,?,?,?,?,?)""", (str(data["date"]), data["fund_name"], data["fund_category"], float(data["amount"]), float(data["nav"]), units, data["investment_type"], data.get("notes", "")))

def update_transaction(tid: int, data: dict) -> None:
    units = float(data["amount"]) / float(data["nav"])
    with get_conn() as conn:
        conn.execute("""UPDATE transactions SET date=?, fund_name=?, fund_category=?, amount=?, nav=?, units=?, investment_type=?, notes=? WHERE id=?""",
                     (str(data["date"]), data["fund_name"], data["fund_category"], float(data["amount"]), float(data["nav"]), units, data["investment_type"], data.get("notes", ""), tid))

def delete_transaction(tid: int) -> None:
    with get_conn() as conn: conn.execute("DELETE FROM transactions WHERE id=?", (tid,))

def fetch_all(table: str) -> list[sqlite3.Row]:
    if table not in {"transactions","goals","watchlist","notifications","nav_history"}: raise ValueError("invalid table")
    with get_conn() as conn: return conn.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()

def export_transactions(path: Path) -> Path:
    rows = fetch_all("transactions")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["id","date","fund_name","fund_category","amount","nav","units","investment_type","notes"])
        for r in rows: w.writerow([r[k] for k in ["id","date","fund_name","fund_category","amount","nav","units","investment_type","notes"]])
    return path

def import_transactions(path: Path) -> int:
    count = 0
    with path.open(newline="", encoding="utf-8") as f, get_conn() as conn:
        for row in csv.DictReader(f):
            data = {k: row[k] for k in ["date","fund_name","fund_category","amount","nav","investment_type","notes"] if k in row}
            units = float(data["amount"]) / float(data["nav"])
            conn.execute("INSERT INTO transactions(date,fund_name,fund_category,amount,nav,units,investment_type,notes) VALUES(?,?,?,?,?,?,?,?)",
                         (data["date"], data["fund_name"], data["fund_category"], float(data["amount"]), float(data["nav"]), units, data.get("investment_type","One-Time"), data.get("notes","")))
            count += 1
    return count

def backup_database() -> Path:
    init_db(); dest = BACKUP_DIR / f"investment_assistant_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"; shutil.copy2(DB_PATH, dest); return dest

def restore_database(src: Path) -> None:
    DATA_DIR.mkdir(exist_ok=True); shutil.copy2(src, DB_PATH)
