import time
import schedule
import sys
import gc
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from src.database import SessionLocal, init_db, Source, CollectionRun, CollectedItem
from src.collectors import get_collector
from src.alert_engine import evaluate_items

init_db()

LOCAL_TZ = ZoneInfo("America/Chicago")
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(name)s] %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger("scheduler")


def log(msg, source="SCHEDULER"):
    logger.info(f"[{source}] {msg}")


def run_collector(source_id: int):
    with SessionLocal() as db:
        src = db.query(Source).filter_by(id=source_id).first()
        if not src or not src.enabled:
            return

        try:
            collector_cls = get_collector(src.collector_type)
            instance = collector_cls(src.config)

            start = time.time()
            result = instance.collect()
            duration = round((time.time() - start) * 1000, 1)

            new_count = 0
            new_items = []

            for data in result.items:
                # Dedup by content_hash
                existing = db.query(CollectedItem).filter(
                    CollectedItem.source_id == src.id,
                    CollectedItem.content_hash == data.content_hash
                ).first()
                if existing:
                    continue

                item = CollectedItem(
                    source_id=src.id,
                    source_name=src.name,
                    source_type=src.collector_type,
                    title=data.title,
                    content=data.content[:100000] if data.content else "",
                    url=data.url,
                    author=data.author,
                    published_at=data.published_at,
                    content_hash=data.content_hash,
                    raw_data=data.raw_data,
                )
                db.add(item)
                new_items.append(item)
                new_count += 1

            db.commit()

            run = CollectionRun(
                source_id=src.id,
                status=result.status,
                items_found=len(result.items),
                items_new=new_count,
                response_summary=result.summary,
                error=result.error,
                duration_ms=duration,
            )
            db.add(run)
            src.last_run_at = datetime.utcnow()
            src.last_status = result.status
            src.last_error = result.error
            db.commit()

            log(f"{src.name} [{src.collector_type}]: {result.status}, "
                f"{new_count} new / {len(result.items)} found ({duration}ms)"
                + (f" — {result.error}" if result.error else ""))

            if new_items:
                evaluate_items(src, new_items)

        except Exception as e:
            log(f"CRASH collecting {src.name}: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            run = CollectionRun(source_id=src.id, status="error", error=f"Crashed: {e}")
            with SessionLocal() as db2:
                db2.add(run)
                try:
                    src2 = db2.query(Source).filter_by(id=src.id).first()
                    if src2:
                        src2.last_status = "error"
                        src2.last_error = str(e)[:500]
                    db2.commit()
                except Exception:
                    db2.rollback()


def reload_schedule():
    schedule.clear()
    with SessionLocal() as db:
        sources = db.query(Source).filter_by(enabled=True).all()
        for src in sources:
            interval = max(src.interval_seconds or 900, 60)
            schedule.every(interval).seconds.do(run_collector, src.id)
            log(f"Scheduled: {src.name} [{src.collector_type}] every {interval}s")
    log(f"Loaded {len(sources)} active sources")


def background_reloader():
    while True:
        time.sleep(60)
        reload_schedule()


if __name__ == "__main__":
    log("Pulse scheduler starting...")
    reload_schedule()

    import threading
    threading.Thread(target=background_reloader, daemon=True).start()

    # Run digests every 5 minutes
    def digest_loop():
        from src.services import run_digests
        while True:
            time.sleep(300)
            try:
                run_digests()
            except Exception as e:
                log(f"Digest error: {e}", "DIGEST")

    threading.Thread(target=digest_loop, daemon=True).start()

    # Check escalations every 2 minutes
    def escalation_loop():
        from src.services import check_escalations
        while True:
            time.sleep(120)
            try:
                check_escalations()
            except Exception as e:
                log(f"Escalation check error: {e}", "ESCALATION")

    threading.Thread(target=escalation_loop, daemon=True).start()

    log("Scheduler online. Collecting data...")
    while True:
        schedule.run_pending()
        time.sleep(1)
        gc.collect()
