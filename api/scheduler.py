"""
APScheduler background job — runs the swing screener nightly.

Cron: 30 12 * * 1-5  UTC  ≈  18:00 IST on weekdays (after NSE close).
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api.db import get_supabase
from api.routes.screener import _do_scan
from core.screeners.swing import run_scan

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _nightly_scan() -> None:
    logger.info("Nightly scan triggered at %s UTC", datetime.now(timezone.utc).isoformat())
    sb = get_supabase()
    res = sb.table("screener_runs").insert({
        "status": "running",
        "universe": "NIFTY 500",
        "total": 0,
        "scanned": 0,
        "passed": 0,
    }).execute()
    run_id = res.data[0]["id"]
    _do_scan(run_id)


def start_scheduler() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _nightly_scan,
        trigger=CronTrigger(hour=12, minute=30, day_of_week="mon-fri"),
        id="nightly_swing_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info("APScheduler started — nightly scan at 12:30 UTC (18:00 IST) weekdays")


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
