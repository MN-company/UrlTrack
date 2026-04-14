import atexit
import hashlib
import hmac
import json
import statistics
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import func

from .extensions import db, log_queue
from .models import Link, Visit


STOP_SENTINEL = {"type": "__stop__"}
_worker_started = False
_worker_lock = threading.Lock()


def _telegram_escape(value: str) -> str:
    if not value:
        return ""
    for char in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        value = value.replace(char, f"\\{char}")
    return value


def _build_visit_payload(visit: Visit) -> dict:
    return {
        "id": visit.id,
        "slug": visit.link.slug if visit.link else "unknown",
        "timestamp": visit.timestamp.isoformat() if visit.timestamp else None,
        "ip": visit.ip_address,
        "country": visit.country,
        "city": visit.city,
        "email": visit.email,
        "canvas_hash": visit.canvas_hash,
        "etag": visit.etag,
        "is_vpn": visit.is_vpn,
        "is_suspicious": visit.is_suspicious,
        "device_type": visit.device_type,
        "os_family": visit.os_family,
        "org": visit.org,
        "dwell_ms": visit.dwell_ms,
        "extensions_detected": visit.extensions_detected,
    }


def _fire_webhook(webhook_url: str, webhook_secret: str, visit_payload: dict) -> None:
    try:
        body = json.dumps(visit_payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if webhook_secret:
            signature = hmac.new(webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers["X-UlrTrack-Signature"] = signature
        requests.post(webhook_url, data=body, headers=headers, timeout=5)
    except Exception as exc:
        print(f"Webhook delivery error: {exc}")


def _fire_telegram(bot_token: str, chat_id: str, visit_payload: dict) -> None:
    try:
        emoji_device = {"Mobile": "📱", "Tablet": "📱", "Desktop": "🖥️"}
        slug = _telegram_escape(visit_payload.get("slug") or "unknown")
        city = _telegram_escape(visit_payload.get("city") or "?")
        country = _telegram_escape(visit_payload.get("country") or "?")
        email = _telegram_escape(visit_payload.get("email") or "Anonimo")
        os_family = _telegram_escape(visit_payload.get("os_family") or "?")
        timestamp = _telegram_escape((visit_payload.get("timestamp") or "")[:19].replace("T", " "))
        vpn_str = "⚠️ VPN/Proxy" if visit_payload.get("is_vpn") else "✅ Clean"
        dwell_ms = visit_payload.get("dwell_ms")
        dwell_str = f"\n⏱ {_telegram_escape(str(int(dwell_ms // 1000)))}s" if isinstance(dwell_ms, int) and dwell_ms > 0 else ""

        ext_str = ""
        extensions_detected = visit_payload.get("extensions_detected")
        if extensions_detected:
            try:
                exts = json.loads(extensions_detected) if isinstance(extensions_detected, str) else extensions_detected
                if exts:
                    ext_str = "\n🧩 Extensions: " + _telegram_escape(", ".join(exts[:3]))
            except Exception:
                pass

        text = (
            f"👁 *Nuova visita* su `/{slug}`\n"
            f"📍 {city}, {country}\n"
            f"📧 {email}\n"
            f"{emoji_device.get(visit_payload.get('device_type'), '🖥️')} {os_family} · {vpn_str}"
            f"{dwell_str}{ext_str}\n"
            f"🕐 {timestamp}"
        )

        _send_telegram_text(bot_token, chat_id, text)
    except Exception as exc:
        print(f"Telegram delivery error: {exc}")


def _send_telegram_text(bot_token: str, chat_id: str, text: str) -> None:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "MarkdownV2"},
            timeout=5,
        )
        if not resp.ok:
            plain = text
            for ch in ("*", "`", "\\"):
                plain = plain.replace(ch, "")
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": plain},
                timeout=5,
            )
    except Exception as exc:
        print(f"Telegram message error: {exc}")


def _cleanup_visits(app):
    while True:
        try:
            with app.app_context():
                retention_days = int(app.config.get("VISIT_RETENTION_DAYS", 0) or 0)
                if retention_days > 0:
                    cutoff = datetime.utcnow() - timedelta(days=retention_days)
                    deleted = Visit.query.filter(Visit.timestamp < cutoff).delete()
                    if deleted:
                        db.session.commit()
                        print(f"Retention cleanup deleted {deleted} visits")
        except Exception as exc:
            print(f"Retention cleanup error: {exc}")
            db.session.rollback()
        finally:
            db.session.remove()
        time.sleep(6 * 3600)


def _resolve_digest_timezone(app) -> ZoneInfo:
    try:
        with app.app_context():
            timezone_name = (
                db.session.query(Visit.timezone)
                .filter(Visit.timezone.isnot(None), Visit.timezone != "")
                .order_by(Visit.timestamp.desc())
                .limit(1)
                .scalar()
            )
            if timezone_name:
                return ZoneInfo(timezone_name)
    except Exception as exc:
        print(f"Digest timezone error: {exc}")
    return ZoneInfo("UTC")


def _send_daily_digest(app) -> None:
    with app.app_context():
        bot_token = app.config.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = app.config.get("TELEGRAM_CHAT_ID", "")
        if not bot_token or not chat_id:
            return

        cutoff = datetime.utcnow() - timedelta(hours=24)
        total_visits = Visit.query.filter(Visit.timestamp >= cutoff).count()
        identified = Visit.query.filter(Visit.timestamp >= cutoff, Visit.email.isnot(None)).count()
        vpn_count = (
            Visit.query.filter(
                Visit.timestamp >= cutoff,
                db.or_(Visit.is_vpn.is_(True), Visit.is_proxy.is_(True)),
            ).count()
        )

        first_visit_subquery = (
            db.session.query(Visit.link_id, func.min(Visit.timestamp).label("first_seen"))
            .group_by(Visit.link_id)
            .subquery()
        )
        new_links_clicked = (
            db.session.query(func.count())
            .select_from(first_visit_subquery)
            .filter(first_visit_subquery.c.first_seen >= cutoff)
            .scalar()
            or 0
        )

        top_link = (
            db.session.query(Link.slug, func.count(Visit.id).label("visit_count"))
            .join(Visit, Visit.link_id == Link.id)
            .filter(Visit.timestamp >= cutoff)
            .group_by(Link.slug)
            .order_by(func.count(Visit.id).desc())
            .first()
        )
        top_country = (
            db.session.query(Visit.country, func.count(Visit.id).label("visit_count"))
            .filter(Visit.timestamp >= cutoff)
            .group_by(Visit.country)
            .order_by(func.count(Visit.id).desc())
            .first()
        )

        stats_dict = {
            "total_visits": total_visits,
            "new_links_clicked": new_links_clicked,
            "identified": identified,
            "vpn_count": vpn_count,
            "top_link": top_link[0] if top_link else None,
            "top_link_visits": top_link[1] if top_link else 0,
            "top_country": top_country[0] if top_country else None,
        }

        summary = ""
        if app.config.get("GEMINI_API_KEY"):
            try:
                from .services.ai_service import AIService

                prompt = (
                    "In max 2 righe, riassumi questi dati di tracking delle ultime 24 ore "
                    f"in italiano, tono professionale: {stats_dict}"
                )
                summary = (AIService.generate(prompt, model=app.config.get("GEMINI_MODEL")) or "").strip()
            except Exception as exc:
                print(f"Daily digest AI error: {exc}")

        tz = _resolve_digest_timezone(app)
        today_label = datetime.now(tz).strftime("%Y-%m-%d")
        message = (
            f"📊 *Daily Digest - {_telegram_escape(today_label)}*\n\n"
            f"👆 {_telegram_escape(str(total_visits))} visite · 📧 {_telegram_escape(str(identified))} email\n"
            f"🆕 Link nuovi cliccati: {_telegram_escape(str(new_links_clicked))}\n"
            f"🔗 Link top: /{_telegram_escape(top_link[0] if top_link else '?')} "
            f"({_telegram_escape(str(top_link[1] if top_link else 0))} visite)\n"
            f"🌍 Paese top: {_telegram_escape((top_country[0] or '?') if top_country else '?')}\n"
            f"⚠️ VPN: {_telegram_escape(str(vpn_count))}"
        )
        if summary:
            message += f"\n\n{_telegram_escape(summary)}"
        _send_telegram_text(bot_token, chat_id, message)


def _daily_digest_loop(app) -> None:
    while True:
        try:
            tz = _resolve_digest_timezone(app)
            now_local = datetime.now(tz)
            target = now_local.replace(hour=9, minute=0, second=0, microsecond=0)
            if now_local >= target:
                target += timedelta(days=1)
            sleep_seconds = max(60, int((target - now_local).total_seconds()))
            time.sleep(sleep_seconds)
            _send_daily_digest(app)
        except Exception as exc:
            print(f"Daily digest loop error: {exc}")
            time.sleep(3600)
        finally:
            try:
                with app.app_context():
                    db.session.remove()
            except Exception:
                pass


def _followup_loop(app) -> None:
    while True:
        try:
            with app.app_context():
                bot_token = app.config.get("TELEGRAM_BOT_TOKEN", "")
                chat_id = app.config.get("TELEGRAM_CHAT_ID", "")
                if not bot_token or not chat_id:
                    time.sleep(3600)
                    continue

                followup_hours = int(app.config.get("SMART_FOLLOWUP_HOURS", 48) or 48)
                cutoff = datetime.utcnow() - timedelta(hours=followup_hours)
                links = (
                    Link.query.filter(
                        Link.created_at <= cutoff,
                        Link.followup_notified_at.is_(None),
                    )
                    .order_by(Link.created_at.asc())
                    .all()
                )

                for link in links:
                    visits = Visit.query.filter_by(link_id=link.id).order_by(Visit.timestamp.asc()).all()
                    if not visits:
                        age_hours = int((datetime.utcnow() - link.created_at).total_seconds() // 3600)
                        text = (
                            f"⏰ Il link `/{_telegram_escape(link.slug)}` non e' stato ancora aperto.\n"
                            f"Creato {_telegram_escape(str(age_hours))}h fa.\n"
                            f"Destinazione: {_telegram_escape((link.destination or '')[:50])}"
                        )
                        _send_telegram_text(bot_token, chat_id, text)
                        link.followup_notified_at = datetime.utcnow()
                        db.session.commit()
                        continue

                    dwell_values = [visit.dwell_ms for visit in visits if isinstance(visit.dwell_ms, int)]
                    if not dwell_values:
                        continue

                    median_dwell = statistics.median(dwell_values)
                    if median_dwell < 3000:
                        avg_dwell_s = round(sum(dwell_values) / len(dwell_values) / 1000, 1)
                        text = (
                            f"⚡ `/{_telegram_escape(link.slug)}` aperto ma engagement basso.\n"
                            f"Avg {_telegram_escape(str(avg_dwell_s))}s. Potrebbe servire followup."
                        )
                        _send_telegram_text(bot_token, chat_id, text)
                        link.followup_notified_at = datetime.utcnow()
                        db.session.commit()
        except Exception as exc:
            print(f"Followup loop error: {exc}")
            db.session.rollback()
        finally:
            db.session.remove()
        time.sleep(3600)


def _handle_task(app, task):
    try:
        with app.app_context():
            if task.get("type") == "enrich_visit":
                visit = db.session.get(Visit, task.get("visit_id"))
                if visit is None:
                    return

                from .utils import get_geo_data, get_reverse_dns

                raw_ip = task.get("ip")
                if raw_ip:
                    hostname = get_reverse_dns(raw_ip)
                    if hostname:
                        visit.hostname = hostname

                    geo_data = get_geo_data(raw_ip)
                    visit.is_vpn = visit.is_vpn or bool(geo_data.get("proxy"))
                    visit.is_proxy = visit.is_proxy or bool(geo_data.get("proxy"))
                    visit.is_hosting = visit.is_hosting or bool(geo_data.get("hosting"))
                    visit.is_mobile = visit.is_mobile or bool(geo_data.get("mobile"))
                    visit.isp = visit.isp or geo_data.get("isp")
                    visit.org = visit.org or geo_data.get("org")
                    visit.country = visit.country or geo_data.get("country")
                    visit.city = visit.city or geo_data.get("city")
                    visit.country_code = visit.country_code or geo_data.get("countryCode")
                    visit.lat = visit.lat or geo_data.get("lat")
                    visit.lon = visit.lon or geo_data.get("lon")

                if not visit.email and visit.canvas_hash:
                    match = (
                        Visit.query.filter(Visit.canvas_hash == visit.canvas_hash, Visit.email.isnot(None))
                        .order_by(Visit.timestamp.desc())
                        .first()
                    )
                    if match:
                        visit.email = match.email

                db.session.commit()

                visit_payload = _build_visit_payload(visit)
                webhook_url = app.config.get("WEBHOOK_URL", "")
                webhook_secret = app.config.get("WEBHOOK_SECRET", "")
                if webhook_url:
                    threading.Thread(
                        target=_fire_webhook,
                        args=(webhook_url, webhook_secret, visit_payload),
                        daemon=True,
                    ).start()

                bot_token = app.config.get("TELEGRAM_BOT_TOKEN", "")
                chat_id = app.config.get("TELEGRAM_CHAT_ID", "")
                if bot_token and chat_id:
                    threading.Thread(
                        target=_fire_telegram,
                        args=(bot_token, chat_id, visit_payload),
                        daemon=True,
                    ).start()
            else:
                print(f"Worker ignored unknown task type: {task.get('type')}")
    except Exception as exc:
        print(f"Worker task error: {exc}")
        db.session.rollback()
    finally:
        try:
            with app.app_context():
                db.session.remove()
        except Exception:
            pass


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
    threading.Thread(target=_daily_digest_loop, args=(app,), daemon=True).start()
    threading.Thread(target=_followup_loop, args=(app,), daemon=True).start()

    def _shutdown():
        try:
            log_queue.put(STOP_SENTINEL)
        except Exception:
            pass

    atexit.register(_shutdown)
