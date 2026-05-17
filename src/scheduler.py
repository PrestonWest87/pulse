import time
import schedule
import sys
import gc
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from src.database import SessionLocal, init_db, Monitor, MonitorCheck
from src.monitors import get_monitor
from src.alert_engine import evaluate_and_alert

init_db()

LOCAL_TZ = ZoneInfo("America/Chicago")
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(name)s] %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger("scheduler")


def log(msg, source="SCHEDULER"):
    logger.info(f"[{source}] {msg}")


def run_monitor_check(monitor_id: int):
    with SessionLocal() as db:
        mon = db.query(Monitor).filter_by(id=monitor_id).first()
        if not mon or not mon.enabled:
            return

        try:
            monitor_cls = get_monitor(mon.monitor_type)
            instance = monitor_cls(mon.config)
            check_start = time.time()
            result = instance.check()
            elapsed_ms = round((time.time() - check_start) * 1000, 1)

            check = MonitorCheck(
                monitor_id=mon.id,
                status=result.status,
                status_code=result.status_code,
                response_time_ms=result.response_time_ms or elapsed_ms,
                response_summary=result.response_summary,
                error=result.error,
                raw_data=result.raw_data,
            )
            db.add(check)
            db.commit()
            db.refresh(check)

            mon.last_check_at = datetime.utcnow()
            mon.last_status = result.status
            mon.last_response_time_ms = result.response_time_ms or elapsed_ms
            mon.last_error = result.error
            mon.last_response_summary = result.response_summary
            db.commit()

            log(f"{mon.name} [{mon.monitor_type}]: {result.status} "
                f"({result.response_time_ms or elapsed_ms}ms)"
                + (f" - {result.error}" if result.error else ""))

            evaluate_and_alert(mon, check, result)

        except Exception as e:
            log(f"CRASH checking {mon.name}: {e}", "ERROR")
            import traceback
            traceback.print_exc()

            check = MonitorCheck(
                monitor_id=mon.id, status="error",
                error=f"Monitor crashed: {e}"
            )
            with SessionLocal() as db2:
                db2.add(check)
                db2.commit()


def reload_schedule():
    schedule.clear()
    with SessionLocal() as db:
        monitors = db.query(Monitor).filter_by(enabled=True).all()
        for mon in monitors:
            interval = max(mon.interval_seconds or 300, 10)
            job = schedule.every(interval).seconds.do(run_monitor_check, mon.id)
            job.tag(f"monitor-{mon.id}")
            log(f"Scheduled: {mon.name} [{mon.monitor_type}] every {interval}s")

    log(f"Loaded {len(monitors)} active monitors")


def background_reloader():
    """Periodically reload the schedule to pick up new/changed monitors."""
    while True:
        time.sleep(60)
        reload_schedule()


if __name__ == "__main__":
    log("Pulse Scheduler starting...")
    reload_schedule()

    import threading
    reloader = threading.Thread(target=background_reloader, daemon=True)
    reloader.start()

    log("Scheduler online. Running checks...")
    while True:
        schedule.run_pending()
        time.sleep(1)
        gc.collect()
