import hashlib
import hmac
import json
import re
from typing import Any


FINGERPRINT_VERSION = 1


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _normalize_list_text(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = [str(item) for item in value]
    else:
        return _normalize_text(value)
    cleaned = sorted({_normalize_text(part) for part in parts if _normalize_text(part)})
    return ",".join(cleaned)


def fingerprint_components(visit) -> dict[str, str]:
    webgl = "|".join(
        item
        for item in [
            _normalize_text(visit.webgl_vendor),
            _normalize_text(visit.webgl_renderer),
            _normalize_text(visit.webgl_extensions_hash),
            str(visit.webgl_max_texture or ""),
        ]
        if item
    )
    screen = "|".join(
        item
        for item in [
            _normalize_text(visit.screen_res),
            str(round(float(visit.pixel_ratio), 3)) if visit.pixel_ratio is not None else "",
            str(visit.screen_depth or ""),
            str(visit.touch_points if visit.touch_points is not None else ""),
            _normalize_text(visit.platform),
        ]
        if item
    )
    network = "|".join(
        item
        for item in [
            _normalize_text(visit.timezone),
            _normalize_text(visit.browser_language),
            _normalize_text(visit.ua_brands),
        ]
        if item
    )
    return {
        "canvas": _normalize_text(visit.canvas_hash),
        "audio": _normalize_text(visit.audio_fp),
        "webgl": webgl,
        "fonts": _normalize_list_text(visit.fonts),
        "screen": screen,
        "network": network,
    }


def component_hmac(value: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def composite_fingerprint(visit, secret: str) -> str | None:
    components = {key: value for key, value in fingerprint_components(visit).items() if value}
    if not components:
        return None
    payload = json.dumps(components, sort_keys=True, separators=(",", ":"))
    return component_hmac(payload, secret)
