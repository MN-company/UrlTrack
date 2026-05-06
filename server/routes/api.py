import json
from datetime import datetime

from flask import Blueprint, request

from ..config import Config
from ..extensions import csrf, db, limiter, log_queue
from ..models import Visit
from ..services.scoring import apply_visit_scoring
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


def _visit_from_payload(data):
    try:
        visit_id = int(data.get("visit_id", 0))
    except (TypeError, ValueError):
        return None
    return db.session.get(Visit, visit_id)


def _clean_partial_email(value: str) -> str:
    if not value:
        return ""
    cleaned = "".join(ch for ch in value.strip() if ch.isprintable())
    return cleaned[:120]


def _coerce_int(value, minimum=None, maximum=None):
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def _coerce_float(value, minimum=None, maximum=None):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    value = float(value)
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return None


def _json_list_text(value, item_limit: int, max_len: int) -> str | None:
    if not isinstance(value, list):
        return None
    cleaned = []
    for item in value[:item_limit]:
        normalized = sanitize(str(item), 120)
        if normalized:
            cleaned.append(normalized)
    payload = json.dumps(cleaned)
    return payload[:max_len] if payload else None


@bp.route("/beacon", methods=["POST"])
@limiter.limit("60 per minute")
def receive_beacon():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if not _validate_visit_token(data):
            return "Unauthorized", 403

        visit = _visit_from_payload(data)
        if visit is None:
            return "Not found", 404

        visit.screen_res = sanitize(data.get("screen_res"), 32) or visit.screen_res
        screen_depth = _coerce_int(data.get("screen_depth"), 1, 128)
        if screen_depth is not None:
            visit.screen_depth = screen_depth
        pixel_ratio = _coerce_float(data.get("pixel_ratio"), 0, 20)
        if pixel_ratio is not None:
            visit.pixel_ratio = pixel_ratio
        visit.timezone = sanitize(data.get("timezone"), 64) or visit.timezone
        visit.platform = sanitize(data.get("platform"), 64) or visit.platform
        touch_points = _coerce_int(data.get("touch_points"), 0, 64)
        if touch_points is not None:
            visit.touch_points = touch_points
        dark_mode = _coerce_bool(data.get("dark_mode"))
        if dark_mode is not None:
            visit.dark_mode = dark_mode
        reduced_motion = _coerce_bool(data.get("reduced_motion"))
        if reduced_motion is not None:
            visit.reduced_motion = reduced_motion
        visit.connection_type = sanitize(data.get("connection_type"), 32) or visit.connection_type
        visit.browser_bot = bool(data.get("webdriver", False))
        visit.browser_language = sanitize(data.get("language"), 32) or visit.browser_language
        visit.do_not_track = sanitize(data.get("do_not_track"), 8) or visit.do_not_track
        visit.adblock = bool(data.get("adblock", False))
        visit.canvas_hash = sanitize(data.get("canvas_hash"), 64) or visit.canvas_hash
        visit.audio_fp = sanitize(data.get("audio_fp"), 128) or visit.audio_fp
        visit.fonts = sanitize(data.get("fonts"), 4000) or visit.fonts
        visit.webgl_renderer = sanitize(data.get("renderer") or data.get("webgl_renderer"), 256) or visit.webgl_renderer
        visit.webgl_vendor = sanitize(data.get("vendor"), 256) or visit.webgl_vendor
        visit.webgl_extensions_hash = sanitize(data.get("extensions_hash"), 16) or visit.webgl_extensions_hash
        webgl_max_texture = _coerce_int(data.get("max_texture"), 0, 65536)
        if webgl_max_texture is not None:
            visit.webgl_max_texture = webgl_max_texture
        visit.client_rects_fp = sanitize(data.get("client_rects_fp"), 16) or visit.client_rects_fp
        visit.webrtc_ips = _json_list_text(data.get("webrtc_ips"), item_limit=12, max_len=512) or visit.webrtc_ips
        visit.extensions_detected = (
            _json_list_text(data.get("extensions_detected"), item_limit=20, max_len=1000)
            or visit.extensions_detected
        )
        cpu_cores = _coerce_int(data.get("cpu_cores"), 1, 256)
        if cpu_cores is not None:
            visit.cpu_cores = cpu_cores
        ram_gb = _coerce_float(data.get("ram_gb"), 0, 2048)
        if ram_gb is not None:
            visit.ram_gb = ram_gb
        taskbar_size = _coerce_int(data.get("taskbar_size"), -5000, 5000)
        if taskbar_size is not None:
            visit.taskbar_size = taskbar_size
        visit.ua_brands = sanitize(data.get("ua_brands"), 256) or visit.ua_brands
        dwell_ms = _coerce_int(data.get("dwell_ms"), 0, 300000)
        if dwell_ms is not None:
            visit.dwell_ms = dwell_ms
        visit.beacon_received_at = datetime.utcnow()
        visit.visit_complete = True
        apply_visit_scoring(visit, secret=Config.FINGERPRINT_SECRET)
        db.session.commit()
        try:
            log_queue.put({"type": "enrich_visit", "visit_id": visit.id, "notify": True})
        except Exception:
            pass
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

        visit = _visit_from_payload(data)
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

    try:
        visit = db.session.get(Visit, int(visit_id))
    except (TypeError, ValueError):
        return "Not found", 404
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

        visit = _visit_from_payload(data)
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
