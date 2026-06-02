import ipaddress
import json
from datetime import datetime

from sqlalchemy import or_

from ..config import Config
from ..extensions import db
from ..models import Visit, Visitor, VisitorSignal
from .fingerprint import FINGERPRINT_VERSION, composite_fingerprint, fingerprint_components
from .thumbmark import maybe_enrich_thumbmark_api


IDENTITY_STRONG_THRESHOLD = 70
IDENTITY_POSSIBLE_THRESHOLD = 40
RISK_ALERT_THRESHOLD = 50
MATCH_THRESHOLD = 60
PROBABLE_THRESHOLD = 30

SIGNAL_WEIGHTS = {
    "email": 40,
    "thumbmark_visitor_id": 35,
    "thumbmark_hash": 20,
    "audio_hash": 18,
    "canvas_hash": 18,
    "webgl_hash": 15,
    "fonts_hash": 12,
    "hardware_profile": 10,
    "speech_hash": 10,
    "webrtc_ip": 10,
    "math_hash": 8,
    "screen_profile": 8,
    "timezone": 6,
    "language": 5,
    "media_devices": 5,
    "ip_address": 5,
}

PENALTIES = {
    "vpn_datacenter": -10,
    "known_bot": -50,
}


_COUNTRY_TIMEZONE_REGIONS = {
    "IT": ("europe/",),
    "FR": ("europe/",),
    "DE": ("europe/",),
    "ES": ("europe/",),
    "GB": ("europe/",),
    "NL": ("europe/",),
    "CH": ("europe/",),
    "US": ("america/", "us/"),
    "CA": ("america/", "canada/"),
    "BR": ("america/",),
    "MX": ("america/",),
    "JP": ("asia/",),
    "CN": ("asia/",),
    "IN": ("asia/",),
    "AU": ("australia/",),
}


def _same_ip_network(first: str | None, second: str | None) -> bool:
    if not first or not second:
        return False
    try:
        first_ip = ipaddress.ip_address(first)
        second_ip = ipaddress.ip_address(second)
        if first_ip.version != second_ip.version:
            return False
        prefix = 24 if first_ip.version == 4 else 64
        return ipaddress.ip_network(f"{first_ip}/{prefix}", strict=False) == ipaddress.ip_network(
            f"{second_ip}/{prefix}",
            strict=False,
        )
    except ValueError:
        return first == second


def _font_similarity(first: str, second: str) -> float:
    first_set = {item for item in first.split(",") if item}
    second_set = {item for item in second.split(",") if item}
    if not first_set or not second_set:
        return 0.0
    return len(first_set & second_set) / len(first_set | second_set)


def _country_timezone_conflict(visit: Visit) -> bool:
    country = (visit.country_code or "").upper()
    timezone = (visit.timezone or "").strip().lower()
    if not country or not timezone:
        return False
    expected_prefixes = _COUNTRY_TIMEZONE_REGIONS.get(country)
    if not expected_prefixes:
        return False
    return not timezone.startswith(expected_prefixes)


def _privacy_extension_detected(visit: Visit) -> bool:
    if visit.adblock:
        return True
    try:
        extensions = json.loads(visit.extensions_detected or "[]")
    except (TypeError, ValueError):
        extensions = []
    privacy_keywords = ("ublock", "adblock", "privacy badger", "dark reader")
    return any(any(keyword in str(ext).lower() for keyword in privacy_keywords) for ext in extensions)


def _load_candidates(visit: Visit, composite: str | None) -> list[Visit]:
    filters = []
    if visit.email:
        filters.append(Visit.email == visit.email)
    if visit.canvas_hash:
        filters.append(Visit.canvas_hash == visit.canvas_hash)
    if composite:
        filters.append(Visit.fingerprint_composite_v1 == composite)
    if visit.ip_address:
        filters.append(Visit.ip_address == visit.ip_address)
    if not filters:
        return []
    return (
        Visit.query.filter(Visit.id != visit.id)
        .filter(or_(*filters))
        .order_by(Visit.timestamp.desc())
        .limit(100)
        .all()
    )


def _score_identity_against(visit: Visit, candidate: Visit, current_components: dict[str, str]) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []
    conflicts: list[str] = []
    candidate_components = fingerprint_components(candidate)

    if visit.email and candidate.email:
        if visit.email.lower() == candidate.email.lower():
            score += 40
            reasons.append("same_email")
        else:
            score -= 15
            conflicts.append("email_conflict")

    if visit.fingerprint_composite_v1 and candidate.fingerprint_composite_v1:
        if visit.fingerprint_composite_v1 == candidate.fingerprint_composite_v1:
            score += 15
            reasons.append("same_composite_fingerprint")

    component_matches = 0
    component_conflicts = 0
    component_weights = {
        "canvas": 12,
        "audio": 8,
        "webgl": 8,
        "network": 5,
        "screen": 4,
    }
    for key, weight in component_weights.items():
        current_value = current_components.get(key)
        candidate_value = candidate_components.get(key)
        if not current_value or not candidate_value:
            continue
        if current_value == candidate_value:
            component_matches += 1
            score += weight
            reasons.append(f"same_{key}")
        else:
            component_conflicts += 1

    fonts_similarity = _font_similarity(current_components.get("fonts", ""), candidate_components.get("fonts", ""))
    if fonts_similarity >= 0.6:
        score += 6
        reasons.append("similar_fonts")
        component_matches += 1

    if visit.device_type and candidate.device_type and visit.device_type == candidate.device_type:
        score += 4
        reasons.append("same_device_class")
    if visit.os_family and candidate.os_family and visit.os_family == candidate.os_family:
        score += 4
        reasons.append("same_os_family")
    if _same_ip_network(visit.ip_address, candidate.ip_address):
        score += 3
        reasons.append("same_ip_network")

    if candidate.review_label == "same_user":
        score += 10
        reasons.append("human_confirmed_same_user")
    if candidate.review_label == "false_match":
        score -= 25
        conflicts.append("human_marked_false_match")

    if component_conflicts >= 3 and component_matches <= 1:
        score -= 20
        conflicts.append("strong_fingerprint_conflict")

    return max(0, min(100, score)), reasons, conflicts


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _json_array_append(payload: str | None, value: str | None) -> str | None:
    if not value:
        return payload
    try:
        items = json.loads(payload or "[]")
    except (TypeError, ValueError):
        items = []
    if not isinstance(items, list):
        items = []
    if value not in items:
        items.append(value)
    return json.dumps(items)


def _normalize_signal_value(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"))
    value = str(value).strip()
    return value if value else None


def _first_csv(value: str | None) -> str | None:
    if not value:
        return None
    return next((part.strip() for part in value.split(",") if part.strip()), None)


def _legacy_screen_profile(visit: Visit) -> str | None:
    if not visit.screen_res:
        return None
    depth = visit.screen_depth if visit.screen_depth is not None else 0
    ratio = visit.pixel_ratio if visit.pixel_ratio is not None else 1
    return f"{visit.screen_res}x{depth}@{ratio}"


def _legacy_hardware_profile(visit: Visit) -> str | None:
    if visit.cpu_cores is None and visit.ram_gb is None and visit.touch_points is None:
        return None
    cores = visit.cpu_cores or 0
    memory = visit.ram_gb or 0
    touch = visit.touch_points or 0
    return f"{cores}c/{memory}gb/{touch}tp"


def _legacy_webrtc_ip(visit: Visit) -> str | None:
    if not visit.webrtc_ips:
        return None
    try:
        values = json.loads(visit.webrtc_ips)
    except (TypeError, ValueError):
        values = visit.webrtc_ips.split(",")
    if not isinstance(values, list):
        return None
    for value in values:
        normalized = _normalize_signal_value(value)
        if normalized:
            return normalized
    return None


def _extract_signals_from_visit(visit: Visit) -> dict[str, str]:
    signals = {
        "thumbmark_visitor_id": visit.thumbmark_visitor_id,
        "thumbmark_hash": visit.thumbmark_hash,
        "canvas_hash": visit.fp_canvas_hash or visit.canvas_hash,
        "audio_hash": visit.fp_audio_hash or visit.audio_fp,
        "webgl_hash": visit.fp_webgl_hash or visit.webgl_extensions_hash,
        "fonts_hash": visit.fp_fonts_hash or visit.fonts,
        "screen_profile": visit.fp_screen_profile or _legacy_screen_profile(visit),
        "hardware_profile": visit.fp_hardware_profile or _legacy_hardware_profile(visit),
        "language": _first_csv(visit.fp_languages) or visit.browser_language,
        "timezone": visit.fp_timezone or visit.timezone,
        "speech_hash": visit.fp_speech_hash,
        "math_hash": visit.fp_math_hash,
        "media_devices": visit.fp_media_devices,
        "webrtc_ip": _first_csv(visit.fp_webrtc_ips) or _legacy_webrtc_ip(visit),
        "email": visit.email,
        "ip_address": visit.ip_address,
    }
    return {
        signal_type: normalized
        for signal_type, value in signals.items()
        if (normalized := _normalize_signal_value(value))
    }


def _update_visitor_rollups(visitor: Visitor, visit: Visit, signals: dict[str, str]) -> None:
    visitor.primary_thumbmark_hash = visitor.primary_thumbmark_hash or signals.get("thumbmark_hash")
    visitor.primary_thumbmark_visitor_id = visitor.primary_thumbmark_visitor_id or signals.get("thumbmark_visitor_id")
    visitor.known_canvas_hashes = _json_array_append(visitor.known_canvas_hashes, signals.get("canvas_hash"))
    visitor.known_audio_hashes = _json_array_append(visitor.known_audio_hashes, signals.get("audio_hash"))
    visitor.known_webgl_vendors = _json_array_append(
        visitor.known_webgl_vendors,
        _normalize_signal_value(visit.fp_webgl_vendor or visit.webgl_vendor or visit.webgl_renderer),
    )
    visitor.known_screen_profiles = _json_array_append(visitor.known_screen_profiles, signals.get("screen_profile"))
    visitor.known_timezones = _json_array_append(visitor.known_timezones, signals.get("timezone"))
    visitor.known_languages = _json_array_append(visitor.known_languages, signals.get("language"))
    visitor.known_thumbmark_visitor_ids = _json_array_append(
        visitor.known_thumbmark_visitor_ids,
        signals.get("thumbmark_visitor_id"),
    )
    timestamp = visit.timestamp or datetime.utcnow()
    visitor.first_seen = min(filter(None, [visitor.first_seen, timestamp]), default=timestamp)
    visitor.last_seen = max(filter(None, [visitor.last_seen, timestamp]), default=timestamp)
    visitor.updated_at = datetime.utcnow()


def _update_api_stats(visitor: Visitor) -> None:
    db.session.flush()
    api_visits = Visit.query.filter(
        Visit.visitor_id == visitor.id,
        Visit.thumbmark_api_called.is_(True),
    ).all()
    confidences = [
        visit.thumbmark_api_confidence
        for visit in api_visits
        if isinstance(visit.thumbmark_api_confidence, (int, float))
    ]
    visitor.thumbmark_api_calls_count = len(api_visits)
    visitor.thumbmark_api_confidence_avg = (sum(confidences) / len(confidences)) if confidences else None


def _update_visitor_signals(visitor_id: str, visit: Visit, signals: dict[str, str]) -> Visitor:
    visitor = db.session.get(Visitor, visitor_id)
    if visitor is None:
        visitor = Visitor(id=visitor_id)
        db.session.add(visitor)
        db.session.flush()

    visit.visitor_id = visitor.id
    timestamp = visit.timestamp or datetime.utcnow()
    for signal_type, signal_value in signals.items():
        weight = SIGNAL_WEIGHTS.get(signal_type, 0)
        existing = VisitorSignal.query.filter_by(
            visitor_id=visitor.id,
            signal_type=signal_type,
            signal_value=signal_value,
        ).first()
        if existing:
            if existing.visit_id != visit.id:
                existing.occurrence_count += 1
            existing.visit_id = visit.id
            existing.last_seen = timestamp
            existing.confidence_weight = weight
        else:
            db.session.add(
                VisitorSignal(
                    visitor_id=visitor.id,
                    visit_id=visit.id,
                    signal_type=signal_type,
                    signal_value=signal_value,
                    confidence_weight=weight,
                    first_seen=timestamp,
                    last_seen=timestamp,
                )
            )

    _update_visitor_rollups(visitor, visit, signals)
    _update_api_stats(visitor)
    return visitor


def _create_new_visitor(visit: Visit, signals: dict[str, str]) -> Visitor:
    timestamp = visit.timestamp or datetime.utcnow()
    visitor = Visitor(first_seen=timestamp, last_seen=timestamp)
    db.session.add(visitor)
    db.session.flush()
    return _update_visitor_signals(visitor.id, visit, signals)


def _ensure_visitor_for_visit(visit: Visit) -> Visitor:
    signals = _extract_signals_from_visit(visit)
    if visit.visitor_id:
        return _update_visitor_signals(visit.visitor_id, visit, signals)
    return _create_new_visitor(visit, signals)


def _candidate_scores(signals: dict[str, str], *, exclude_visitor_id: str | None = None) -> dict[str, int]:
    candidates: dict[str, int] = {}
    for signal_type, signal_value in signals.items():
        weight = SIGNAL_WEIGHTS.get(signal_type, 0)
        if not weight:
            continue
        matches = VisitorSignal.query.filter_by(signal_type=signal_type, signal_value=signal_value).all()
        for match in matches:
            if exclude_visitor_id and match.visitor_id == exclude_visitor_id:
                continue
            candidates[match.visitor_id] = candidates.get(match.visitor_id, 0) + weight
    return candidates


def _signal_match_reasons(visitor_id: str, signals: dict[str, str]) -> list[str]:
    reasons = []
    for signal_type, signal_value in signals.items():
        if VisitorSignal.query.filter_by(
            visitor_id=visitor_id,
            signal_type=signal_type,
            signal_value=signal_value,
        ).first():
            reasons.append(signal_type)
    return reasons


def match_visitor(visit: Visit, *, allow_reassign: bool = False) -> tuple[str, int, list[str]]:
    signals = _extract_signals_from_visit(visit)
    if visit.visitor_id and not allow_reassign:
        _update_visitor_signals(visit.visitor_id, visit, signals)
        return visit.visitor_id, visit.identity_confidence or 0, ["existing_visitor"]

    candidates = _candidate_scores(signals, exclude_visitor_id=visit.visitor_id if allow_reassign else None)
    if visit.is_vpn or visit.is_proxy or visit.is_hosting:
        for visitor_id in candidates:
            candidates[visitor_id] += PENALTIES["vpn_datacenter"]
    if visit.browser_bot:
        for visitor_id in candidates:
            candidates[visitor_id] += PENALTIES["known_bot"]

    if not candidates:
        if visit.visitor_id:
            _update_visitor_signals(visit.visitor_id, visit, signals)
            return visit.visitor_id, 0, ["existing_visitor"]
        visitor = _create_new_visitor(visit, signals)
        return visitor.id, 0, ["new_visitor"]

    best_id = max(candidates, key=candidates.get)
    best_score = max(0, min(100, candidates[best_id]))
    reasons = _signal_match_reasons(best_id, signals)

    if best_score >= MATCH_THRESHOLD:
        visit.probable_visitor_id = None
        _update_visitor_signals(best_id, visit, signals)
        return best_id, best_score, reasons

    if best_score >= PROBABLE_THRESHOLD:
        visitor = _create_new_visitor(visit, signals)
        visitor.probable_match_id = best_id
        visit.probable_visitor_id = best_id
        return visitor.id, best_score, ["probable_match"] + reasons

    if visit.visitor_id:
        _update_visitor_signals(visit.visitor_id, visit, signals)
        return visit.visitor_id, 0, ["existing_visitor"]
    visitor = _create_new_visitor(visit, signals)
    return visitor.id, 0, ["new_visitor"]


def _risk_score(visit: Visit, missing_beacon: bool) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []
    conflicts: list[str] = []
    notes = (visit.notes or "").lower()

    if "malicious ip" in notes:
        score += 25
        reasons.append("malicious_ip")
    if visit.is_vpn or visit.is_proxy or visit.is_hosting:
        score += 20
        reasons.append("vpn_proxy_or_hosting")
    if visit.browser_bot:
        score += 20
        reasons.append("webdriver_or_headless")
    if _country_timezone_conflict(visit):
        score += 15
        conflicts.append("country_timezone_mismatch")
    if missing_beacon:
        score += 15
        reasons.append("missing_beacon")
    if visit.beacon_received_at and not visit.canvas_hash and not visit.audio_fp:
        score += 10
        reasons.append("missing_expected_fingerprints")
    if isinstance(visit.dwell_ms, int) and visit.dwell_ms < 500:
        score += 10
        reasons.append("abnormal_dwell")
    if _privacy_extension_detected(visit):
        score += 8
        reasons.append("adblock_or_privacy_extension")
    if visit.review_label == "bot":
        score += 30
        reasons.append("human_marked_bot")
    if visit.review_label == "suspicious":
        score += 15
        reasons.append("human_marked_suspicious")
    if visit.review_label == "clean":
        score = max(0, score - 10)
        reasons.append("human_marked_clean")

    return min(100, score), reasons, conflicts


def apply_visit_scoring(
    visit: Visit,
    *,
    missing_beacon: bool = False,
    secret: str | None = None,
    use_thumbmark_api: bool = False,
) -> dict:
    secret = secret or Config.FINGERPRINT_SECRET
    visit.fingerprint_version = FINGERPRINT_VERSION
    visit.fingerprint_composite_v1 = composite_fingerprint(visit, secret) or visit.fingerprint_composite_v1

    components = fingerprint_components(visit)
    best_score = 0
    best_reasons: list[str] = []
    best_conflicts: list[str] = []
    matched_visit_id = None

    for candidate in _load_candidates(visit, visit.fingerprint_composite_v1):
        candidate_score, reasons, conflicts = _score_identity_against(visit, candidate, components)
        if candidate_score > best_score:
            best_score = candidate_score
            best_reasons = reasons
            best_conflicts = conflicts
            matched_visit_id = candidate.id

    if matched_visit_id and "human_marked_false_match" not in best_conflicts:
        matched_visit = db.session.get(Visit, matched_visit_id)
        if matched_visit is not None:
            _ensure_visitor_for_visit(matched_visit)

    allow_signal_reassign = bool(visit.visitor_id and (visit.identity_confidence or 0) < PROBABLE_THRESHOLD)
    visitor_id, signal_score, signal_reasons = match_visitor(visit, allow_reassign=allow_signal_reassign)
    identity_score = max(best_score, signal_score)
    identity_reasons = _ordered_unique(best_reasons + signal_reasons)

    if use_thumbmark_api:
        api_result = maybe_enrich_thumbmark_api(visit, identity_score)
        if api_result is not None:
            visitor_id, api_signal_score, api_reasons = match_visitor(visit, allow_reassign=True)
            identity_score = max(identity_score, api_signal_score)
            identity_reasons = _ordered_unique(identity_reasons + api_reasons)

    if "human_marked_false_match" in best_conflicts:
        identity_score = min(identity_score, best_score)

    risk_score, risk_reasons, risk_conflicts = _risk_score(visit, missing_beacon)
    conflicts = sorted(set(best_conflicts + risk_conflicts))
    visit.identity_confidence = identity_score
    visit.risk_score = risk_score
    visit.cluster_conflict = bool(conflicts)
    visit.conflict_reason = ", ".join(conflicts) if conflicts else None
    visit.match_reasons_json = json.dumps(
        {
            "identity": identity_reasons,
            "risk": risk_reasons,
            "conflicts": conflicts,
            "matched_visit_id": matched_visit_id,
            "visitor_id": visitor_id,
            "probable_visitor_id": visit.probable_visitor_id,
            "thumbmark_api_called": bool(visit.thumbmark_api_called),
            "thumbmark_api_error": visit.thumbmark_api_error,
            "fingerprint_version": FINGERPRINT_VERSION,
        },
        sort_keys=True,
    )
    return {
        "identity_confidence": identity_score,
        "risk_score": risk_score,
        "identity_reasons": identity_reasons,
        "risk_reasons": risk_reasons,
        "conflicts": conflicts,
        "matched_visit_id": matched_visit_id,
        "visitor_id": visitor_id,
    }
