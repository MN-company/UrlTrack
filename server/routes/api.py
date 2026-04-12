import json

from flask import Blueprint, request

from ..config import Config
from ..extensions import csrf, db, limiter
from ..models import Visit
from ..utils import safe_json, sanitize, verify_visit_token


bp = Blueprint("api", __name__, url_prefix="/api")
csrf.exempt(bp)


def _validate_visit_token(data):
    if not Config.REQUIRE_VISIT_TOKEN:
        return True
    if not data:
        return False
    token = data.get("visit_token") or data.get("token")
    visit_id = data.get("visit_id")
    try:
        visit_id = int(visit_id)
    except (TypeError, ValueError):
        return False
    verified_id = verify_visit_token(token, Config.VISIT_TOKEN_TTL_SECONDS)
    return verified_id == visit_id


def _clean_partial_email(value: str) -> str:
    if not value:
        return ""
    cleaned = "".join(ch for ch in value.strip() if ch.isprintable())
    return cleaned[:120]


@bp.route("/beacon", methods=["POST"])
@limiter.limit("60 per minute")
def receive_beacon():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if not _validate_visit_token(data):
            return "Unauthorized", 403

        visit = db.session.get(Visit, int(data.get("visit_id", 0)))
        if visit is None:
            return "Not found", 404

        visit.screen_res = sanitize(data.get("screen_res"), 32) or visit.screen_res
        visit.timezone = sanitize(data.get("timezone"), 64) or visit.timezone
        visit.browser_bot = bool(data.get("webdriver", False))
        visit.browser_language = sanitize(data.get("language"), 32) or visit.browser_language
        visit.adblock = bool(data.get("adblock", False))
        visit.canvas_hash = sanitize(data.get("canvas_hash"), 64) or visit.canvas_hash
        visit.webgl_renderer = sanitize(data.get("webgl_renderer"), 256) or visit.webgl_renderer
        visit.cpu_cores = data.get("cpu_cores") if isinstance(data.get("cpu_cores"), int) else visit.cpu_cores
        visit.ram_gb = data.get("ram_gb") if isinstance(data.get("ram_gb"), (int, float)) else visit.ram_gb
        visit.battery_level = sanitize(data.get("battery_level"), 20) or visit.battery_level
        db.session.commit()
    except Exception as exc:
        print(f"Beacon Error: {exc}")
        db.session.rollback()
    return "OK", 200


@bp.route("/log_session", methods=["POST"])
@limiter.limit("30 per minute")
def log_session():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if not _validate_visit_token(data):
            return "Unauthorized", 403

        visit = db.session.get(Visit, int(data.get("visit_id", 0)))
        sessions = data.get("sessions") or []
        if visit is None or not isinstance(sessions, list):
            return "OK", 200

        existing = safe_json(visit.detected_sessions, []) or []
        if not isinstance(existing, list):
            existing = []
        for session_name in sessions:
            value = sanitize(str(session_name), 80)
            if value and value not in existing:
                existing.append(value)
        visit.detected_sessions = json.dumps(existing)
        db.session.commit()
    except Exception as exc:
        print(f"Session Log Error: {exc}")
        db.session.rollback()
    return "OK", 200


@bp.route("/partial_email", methods=["POST"])
@limiter.limit("10 per minute")
def partial_email():
    if not Config.ALLOW_PARTIAL_EMAIL_CAPTURE:
        return "Disabled", 403

    visit_id = request.form.get("visit_id")
    visit_token = request.form.get("visit_token")
    partial = _clean_partial_email(request.form.get("partial_email", ""))

    if not _validate_visit_token({"visit_id": visit_id, "visit_token": visit_token}):
        return "Unauthorized", 403
    if not visit_id or not partial:
        return "Missing data", 400

    visit = db.session.get(Visit, int(visit_id))
    if visit is None:
        return "Not found", 404

    note = f"partial_email:{partial}"
    if visit.notes:
        if note not in visit.notes:
            visit.notes = f"{visit.notes} | {note}"
    else:
        visit.notes = note
    db.session.commit()
    return "OK", 200


@bp.route("/dwell", methods=["POST"])
@limiter.limit("60 per minute")
def dwell():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if not _validate_visit_token(data):
            return "Unauthorized", 403

        visit = db.session.get(Visit, int(data.get("visit_id", 0)))
        if visit is None:
            return "Not found", 404

        dwell_ms = data.get("dwell_ms")
        if not isinstance(dwell_ms, int):
            return "Invalid dwell", 400
        if dwell_ms < 0 or dwell_ms > 300000:
            return "Invalid dwell", 400

        visit.dwell_ms = dwell_ms
        db.session.commit()
        return "OK", 200
    except Exception as exc:
        print(f"Dwell Error: {exc}")
        db.session.rollback()
        return "Error", 500
