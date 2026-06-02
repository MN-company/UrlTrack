import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import FrozenSet

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_URI = f"sqlite:///{(BASE_DIR / 'server' / 'data' / 'ulrtrack.db').resolve().as_posix()}"


def _load_dotenv() -> None:
    candidates = [
        BASE_DIR / ".env",
        Path(__file__).resolve().parent / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate)
            return
    load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


_load_dotenv()


@dataclass(frozen=True)
class Config:
    SECRET_KEY: str = os.environ["SECRET_KEY"]
    DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DB_URI)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    SERVER_URL: str = os.getenv("SERVER_URL", "http://127.0.0.1:8000")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
    TURNSTILE_SITE_KEY: str = os.getenv("TURNSTILE_SITE_KEY", "")
    TURNSTILE_SECRET_KEY: str = os.getenv("TURNSTILE_SECRET_KEY", "")
    THUMBMARK_API_KEY: str = os.getenv("THUMBMARK_API_KEY", "")
    THUMBMARK_API_URL: str = os.getenv("THUMBMARK_API_URL", "https://api.thumbmarkjs.com/thumbmark")
    TRUST_PROXY_HEADERS: bool = _bool_env("TRUST_PROXY_HEADERS", False)
    ANONYMIZE_IP: bool = _bool_env("ANONYMIZE_IP", True)
    REQUIRE_CONSENT: bool = _bool_env("REQUIRE_CONSENT", False)
    ALLOW_PARTIAL_EMAIL_CAPTURE: bool = _bool_env("ALLOW_PARTIAL_EMAIL_CAPTURE", False)
    CONSENT_COOKIE_NAME: str = os.getenv("CONSENT_COOKIE_NAME", "ulrtrack_consent")
    CONSENT_TTL_DAYS: int = _int_env("CONSENT_TTL_DAYS", 180)
    VISIT_RETENTION_DAYS: int = _int_env("VISIT_RETENTION_DAYS", 90)
    VISIT_TOKEN_TTL_SECONDS: int = _int_env("VISIT_TOKEN_TTL_SECONDS", 3600)
    REQUIRE_VISIT_TOKEN: bool = _bool_env("REQUIRE_VISIT_TOKEN", True)
    CSP_STRICT: bool = _bool_env("CSP_STRICT", True)
    MASK_WITH_ISGD: bool = _bool_env("MASK_WITH_ISGD", False)
    RATE_LIMIT_REDIRECT: str = os.getenv("RATE_LIMIT_REDIRECT", "60 per minute")
    RATE_LIMIT_AUTH: str = os.getenv("RATE_LIMIT_AUTH", "10 per minute")
    MAX_CONTENT_LENGTH: int = _int_env("MAX_CONTENT_LENGTH", 1_048_576)
    CACHE_DEFAULT_TIMEOUT: int = _int_env("CACHE_DEFAULT_TIMEOUT", 60)
    SESSION_COOKIE_SECURE: bool = _bool_env("SESSION_COOKIE_SECURE", False)
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SKIP_BACKGROUND_WORKER: bool = _bool_env("SKIP_BACKGROUND_WORKER", False)
    ADMIN_BOOTSTRAP_ENABLED: bool = _bool_env("ADMIN_BOOTSTRAP_ENABLED", True)
    SETUP_SECRET_LENGTH: int = _int_env("SETUP_SECRET_LENGTH", 24)
    MALICIOUS_IP_REFRESH_SECONDS: int = _int_env("MALICIOUS_IP_REFRESH_SECONDS", 21600)
    MALICIOUS_IP_MIN_COUNT: int = _int_env("MALICIOUS_IP_MIN_COUNT", 1000)
    SMART_FOLLOWUP_HOURS: int = _int_env("SMART_FOLLOWUP_HOURS", 48)
    BEACON_WAIT_SECONDS: int = _int_env("BEACON_WAIT_SECONDS", 3)
    FINGERPRINT_SECRET: str = os.getenv("FINGERPRINT_SECRET", os.environ["SECRET_KEY"])
    RESERVED_SLUGS: FrozenSet[str] = frozenset(
        {
            "dashboard",
            "login",
            "logout",
            "setup",
            "api",
            "fp",
            "static",
            "verify_captcha",
            "verify_password",
            "verify_email",
            "consent",
            "favicon.ico",
            "robots.txt",
        }
    )
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=24)
    WTF_CSRF_TIME_LIMIT: int = 86400
    WTF_CSRF_SSL_STRICT: bool = False
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    @classmethod
    def as_flask_config(cls) -> dict:
        config = cls()
        return {
            "SECRET_KEY": config.SECRET_KEY,
            "SQLALCHEMY_DATABASE_URI": config.DATABASE_URL,
            "SQLALCHEMY_TRACK_MODIFICATIONS": config.SQLALCHEMY_TRACK_MODIFICATIONS,
            "SESSION_COOKIE_SECURE": config.SESSION_COOKIE_SECURE,
            "SESSION_COOKIE_HTTPONLY": config.SESSION_COOKIE_HTTPONLY,
            "SESSION_COOKIE_SAMESITE": config.SESSION_COOKIE_SAMESITE,
            "SKIP_BACKGROUND_WORKER": config.SKIP_BACKGROUND_WORKER,
            "PERMANENT_SESSION_LIFETIME": config.PERMANENT_SESSION_LIFETIME,
            "WTF_CSRF_TIME_LIMIT": config.WTF_CSRF_TIME_LIMIT,
            "WTF_CSRF_SSL_STRICT": config.WTF_CSRF_SSL_STRICT,
            "MAX_CONTENT_LENGTH": config.MAX_CONTENT_LENGTH,
            "SERVER_URL": config.SERVER_URL,
            "TELEGRAM_BOT_TOKEN": config.TELEGRAM_BOT_TOKEN,
            "TELEGRAM_CHAT_ID": config.TELEGRAM_CHAT_ID,
            "WEBHOOK_URL": config.WEBHOOK_URL,
            "WEBHOOK_SECRET": config.WEBHOOK_SECRET,
            "GEMINI_API_KEY": config.GEMINI_API_KEY,
            "GEMINI_MODEL": config.GEMINI_MODEL,
            "TURNSTILE_SITE_KEY": config.TURNSTILE_SITE_KEY,
            "TURNSTILE_SECRET_KEY": config.TURNSTILE_SECRET_KEY,
            "THUMBMARK_API_KEY": config.THUMBMARK_API_KEY,
            "THUMBMARK_API_URL": config.THUMBMARK_API_URL,
            "TRUST_PROXY_HEADERS": config.TRUST_PROXY_HEADERS,
            "ANONYMIZE_IP": config.ANONYMIZE_IP,
            "VISIT_RETENTION_DAYS": config.VISIT_RETENTION_DAYS,
            "VISIT_TOKEN_TTL_SECONDS": config.VISIT_TOKEN_TTL_SECONDS,
            "REQUIRE_VISIT_TOKEN": config.REQUIRE_VISIT_TOKEN,
            "REQUIRE_CONSENT": config.REQUIRE_CONSENT,
            "ALLOW_PARTIAL_EMAIL_CAPTURE": config.ALLOW_PARTIAL_EMAIL_CAPTURE,
            "CONSENT_COOKIE_NAME": config.CONSENT_COOKIE_NAME,
            "CONSENT_TTL_DAYS": config.CONSENT_TTL_DAYS,
            "CSP_STRICT": config.CSP_STRICT,
            "MASK_WITH_ISGD": config.MASK_WITH_ISGD,
            "RATE_LIMIT_REDIRECT": config.RATE_LIMIT_REDIRECT,
            "RATE_LIMIT_AUTH": config.RATE_LIMIT_AUTH,
            "CACHE_DEFAULT_TIMEOUT": config.CACHE_DEFAULT_TIMEOUT,
            "ADMIN_BOOTSTRAP_ENABLED": config.ADMIN_BOOTSTRAP_ENABLED,
            "SETUP_SECRET_LENGTH": config.SETUP_SECRET_LENGTH,
            "MALICIOUS_IP_REFRESH_SECONDS": config.MALICIOUS_IP_REFRESH_SECONDS,
            "MALICIOUS_IP_MIN_COUNT": config.MALICIOUS_IP_MIN_COUNT,
            "SMART_FOLLOWUP_HOURS": config.SMART_FOLLOWUP_HOURS,
            "BEACON_WAIT_SECONDS": config.BEACON_WAIT_SECONDS,
            "FINGERPRINT_SECRET": config.FINGERPRINT_SECRET,
            "RESERVED_SLUGS": config.RESERVED_SLUGS,
        }
