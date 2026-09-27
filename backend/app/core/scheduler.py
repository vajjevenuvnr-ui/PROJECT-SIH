"""Runs the downscaling pipeline daily at 06:00 IST (APScheduler) and on demand from the admin API.

Off by default in development; enable with PIPELINE_SCHEDULE=true in backend/.env.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone

from app.core.config import get_settings

log = logging.getLogger(__name__)
_lock = threading.Lock()
STATE: dict = {"running": False, "started_at": None, "finished_at": None, "last_run": None, "error": None,
               "scheduled": False}


def run_pipeline_job(replay: date | None = None, publish_demo: bool | None = None) -> None:
    if not _lock.acquire(blocking=False):
        return  # a run is already in progress
    STATE.update(running=True, started_at=datetime.now(timezone.utc).isoformat(), error=None)
    try:
        from pipeline.run_daily import run

        pub = get_settings().pipeline_publish_demo if publish_demo is None else publish_demo
        res = run(replay=replay, publish_demo=pub, quiet=True)
        STATE["last_run"] = {k: res[k] for k in ("run", "published_demo", "published_db")} | {
            "timings": [{"step": n, "seconds": round(t, 1)} for n, t in res["timings"]]}
    except Exception as exc:  # report in the status endpoint; never crash the API
        log.exception("pipeline failed")
        STATE["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        STATE.update(running=False, finished_at=datetime.now(timezone.utc).isoformat())
        _lock.release()


def start_in_background(replay: date | None = None, publish_demo: bool | None = None) -> bool:
    if STATE["running"]:
        return False
    threading.Thread(target=run_pipeline_job, args=(replay, publish_demo), daemon=True).start()
    return True


def start_scheduler() -> None:
    if not get_settings().pipeline_schedule or STATE["scheduled"]:
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    sched = BackgroundScheduler(timezone="Asia/Kolkata")
    sched.add_job(run_pipeline_job, "cron", hour=6, minute=0, id="daily-pipeline", misfire_grace_time=3600)
    sched.start()
    STATE["scheduled"] = True
    log.info("pipeline scheduled daily at 06:00 IST")
