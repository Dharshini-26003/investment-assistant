from pathlib import Path
APP_NAME = "AI Personal Investment Assistant"
GOAL_AMOUNT = 30_000.0
DEFAULT_INVESTMENT = 500.0
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "investment_assistant.sqlite3"
NAV_CACHE_PATH = DATA_DIR / "nav_cache.json"
REPORTS_DIR = Path("reports")
BACKUP_DIR = Path("backups")
DISCLAIMER = (
    "Educational tool only. It never places trades, never stores banking passwords, "
    "and does not guarantee profits. Consult a SEBI-registered advisor for personal advice."
)
