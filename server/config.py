import os
from datetime import timedelta
from dotenv import load_dotenv
from typing import Optional, Set

# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    # Fallback to parent directory
    parent_env = os.path.join(os.path.dirname(basedir), '.env')
    if os.path.exists(parent_env):
        load_dotenv(parent_env)
    else:
        load_dotenv()

class Config:
    """Application Configuration."""
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'default_dev_secret')
    PRODUCTION: bool = os.getenv('PRODUCTION', '').lower() in ('1', 'true', 'yes', 'on')
    
    # Database
    db_path = os.path.join(basedir, 'instance', 'shortener.db')
    if not os.path.exists(os.path.dirname(db_path)):
        db_path = os.path.join(basedir, 'shortener.db')
        
    SQLALCHEMY_DATABASE_URI: str = os.getenv('DATABASE_URL', f'sqlite:///{db_path}')
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    
    # Security / Session
    SESSION_COOKIE_SECURE: bool = PRODUCTION
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    WTF_CSRF_TIME_LIMIT: int = 86400 # Match session lifetime (seconds)
    WTF_CSRF_SSL_STRICT: bool = False # Allow HTTP for dev/internal proxies
    
    # API Keys & Integrations
    API_KEY: str = os.getenv('API_KEY', 'changeme')
    SERVER_URL: str = os.getenv('SERVER_URL', 'http://127.0.0.1:8080')
    GEMINI_API_KEY: Optional[str] = os.getenv('GEMINI_API_KEY')
    
    TURNSTILE_SITE_KEY: str = os.getenv('TURNSTILE_SITE_KEY', '')
    TURNSTILE_SECRET_KEY: str = os.getenv('TURNSTILE_SECRET_KEY', '')
    
    # AI Configuration
    GEMINI_MODEL: str = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    AI_PROMPT: str = os.getenv(
        'AI_PROMPT',
        os.getenv('AI_SYSTEM_PROMPT', 'You are a cybersecurity expert analyzing user agents and device fingerprints.')
    )
    
    # OSINT Tools
    HOLEHE_CMD: str = os.getenv('HOLEHE_CMD', 'holehe')
    WEBHOOK_URL: Optional[str] = os.getenv('WEBHOOK_URL')

    # Proxy / Security Controls
    TRUST_PROXY_HEADERS: bool = os.getenv('TRUST_PROXY_HEADERS', '').lower() in ('1', 'true', 'yes', 'on')
    REQUIRE_VISIT_TOKEN: bool = os.getenv(
        'REQUIRE_VISIT_TOKEN',
        'true' if PRODUCTION else 'false'
    ).lower() in ('1', 'true', 'yes', 'on')
    VISIT_TOKEN_TTL_SECONDS: int = int(os.getenv('VISIT_TOKEN_TTL_SECONDS', '3600'))
    ALLOW_CREDENTIAL_CAPTURE: bool = os.getenv('ALLOW_CREDENTIAL_CAPTURE', '').lower() in ('1', 'true', 'yes', 'on')
    ALLOW_PARTIAL_EMAIL_CAPTURE: bool = os.getenv('ALLOW_PARTIAL_EMAIL_CAPTURE', '').lower() in ('1', 'true', 'yes', 'on')
    REQUIRE_CONSENT: bool = os.getenv('REQUIRE_CONSENT', '').lower() in ('1', 'true', 'yes', 'on')
    CONSENT_COOKIE_NAME: str = os.getenv('CONSENT_COOKIE_NAME', 'ulrtrack_consent')
    CONSENT_TTL_DAYS: int = int(os.getenv('CONSENT_TTL_DAYS', '180'))
    ANONYMIZE_IP: bool = os.getenv('ANONYMIZE_IP', '').lower() in ('1', 'true', 'yes', 'on')
    VISIT_RETENTION_DAYS: int = int(os.getenv('VISIT_RETENTION_DAYS', '0'))
    MALICIOUS_IP_REFRESH_SECONDS: int = int(os.getenv('MALICIOUS_IP_REFRESH_SECONDS', '21600'))
    MALICIOUS_IP_MIN_COUNT: int = int(os.getenv('MALICIOUS_IP_MIN_COUNT', '1000'))
    CUSTOM_HTML_LOCKDOWN: bool = os.getenv('CUSTOM_HTML_LOCKDOWN', '').lower() in ('1', 'true', 'yes', 'on')
    CSP_STRICT: bool = os.getenv('CSP_STRICT', '').lower() in ('1', 'true', 'yes', 'on')

    RESERVED_SLUGS: Set[str] = {
        'dashboard', 'login', 'logout', 'api', 'static', 'verify_captcha',
        'verify_password', 'verify_email', 'favicon.ico', 'robots.txt'
        , 'consent'
    }
