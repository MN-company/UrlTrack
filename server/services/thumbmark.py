import json
import re
from datetime import datetime, timedelta
from typing import Any

import requests
from flask import current_app

from ..config import Config
from ..extensions import db
from ..models import Visit, Visitor


def _config_value(name: str, default: str = "") -> str:
    try:
        return current_app.config.get(name, default)
    except RuntimeError:
        return getattr(Config, name, default)


def _text(value: Any, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        value = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    value = str(value).strip()
    if not value:
        return None
    return value[:max_len] if max_len else value


def _float_0_1(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1 and number <= 100:
        number = number / 100
    if number < 0 or number > 1:
        return None
    return number


def _first_csv(value: str | None, max_len: int = 32) -> str | None:
    if not value:
        return None
    first = next((part.strip() for part in value.split(",") if part.strip()), "")
    return first[:max_len] if first else None


def _json_list_from_csv(value: str | None, *, limit: int = 12) -> str | None:
    if not value:
        return None
    parts = [part.strip() for part in value.split(",") if part.strip()]
    return json.dumps(parts[:limit]) if parts else None


def _mirror_thumbmark_fields_to_legacy(visit: Visit) -> None:
    if visit.fp_canvas_hash and not visit.canvas_hash:
        visit.canvas_hash = visit.fp_canvas_hash[:64]
    if visit.fp_audio_hash and not visit.audio_fp:
        visit.audio_fp = visit.fp_audio_hash[:128]
    if visit.fp_fonts_hash and not visit.fonts:
        visit.fonts = visit.fp_fonts_hash
    if visit.fp_webgl_vendor:
        visit.webgl_renderer = visit.webgl_renderer or visit.fp_webgl_vendor[:256]
        visit.webgl_vendor = visit.webgl_vendor or visit.fp_webgl_vendor[:256]
    if visit.fp_webgl_hash and not visit.webgl_extensions_hash:
        visit.webgl_extensions_hash = visit.fp_webgl_hash[:16]
    if visit.fp_timezone and not visit.timezone:
        visit.timezone = visit.fp_timezone[:64]
    if visit.fp_languages and not visit.browser_language:
        visit.browser_language = _first_csv(visit.fp_languages)
    if visit.fp_webrtc_ips and not visit.webrtc_ips:
        visit.webrtc_ips = _json_list_from_csv(visit.fp_webrtc_ips)

    if visit.fp_screen_profile:
        match = re.match(r"^(\d+)x(\d+)x(\d+)@([0-9.]+)$", visit.fp_screen_profile)
        if match:
            width, height, depth, ratio = match.groups()
            visit.screen_res = visit.screen_res or f"{width}x{height}"
            if visit.screen_depth is None:
                visit.screen_depth = int(depth)
            if visit.pixel_ratio is None:
                try:
                    visit.pixel_ratio = float(ratio)
                except ValueError:
                    pass

    if visit.fp_hardware_profile:
        match = re.match(r"^(\d+)c/([0-9.]+)gb/(\d+)tp$", visit.fp_hardware_profile)
        if match:
            cores, memory, touch = match.groups()
            if visit.cpu_cores is None:
                visit.cpu_cores = int(cores)
            if visit.ram_gb is None:
                try:
                    visit.ram_gb = float(memory)
                except ValueError:
                    pass
            if visit.touch_points is None:
                visit.touch_points = int(touch)


def store_thumbmark_payload(visit: Visit, data: dict[str, Any]) -> None:
    if "thumbmark_hash" in data or "thumbmark" in data or "hash" in data:
        visit.thumbmark_hash = _text(data.get("thumbmark_hash") or data.get("thumbmark") or data.get("hash"), 256)
    if "thumbmark_raw" in data:
        visit.thumbmark_raw = _text(data.get("thumbmark_raw"))
    elif "components" in data:
        visit.thumbmark_raw = _text(data)
    if "thumbmark_visitor_id" in data or "visitorId" in data:
        visit.thumbmark_visitor_id = _text(data.get("thumbmark_visitor_id") or data.get("visitorId"), 256)
    if "thumbmark_api_confidence" in data or "confidence" in data:
        visit.thumbmark_api_confidence = _float_0_1(
            data.get("thumbmark_api_confidence") if "thumbmark_api_confidence" in data else data.get("confidence")
        )

    field_limits = {
        "fp_audio_hash": 256,
        "fp_canvas_hash": 256,
        "fp_webgl_vendor": 512,
        "fp_webgl_hash": 256,
        "fp_fonts_hash": 512,
        "fp_screen_profile": 128,
        "fp_hardware_profile": 128,
        "fp_languages": 512,
        "fp_timezone": 128,
        "fp_speech_hash": 256,
        "fp_math_hash": 256,
        "fp_permissions_profile": 4000,
        "fp_media_devices": 128,
        "fp_webrtc_ips": 512,
    }
    for field, limit in field_limits.items():
        if field in data:
            setattr(visit, field, _text(data.get(field), limit))

    _mirror_thumbmark_fields_to_legacy(visit)


def _raw_result(visit: Visit) -> dict[str, Any]:
    if not visit.thumbmark_raw:
        return {}
    try:
        parsed = json.loads(visit.thumbmark_raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _api_request_body(visit: Visit) -> dict[str, Any]:
    raw = _raw_result(visit)
    components = raw.get("components") or raw.get("data") or {}
    body: dict[str, Any] = {
        "components": components,
        "options": {
            "timeout": 3000,
            "cache_api_call": True,
            "cache_lifetime_in_ms": 0,
            "experimental": True,
            "logging": False,
        },
        "clientHash": visit.thumbmark_hash,
    }
    if raw.get("version"):
        body["version"] = raw.get("version")
    if visit.thumbmark_visitor_id:
        body["visitorId"] = visit.thumbmark_visitor_id
    return body


def _confidence_from_api_result(result: dict[str, Any]) -> float | None:
    confidence = _float_0_1(result.get("confidence") or result.get("confidenceScore"))
    if confidence is not None:
        return confidence
    info = result.get("info") if isinstance(result.get("info"), dict) else {}
    uniqueness = info.get("uniqueness") if isinstance(info.get("uniqueness"), dict) else {}
    return _float_0_1(uniqueness.get("score"))


def call_thumbmark_api(visit: Visit) -> dict[str, Any] | None:
    api_key = _config_value("THUMBMARK_API_KEY")
    api_url = _config_value("THUMBMARK_API_URL", "https://api.thumbmarkjs.com/thumbmark")
    if not api_key or not visit.thumbmark_hash:
        return None

    try:
        response = requests.post(
            api_url,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=_api_request_body(visit),
            timeout=3,
        )
        visit.thumbmark_api_called = True
        if response.status_code == 200:
            result = response.json()
            visit.thumbmark_visitor_id = _text(result.get("visitorId"), 256) or visit.thumbmark_visitor_id
            visit.thumbmark_api_confidence = _confidence_from_api_result(result)
            visit.thumbmark_api_error = None
            return result
        visit.thumbmark_api_error = f"HTTP {response.status_code}"
    except Exception as exc:
        visit.thumbmark_api_error = str(exc)
    return None


def maybe_enrich_thumbmark_api(visit: Visit, confidence_score: int) -> dict[str, Any] | None:
    api_key = _config_value("THUMBMARK_API_KEY")
    if not api_key or not visit.thumbmark_hash or confidence_score >= 40:
        return None

    if visit.visitor_id:
        visitor = db.session.get(Visitor, visit.visitor_id)
        if visitor and visitor.thumbmark_api_confidence_avg and visitor.thumbmark_api_confidence_avg > 0.85:
            return None

    cutoff = datetime.utcnow() - timedelta(days=7)
    recent = (
        Visit.query.filter(
            Visit.id != visit.id,
            Visit.thumbmark_hash == visit.thumbmark_hash,
            Visit.thumbmark_api_called.is_(True),
            Visit.timestamp >= cutoff,
        )
        .order_by(Visit.timestamp.desc())
        .first()
    )
    if recent:
        visit.thumbmark_visitor_id = recent.thumbmark_visitor_id
        visit.thumbmark_api_confidence = recent.thumbmark_api_confidence
        visit.thumbmark_api_called = True
        visit.thumbmark_api_error = recent.thumbmark_api_error
        return {"cached": True}

    return call_thumbmark_api(visit)
