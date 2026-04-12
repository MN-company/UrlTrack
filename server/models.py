import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def _safe_json_loads(value: Optional[str], default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class DatabaseModel(db.Model):
    __abstract__ = True

    def to_dict(self) -> Dict[str, Any]:
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class Link(DatabaseModel):
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    destination: Mapped[str] = mapped_column(String(2048), nullable=False)

    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    enable_captcha: Mapped[bool] = mapped_column(Boolean, default=False)
    max_clicks: Mapped[int] = mapped_column(Integer, default=0)
    expire_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expiration_minutes: Mapped[int] = mapped_column(Integer, default=0)

    ios_url: Mapped[Optional[str]] = mapped_column(String(2048))
    android_url: Mapped[Optional[str]] = mapped_column(String(2048))
    safe_url: Mapped[Optional[str]] = mapped_column(String(2048))
    block_vpn: Mapped[bool] = mapped_column(Boolean, default=False)
    block_bots: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_no_js: Mapped[bool] = mapped_column(Boolean, default=False)

    schedule_start_hour: Mapped[Optional[int]] = mapped_column(Integer)
    schedule_end_hour: Mapped[Optional[int]] = mapped_column(Integer)
    schedule_timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    block_adblock: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_countries: Mapped[Optional[str]] = mapped_column(String(50))

    public_masked_url: Mapped[Optional[str]] = mapped_column(String(512))
    require_email: Mapped[bool] = mapped_column(Boolean, default=False)
    email_policy: Mapped[str] = mapped_column(String(20), default="all")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    visits: Mapped[List["Visit"]] = relationship(
        back_populates="link",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Visit(DatabaseModel):
    __table_args__ = (
        Index("ix_visit_link_id_ts", "link_id", "timestamp"),
        Index("ix_visit_canvas_hash", "canvas_hash"),
        Index("ix_visit_ip", "ip_address"),
        Index("ix_visit_email", "email"),
        Index("ix_visit_etag", "etag"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("link.id"), nullable=False)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    referrer: Mapped[Optional[str]] = mapped_column(String(500))
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    os_family: Mapped[Optional[str]] = mapped_column(String(64))
    device_type: Mapped[Optional[str]] = mapped_column(String(64))

    isp: Mapped[Optional[str]] = mapped_column(String(128))
    org: Mapped[Optional[str]] = mapped_column(String(128))
    hostname: Mapped[Optional[str]] = mapped_column(String(256))
    city: Mapped[Optional[str]] = mapped_column(String(64))
    country: Mapped[Optional[str]] = mapped_column(String(64))
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lon: Mapped[Optional[float]] = mapped_column(Float)

    screen_res: Mapped[Optional[str]] = mapped_column(String(32))
    timezone: Mapped[Optional[str]] = mapped_column(String(64))
    browser_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    browser_language: Mapped[Optional[str]] = mapped_column(String(32))
    adblock: Mapped[bool] = mapped_column(Boolean, default=False)

    ai_summary: Mapped[Optional[str]] = mapped_column(String(512))
    canvas_hash: Mapped[Optional[str]] = mapped_column(String(64))
    webgl_renderer: Mapped[Optional[str]] = mapped_column(String(256))
    email: Mapped[Optional[str]] = mapped_column(String(255))

    battery_level: Mapped[Optional[str]] = mapped_column(String(20))
    cpu_cores: Mapped[Optional[int]] = mapped_column(Integer)
    ram_gb: Mapped[Optional[float]] = mapped_column(Float)
    etag: Mapped[Optional[str]] = mapped_column(String(64))
    fpjs_confidence: Mapped[Optional[float]] = mapped_column(Float)
    detected_sessions: Mapped[Optional[str]] = mapped_column(Text)

    is_vpn: Mapped[bool] = mapped_column(Boolean, default=False)
    is_proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hosting: Mapped[bool] = mapped_column(Boolean, default=False)
    is_mobile: Mapped[bool] = mapped_column(Boolean, default=False)

    link: Mapped["Link"] = relationship(back_populates="visits")


class User(UserMixin, DatabaseModel):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(80), default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    totp_secret: Mapped[Optional[str]] = mapped_column(String(32))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_codes: Mapped[Optional[str]] = mapped_column(Text)
    passkey_credentials: Mapped[Optional[str]] = mapped_column(Text)

    @property
    def passkeys(self) -> List[Dict[str, Any]]:
        return _safe_json_loads(self.passkey_credentials, [])

    @passkeys.setter
    def passkeys(self, value: List[Dict[str, Any]]) -> None:
        self.passkey_credentials = json.dumps(value)

    @property
    def backup_code_hashes(self) -> List[str]:
        return _safe_json_loads(self.backup_codes, [])


class SetupState(DatabaseModel):
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    setup_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    admin_secret_hash: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
