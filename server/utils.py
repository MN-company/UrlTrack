import ipaddress
import json
import math
import os
import random
import string
import time
from functools import lru_cache
from typing import Any, Dict, Optional, Set, Tuple

import requests
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import Config


http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
http_session.mount("http://", adapter)
http_session.mount("https://", adapter)


def safe_json(value, default=None):
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def sanitize(value: str, max_len: int = 2048) -> str:
    if not value:
        return ""
    return str(value).strip()[:max_len]


def generate_slug(length: int = 6) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def is_bot_ua(ua_string: str) -> bool:
    if not ua_string:
        return False
    bots = [
        "bot",
        "crawl",
        "slurp",
        "spider",
        "curl",
        "wget",
        "facebook",
        "whatsapp",
        "telegram",
        "expand",
        "preview",
        "peeker",
        "twitter",
        "discord",
        "slack",
        "go-http-client",
        "python-requests",
        "headless",
        "phantomjs",
        "puppeteer",
        "selenium",
        "urlscan",
        "lighthouse",
        "gtmetrix",
        "pingdom",
    ]
    ua_lower = ua_string.lower()
    return any(bot in ua_lower for bot in bots)


def calculate_entropy(text: str) -> float:
    if not text:
        return 0.0
    entropy = 0.0
    length = len(text)
    for char in set(text):
        probability = text.count(char) / length
        entropy -= probability * math.log2(probability)
    return entropy


def is_gibberish_email(email: str) -> Tuple[bool, Optional[str]]:
    if not email or "@" not in email:
        return True, "Invalid Format"

    local_part = email.split("@", 1)[0].lower()
    if len(local_part) < 3:
        return True, "Too Short"

    entropy = calculate_entropy(local_part)
    if entropy < 1.0 and len(local_part) > 3:
        return True, "Low Entropy (Repetitive)"

    vowels = "aeiouy"
    consecutive = 0
    longest = 0
    for char in local_part:
        if char.isalpha():
            if char not in vowels:
                consecutive += 1
                longest = max(longest, consecutive)
            else:
                consecutive = 0
    if longest > 5:
        return True, "High Consonant Cluster"

    bad_patterns = ["asdf", "qwer", "zxcv", "1234", "test", "demo", "qwerty"]
    if any(pattern in local_part for pattern in bad_patterns):
        return True, "Common Pattern"

    return False, None


def validate_email_strict(email: str) -> Tuple[bool, str]:
    import re

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email or ""):
        return False, "Invalid email syntax."
    gibberish, reason = is_gibberish_email(email)
    if gibberish:
        return False, f"Gibberish detected: {reason}"
    return True, "Valid"


@lru_cache(maxsize=1000)
def shorten_with_isgd(url: str) -> Optional[str]:
    try:
        response = http_session.get(
            "https://is.gd/create.php",
            params={"format": "simple", "url": url},
            timeout=5,
        )
        if response.status_code == 200:
            return response.text.strip()
    except Exception as exc:
        print(f"is.gd error: {exc}")
    return None


def get_geo_data(ip: str) -> Dict[str, Any]:
    now = time.time()
    cached = _geo_cache.get(ip)
    if cached is not None:
        ts, data = cached
        if now - ts < _GEO_TTL and data:
            return data
    try:
        fields = "status,country,city,lat,lon,isp,org,as,proxy,hosting,mobile,query,countryCode"
        response = http_session.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": fields},
            timeout=3.0,
        )
        payload = response.json()
        if payload.get("status") == "success":
            _geo_cache[ip] = (now, payload)
            return payload
    except Exception as exc:
        print(f"Geo lookup failed for {ip}: {exc}")
    return {}


def get_reverse_dns(ip: str) -> Optional[str]:
    import socket

    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except Exception:
        return None


def parse_referrer(url: str) -> Dict[str, Any]:
    if not url:
        return {"domain": None, "platform": "Direct", "utm": {}}

    from urllib.parse import parse_qs, urlparse

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        platform = "Unknown"
        if "google" in domain:
            platform = "Google"
        elif "facebook" in domain or "fb.com" in domain:
            platform = "Facebook"
        elif "twitter" in domain or "t.co" in domain or "x.com" in domain:
            platform = "Twitter/X"
        elif "linkedin" in domain:
            platform = "LinkedIn"
        elif "instagram" in domain:
            platform = "Instagram"
        elif "youtube" in domain:
            platform = "YouTube"
        elif "tiktok" in domain:
            platform = "TikTok"
        elif "reddit" in domain:
            platform = "Reddit"
        elif "telegram" in domain or "t.me" in domain:
            platform = "Telegram"
        elif "whatsapp" in domain:
            platform = "WhatsApp"
        else:
            platform = domain or "Unknown"

        utm = {}
        for key in ("utm_source", "utm_medium", "utm_campaign", "utm_content"):
            values = parse_qs(parsed.query).get(key)
            if values:
                utm[key] = values[0]
        return {"domain": domain, "platform": platform, "utm": utm}
    except Exception:
        return {"domain": url, "platform": "Unknown", "utm": {}}


def load_domain_list(filename: str) -> Set[str]:
    domains: Set[str] = set()
    try:
        path = os.path.join(os.path.dirname(__file__), "data", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                domains = {line.strip().lower() for line in handle if line.strip()}
    except Exception as exc:
        print(f"Error loading {filename}: {exc}")
    return domains


_domain_cache: Dict[str, Tuple[float, Set[str]]] = {}
_DOMAIN_CACHE_TTL = 300
_geo_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_GEO_TTL = 3600


def _load_domain_list_cached(filename: str) -> Set[str]:
    now = time.time()
    cached = _domain_cache.get(filename)
    if cached is not None:
        ts, data = cached
        if now - ts < _DOMAIN_CACHE_TTL:
            return data

    data = load_domain_list(filename)
    _domain_cache[filename] = (now, data)
    return data


def invalidate_domain_cache() -> None:
    _domain_cache.clear()


_MALICIOUS_IPS: Optional[Set[str]] = None
_MALICIOUS_IPS_LAST_REFRESH = 0.0


def load_malicious_ips() -> Set[str]:
    global _MALICIOUS_IPS
    global _MALICIOUS_IPS_LAST_REFRESH

    if _MALICIOUS_IPS is not None:
        if time.time() - _MALICIOUS_IPS_LAST_REFRESH < Config.MALICIOUS_IP_REFRESH_SECONDS:
            return _MALICIOUS_IPS

    _MALICIOUS_IPS = set()
    cache_path = os.path.join(os.path.dirname(__file__), "data", "malicious_ips.txt")

    try:
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as handle:
                cached = set()
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        ipaddress.ip_address(line)
                        cached.add(line)
                    except ValueError:
                        continue
            if cached:
                _MALICIOUS_IPS = cached
                _MALICIOUS_IPS_LAST_REFRESH = time.time()

        response = http_session.get(
            "https://raw.githubusercontent.com/sefinek/Malicious-IP-Addresses/main/lists/main.txt",
            timeout=5,
        )
        if response.status_code == 200:
            fresh = set()
            for line in response.text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    ipaddress.ip_address(line)
                    fresh.add(line)
                except ValueError:
                    continue
            if len(fresh) >= Config.MALICIOUS_IP_MIN_COUNT:
                _MALICIOUS_IPS = fresh
                _MALICIOUS_IPS_LAST_REFRESH = time.time()
                with open(cache_path, "w", encoding="utf-8") as handle:
                    handle.write("\n".join(sorted(fresh)))
    except Exception as exc:
        print(f"Error loading malicious IPs: {exc}")

    return _MALICIOUS_IPS or set()


def anonymize_ip(ip: str) -> str:
    try:
        address = ipaddress.ip_address(ip)
        if address.version == 4:
            parts = ip.split(".")
            if len(parts) == 4:
                parts[-1] = "0"
                return ".".join(parts)
        else:
            network = ipaddress.IPv6Network(f"{ip}/64", strict=False)
            return str(network.network_address)
    except Exception:
        return ip
    return ip


def should_require_consent(request) -> bool:
    if not Config.REQUIRE_CONSENT:
        return False
    return request.cookies.get(Config.CONSENT_COOKIE_NAME) != "1"


def is_malicious_ip(ip: str) -> bool:
    return ip in load_malicious_ips()


def is_disposable_email(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    return domain in _load_domain_list_cached("disposable_domains.txt")


def is_privacy_email(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    return domain in _load_domain_list_cached("privacy_domains.txt")


def verify_turnstile(token: str, ip: str) -> bool:
    if not Config.TURNSTILE_SECRET_KEY:
        return False
    if not token:
        return False
    try:
        response = http_session.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": Config.TURNSTILE_SECRET_KEY, "response": token, "remoteip": ip},
            timeout=5,
        )
        payload = response.json()
        return bool(payload.get("success"))
    except Exception as exc:
        print(f"Turnstile verification failed: {exc}")
        return False


def _visit_token_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(Config.SECRET_KEY, salt="visit-token")


def sign_visit_token(visit_id: Any) -> Optional[str]:
    try:
        return _visit_token_serializer().dumps({"v": int(visit_id)})
    except Exception:
        return None


def verify_visit_token(token: Optional[str], max_age: int) -> Optional[int]:
    if not token:
        return None
    try:
        data = _visit_token_serializer().loads(token, max_age=max_age)
        value = data.get("v")
        return int(value) if value is not None else None
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None
