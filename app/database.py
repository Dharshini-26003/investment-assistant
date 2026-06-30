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
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'info', notification_key TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, read_at TEXT, UNIQUE(notification_key));
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
 id INTEGER PRIMARY KEY AUTOINCREMENT, snapshot_date TEXT NOT NULL UNIQUE, total_invested REAL NOT NULL,
 current_value REAL NOT NULL, profit_loss REAL NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS update_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""

def init_db(db_path: Path = DB_PATH) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True); BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate_existing_schema(conn)
        conn.execute("INSERT OR IGNORE INTO goals(name,target_amount,monthly_investment) VALUES(?,?,?)", ("₹30,000 Goal", GOAL_AMOUNT, 500))
        for name in ["Emergency Fund","House","Retirement","Education","Vacation"]:
            conn.execute("INSERT OR IGNORE INTO goals(name,target_amount,monthly_investment) VALUES(?,?,?)", (name, GOAL_AMOUNT, 1000))
        conn.commit()

def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

def _migrate_existing_schema(conn: sqlite3.Connection) -> None:
    notification_columns = _table_columns(conn, "notifications")
    if "notification_key" not in notification_columns:
        conn.execute("ALTER TABLE notifications ADD COLUMN notification_key TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_key ON notifications(notification_key) WHERE notification_key IS NOT NULL")

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
    if table not in {"transactions","goals","watchlist","notifications","nav_history","portfolio_snapshots","update_logs"}: raise ValueError("invalid table")
    with get_conn() as conn: return conn.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()

def upsert_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

def get_setting(key: str, default: str | None = None) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def log_update(event_type: str, status: str, message: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT INTO update_logs(event_type,status,message) VALUES(?,?,?)", (event_type, status, message))

def save_nav_history(items: list[dict]) -> int:
    saved = 0
    with get_conn() as conn:
        for item in items:
            before = conn.total_changes
            conn.execute(
                "INSERT OR IGNORE INTO nav_history(scheme_code,fund_name,nav,nav_date) VALUES(?,?,?,?)",
                (item.get("scheme_code"), item["fund_name"], float(item["nav"]), item["nav_date"]),
            )
            saved += int(conn.total_changes > before)
    return saved

def latest_navs() -> dict[str, float]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT nh.fund_name, nh.nav
            FROM nav_history nh
            JOIN (
                SELECT fund_name, MAX(nav_date) AS nav_date
                FROM nav_history
                GROUP BY fund_name
            ) latest ON latest.fund_name = nh.fund_name AND latest.nav_date = nh.nav_date
        """).fetchall()
        return {r["fund_name"]: float(r["nav"]) for r in rows}

def previous_navs() -> dict[str, float]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT fund_name, nav FROM (
                SELECT fund_name, nav, ROW_NUMBER() OVER (PARTITION BY fund_name ORDER BY nav_date DESC) AS rn
                FROM nav_history
            ) ranked WHERE rn = 2
        """).fetchall()
        return {r["fund_name"]: float(r["nav"]) for r in rows}

def save_portfolio_snapshot(snapshot_date: date, total_invested: float, current_value: float) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO portfolio_snapshots(snapshot_date,total_invested,current_value,profit_loss)
            VALUES(?,?,?,?)
            ON CONFLICT(snapshot_date) DO UPDATE SET total_invested=excluded.total_invested,
            current_value=excluded.current_value, profit_loss=excluded.profit_loss""",
            (str(snapshot_date), total_invested, current_value, current_value - total_invested),
        )

def peak_portfolio_value() -> float:
    with get_conn() as conn:
        row = conn.execute("SELECT MAX(current_value) AS peak FROM portfolio_snapshots").fetchone()
        return float(row["peak"] or 0)

def export_transactions(path: Path) -> Path:
    rows = fetch_all("transactions")
    path.parent.mkdir(parents=True, exist_ok=True)
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
    init_db(); BACKUP_DIR.mkdir(parents=True, exist_ok=True); dest = BACKUP_DIR / f"investment_assistant_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"; shutil.copy2(DB_PATH, dest); return dest

def restore_database(src: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True); shutil.copy2(src, DB_PATH)
