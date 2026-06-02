import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    followup_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

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
        Index("ix_visit_fingerprint_composite_v1", "fingerprint_composite_v1"),
        Index("ix_visit_thumbmark_hash", "thumbmark_hash"),
        Index("ix_visit_thumbmark_visitor_id", "thumbmark_visitor_id"),
        Index("ix_visit_visitor_id", "visitor_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("link.id"), nullable=False)
    visitor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("visitor.id", ondelete="SET NULL"))
    probable_visitor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("visitor.id", ondelete="SET NULL"))

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
    screen_depth: Mapped[Optional[int]] = mapped_column(Integer)
    pixel_ratio: Mapped[Optional[float]] = mapped_column(Float)
    timezone: Mapped[Optional[str]] = mapped_column(String(64))
    platform: Mapped[Optional[str]] = mapped_column(String(64))
    touch_points: Mapped[Optional[int]] = mapped_column(Integer)
    dark_mode: Mapped[Optional[bool]] = mapped_column(Boolean)
    reduced_motion: Mapped[Optional[bool]] = mapped_column(Boolean)
    connection_type: Mapped[Optional[str]] = mapped_column(String(32))
    browser_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    browser_language: Mapped[Optional[str]] = mapped_column(String(32))
    do_not_track: Mapped[Optional[str]] = mapped_column(String(8))
    adblock: Mapped[bool] = mapped_column(Boolean, default=False)

    ai_summary: Mapped[Optional[str]] = mapped_column(String(512))
    canvas_hash: Mapped[Optional[str]] = mapped_column(String(64))
    audio_fp: Mapped[Optional[str]] = mapped_column(String(128))
    fonts: Mapped[Optional[str]] = mapped_column(Text)
    webgl_renderer: Mapped[Optional[str]] = mapped_column(String(256))
    webgl_vendor: Mapped[Optional[str]] = mapped_column(String(256))
    webgl_extensions_hash: Mapped[Optional[str]] = mapped_column(String(16))
    webgl_max_texture: Mapped[Optional[int]] = mapped_column(Integer)
    client_rects_fp: Mapped[Optional[str]] = mapped_column(String(16))
    webrtc_ips: Mapped[Optional[str]] = mapped_column(String(512))
    extensions_detected: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    dwell_ms: Mapped[Optional[int]] = mapped_column(Integer)

    battery_level: Mapped[Optional[str]] = mapped_column(String(20))
    cpu_cores: Mapped[Optional[int]] = mapped_column(Integer)
    ram_gb: Mapped[Optional[float]] = mapped_column(Float)
    taskbar_size: Mapped[Optional[int]] = mapped_column(Integer)
    ua_brands: Mapped[Optional[str]] = mapped_column(String(256))
    etag: Mapped[Optional[str]] = mapped_column(String(64))
    fpjs_confidence: Mapped[Optional[float]] = mapped_column(Float)
    fingerprint_version: Mapped[Optional[int]] = mapped_column(Integer)
    fingerprint_composite_v1: Mapped[Optional[str]] = mapped_column(String(64))
    identity_confidence: Mapped[Optional[int]] = mapped_column(Integer)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer)
    match_reasons_json: Mapped[Optional[str]] = mapped_column(Text)
    cluster_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_reason: Mapped[Optional[str]] = mapped_column(Text)
    beacon_received_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    review_label: Mapped[Optional[str]] = mapped_column(String(32))
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    detected_sessions: Mapped[Optional[str]] = mapped_column(Text)
    visit_complete: Mapped[bool] = mapped_column(Boolean, default=False)

    thumbmark_hash: Mapped[Optional[str]] = mapped_column(Text)
    thumbmark_raw: Mapped[Optional[str]] = mapped_column(Text)
    thumbmark_visitor_id: Mapped[Optional[str]] = mapped_column(Text)
    thumbmark_api_confidence: Mapped[Optional[float]] = mapped_column(Float)
    thumbmark_api_called: Mapped[bool] = mapped_column(Boolean, default=False)
    thumbmark_api_error: Mapped[Optional[str]] = mapped_column(Text)
    fp_audio_hash: Mapped[Optional[str]] = mapped_column(Text)
    fp_canvas_hash: Mapped[Optional[str]] = mapped_column(Text)
    fp_webgl_vendor: Mapped[Optional[str]] = mapped_column(Text)
    fp_webgl_hash: Mapped[Optional[str]] = mapped_column(Text)
    fp_fonts_hash: Mapped[Optional[str]] = mapped_column(Text)
    fp_screen_profile: Mapped[Optional[str]] = mapped_column(Text)
    fp_hardware_profile: Mapped[Optional[str]] = mapped_column(Text)
    fp_languages: Mapped[Optional[str]] = mapped_column(Text)
    fp_timezone: Mapped[Optional[str]] = mapped_column(Text)
    fp_speech_hash: Mapped[Optional[str]] = mapped_column(Text)
    fp_math_hash: Mapped[Optional[str]] = mapped_column(Text)
    fp_permissions_profile: Mapped[Optional[str]] = mapped_column(Text)
    fp_media_devices: Mapped[Optional[str]] = mapped_column(Text)
    fp_webrtc_ips: Mapped[Optional[str]] = mapped_column(Text)

    is_vpn: Mapped[bool] = mapped_column(Boolean, default=False)
    is_proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hosting: Mapped[bool] = mapped_column(Boolean, default=False)
    is_mobile: Mapped[bool] = mapped_column(Boolean, default=False)

    link: Mapped["Link"] = relationship(back_populates="visits")
    visitor: Mapped[Optional["Visitor"]] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
        back_populates="visits",
    )
    probable_visitor: Mapped[Optional["Visitor"]] = relationship(
        "Visitor",
        foreign_keys=[probable_visitor_id],
    )


class Visitor(DatabaseModel):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    probable_match_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("visitor.id", ondelete="SET NULL"))

    primary_thumbmark_hash: Mapped[Optional[str]] = mapped_column(Text)
    primary_thumbmark_visitor_id: Mapped[Optional[str]] = mapped_column(Text)
    known_canvas_hashes: Mapped[Optional[str]] = mapped_column(Text)
    known_audio_hashes: Mapped[Optional[str]] = mapped_column(Text)
    known_webgl_vendors: Mapped[Optional[str]] = mapped_column(Text)
    known_screen_profiles: Mapped[Optional[str]] = mapped_column(Text)
    known_timezones: Mapped[Optional[str]] = mapped_column(Text)
    known_languages: Mapped[Optional[str]] = mapped_column(Text)
    known_thumbmark_visitor_ids: Mapped[Optional[str]] = mapped_column(Text)
    thumbmark_api_calls_count: Mapped[int] = mapped_column(Integer, default=0)
    thumbmark_api_confidence_avg: Mapped[Optional[float]] = mapped_column(Float)

    visits: Mapped[List["Visit"]] = relationship(
        "Visit",
        foreign_keys=[Visit.visitor_id],
        back_populates="visitor",
    )
    signals: Mapped[List["VisitorSignal"]] = relationship(
        "VisitorSignal",
        back_populates="visitor",
        cascade="all, delete-orphan",
    )


class VisitorSignal(DatabaseModel):
    __table_args__ = (
        UniqueConstraint("visitor_id", "signal_type", "signal_value", name="uq_visitor_signal_value"),
        Index("idx_visitor_signal_visitor", "visitor_id"),
        Index("idx_visitor_signal_type_value", "signal_type", "signal_value"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    visitor_id: Mapped[str] = mapped_column(String(36), ForeignKey("visitor.id", ondelete="CASCADE"), nullable=False)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id", ondelete="SET NULL"))
    signal_type: Mapped[str] = mapped_column(Text, nullable=False)
    signal_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    visitor: Mapped["Visitor"] = relationship("Visitor", back_populates="signals")


class Lead(DatabaseModel):
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    primary_canvas_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    primary_ip: Mapped[Optional[str]] = mapped_column(String(45))
    all_canvas_hashes: Mapped[Optional[str]] = mapped_column(Text)
    all_ips: Mapped[Optional[str]] = mapped_column(Text)
    all_slugs_visited: Mapped[Optional[str]] = mapped_column(Text)
    country: Mapped[Optional[str]] = mapped_column(String(64))
    city: Mapped[Optional[str]] = mapped_column(String(64))
    org: Mapped[Optional[str]] = mapped_column(String(128))
    device_type: Mapped[Optional[str]] = mapped_column(String(64))
    os_family: Mapped[Optional[str]] = mapped_column(String(64))
    is_vpn: Mapped[bool] = mapped_column(Boolean, default=False)
    total_visits: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    label: Mapped[Optional[str]] = mapped_column(String(128))


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
