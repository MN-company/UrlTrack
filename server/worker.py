import atexit
import threading
import time
from datetime import datetime, timedelta

from .config import Config
from .extensions import db, log_queue
from .models import Visit


STOP_SENTINEL = {"type": "__stop__"}
_worker_started = False
_worker_lock = threading.Lock()


def _cleanup_visits(app):
    while True:
        try:
            if Config.VISIT_RETENTION_DAYS > 0:
                cutoff = datetime.utcnow() - timedelta(days=Config.VISIT_RETENTION_DAYS)
                with app.app_context():
                    deleted = Visit.query.filter(Visit.timestamp < cutoff).delete()
                    if deleted:
                        db.session.commit()
                        print(f"Retention cleanup deleted {deleted} visits")
        except Exception as exc:
            print(f"Retention cleanup error: {exc}")
            db.session.rollback()
        time.sleep(6 * 3600)


def _handle_task(app, task):
    try:
        with app.app_context():
            if task.get("type") == "enrich_visit":
                visit = db.session.get(Visit, task.get("visit_id"))
                if visit is None:
                    return

                from .utils import get_geo_data, get_reverse_dns

                ip_address = task.get("ip")
                if ip_address:
                    hostname = get_reverse_dns(ip_address)
                    if hostname:
                        visit.hostname = hostname

                    geo_data = get_geo_data(ip_address)
                    visit.is_vpn = bool(geo_data.get("proxy"))
                    visit.is_proxy = bool(geo_data.get("proxy"))
                    visit.is_hosting = bool(geo_data.get("hosting"))
                    visit.is_mobile = bool(geo_data.get("mobile"))
                    if not visit.isp:
                        visit.isp = geo_data.get("isp")
                    if not visit.org:
                        visit.org = geo_data.get("org")

                if not visit.email and visit.canvas_hash:
                    match = (
                        Visit.query.filter(Visit.canvas_hash == visit.canvas_hash, Visit.email.isnot(None))
                        .order_by(Visit.timestamp.desc())
                        .first()
                    )
                    if match:
                        visit.email = match.email
                db.session.commit()
            else:
                print(f"Worker ignored unknown task type: {task.get('type')}")
    except Exception as exc:
        print(f"Worker task error: {exc}")
        db.session.rollback()
    finally:
        db.session.remove()


def _worker_loop(app):
    while True:
        try:
            task = log_queue.get()
            if task == STOP_SENTINEL or task is None:
                log_queue.task_done()
                break
            _handle_task(app, task)
            log_queue.task_done()
        except Exception as exc:
            print(f"Worker loop error: {exc}")
            db.session.rollback()
            db.session.remove()


def start_worker(app):
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    threading.Thread(target=_worker_loop, args=(app,), daemon=True).start()
    threading.Thread(target=_cleanup_visits, args=(app,), daemon=True).start()

    def _shutdown():
        try:
            log_queue.put(STOP_SENTINEL)
        except Exception:
            pass

    atexit.register(_shutdown)
