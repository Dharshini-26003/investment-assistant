from __future__ import annotations
import json, logging
from datetime import datetime, timedelta
from pathlib import Path
import requests
from app.config import NAV_CACHE_PATH
log = logging.getLogger(__name__)
AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

def fetch_amfi_navs(cache_path: Path = NAV_CACHE_PATH, max_age_hours: int = 24) -> dict[str, dict]:
    cache_path.parent.mkdir(exist_ok=True)
    if cache_path.exists() and datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime) < timedelta(hours=max_age_hours):
        return json.loads(cache_path.read_text(encoding="utf-8"))
    try:
        text = requests.get(AMFI_URL, timeout=20).text
        data = {}
        for line in text.splitlines():
            parts = line.split(";")
            if len(parts) >= 6 and parts[0].isdigit():
                data[parts[3].strip()] = {"scheme_code": parts[0], "nav": float(parts[4]), "date": parts[5]}
        cache_path.write_text(json.dumps(data), encoding="utf-8")
        return data
    except Exception as exc:
        log.warning("NAV fetch failed: %s", exc)
        return json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

def find_nav(fund_name: str, navs: dict[str, dict]) -> float | None:
    key = fund_name.lower()
    for name, item in navs.items():
        if key in name.lower() or name.lower() in key:
            return float(item["nav"])
    return None
