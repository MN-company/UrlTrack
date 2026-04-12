import atexit
import threading
import time
from datetime import datetime, timedelta

import requests

from .config import Config
from .extensions import db, log_queue
from .models import Visit


STOP_SENTINEL = {"type": "__stop__"}
_worker_started = False
_worker_lock = threading.Lock()


def _telegram_escape(value: str) -> str:
    if not value:
        return ""
    for char in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        value = value.replace(char, f"\\{char}")
    return value


def _fire_telegram(app, visit_payload: dict):
    try:
        with app.app_context():
            slug = _telegram_escape(visit_payload.get("slug") or "unknown")
            city = _telegram_escape(visit_payload.get("city") or "Unknown city")
            country = _telegram_escape(visit_payload.get("country") or "Unknown country")
            email = _telegram_escape(visit_payload.get("email") or "anonimo")
            device_type = _telegram_escape(visit_payload.get("device_type") or "Unknown device")
            os_family = _telegram_escape(visit_payload.get("os_family") or "Unknown OS")
            timestamp = _telegram_escape(visit_payload.get("timestamp") or "Unknown time")
            vpn_label = "Si" if visit_payload.get("is_vpn") else "No"
            text = (
                f"👁 *Nuova visita* su `/{slug}`\n"
                f"📍 {city}, {country}\n"
                f"📧 {email}\n"
                f"🖥 {device_type} · {os_family}\n"
                f"🔒 VPN: {vpn_label}\n"
                f"🕐 {timestamp}"
            )
            requests.post(
                f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": Config.TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=5,
            )
    except Exception as exc:
        print(f"Telegram delivery error: {exc}")


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
                if Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID:
                    payload = {
                        "slug": visit.link.slug if visit.link else None,
                        "timestamp": visit.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if visit.timestamp else None,
                        "city": visit.city,
                        "country": visit.country,
                        "email": visit.email,
                        "device_type": visit.device_type,
                        "os_family": visit.os_family,
                        "is_vpn": visit.is_vpn,
                    }
                    threading.Thread(target=_fire_telegram, args=(app, payload), daemon=True).start()
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
