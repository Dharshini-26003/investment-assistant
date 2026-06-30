from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.services.tracker import refresh_navs_for_portfolio, update_portfolio_tracking

log = logging.getLogger(__name__)


def run_daily_update() -> dict:
    refresh_navs_for_portfolio()
    return update_portfolio_tracking()


def start_background_scheduler(hour: int = 18, minute: int = 0) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(run_daily_update, "cron", hour=hour, minute=minute, id="daily_portfolio_update", replace_existing=True)
    scheduler.start()
    log.info("Started daily portfolio scheduler at %02d:%02d Asia/Kolkata", hour, minute)
    return scheduler
