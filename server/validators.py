import re
from typing import Iterable, Optional
from urllib.parse import urlparse, urlunparse

SAFE_SCHEMES = {"http", "https"}
SLUG_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")


def parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def validate_slug(slug: str, reserved: Iterable[str]) -> Optional[str]:
    if not slug:
        return "Slug is required."
    if not SLUG_RE.match(slug):
        return "Slug must be 3-20 chars and contain only letters, numbers, '-' or '_'."
    if slug.lower() in {s.lower() for s in reserved}:
        return "Slug is reserved. Choose a different one."
    return None


def normalize_destination_url(raw_url: str) -> str:
    if raw_url is None:
        raise ValueError("URL is required.")
    url = raw_url.strip()
    if not url:
        raise ValueError("URL is required.")

    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    if parsed.scheme.lower() not in SAFE_SCHEMES:
        raise ValueError("Only http/https URLs are allowed.")
    if not parsed.netloc:
        raise ValueError("URL must include a valid host.")

    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)


def normalize_optional_url(raw_url: Optional[str]) -> Optional[str]:
    if raw_url is None:
        return None
    url = raw_url.strip()
    if not url:
        return None
    return normalize_destination_url(url)


def get_client_ip(request, trust_proxy_headers: bool = False) -> str:
    if trust_proxy_headers:
        xff = request.headers.get('X-Forwarded-For', '')
        if xff:
            parts = [p.strip() for p in xff.split(',') if p.strip()]
            if parts:
                return parts[0]
        x_real_ip = request.headers.get('X-Real-IP')
        if x_real_ip:
            return x_real_ip
    return request.remote_addr
