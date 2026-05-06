import ipaddress
import json

from sqlalchemy import or_

from ..config import Config
from ..models import Visit
from .fingerprint import FINGERPRINT_VERSION, composite_fingerprint, fingerprint_components


IDENTITY_STRONG_THRESHOLD = 70
IDENTITY_POSSIBLE_THRESHOLD = 40
RISK_ALERT_THRESHOLD = 50


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


def apply_visit_scoring(visit: Visit, *, missing_beacon: bool = False, secret: str | None = None) -> dict:
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

    risk_score, risk_reasons, risk_conflicts = _risk_score(visit, missing_beacon)
    conflicts = sorted(set(best_conflicts + risk_conflicts))
    visit.identity_confidence = best_score
    visit.risk_score = risk_score
    visit.cluster_conflict = bool(conflicts)
    visit.conflict_reason = ", ".join(conflicts) if conflicts else None
    visit.match_reasons_json = json.dumps(
        {
            "identity": best_reasons,
            "risk": risk_reasons,
            "conflicts": conflicts,
            "matched_visit_id": matched_visit_id,
            "fingerprint_version": FINGERPRINT_VERSION,
        },
        sort_keys=True,
    )
    return {
        "identity_confidence": best_score,
        "risk_score": risk_score,
        "identity_reasons": best_reasons,
        "risk_reasons": risk_reasons,
        "conflicts": conflicts,
        "matched_visit_id": matched_visit_id,
    }
