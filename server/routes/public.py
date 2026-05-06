import hashlib
import secrets
from datetime import datetime
from pathlib import Path

import pytz
from flask import Blueprint, abort, current_app, make_response, redirect, render_template, request, send_from_directory, url_for
from user_agents import parse

from ..config import Config
from ..extensions import cache, db, limiter, log_queue
from ..models import Link, User, Visit
from ..utils import (
    anonymize_ip,
    generate_slug,
    get_geo_data,
    is_bot_ua,
    is_disposable_email,
    is_malicious_ip,
    is_privacy_email,
    sanitize,
    should_require_consent,
    sign_visit_token,
    validate_email_strict,
    verify_turnstile,
)
from ..validators import get_client_ip, normalize_destination_url


bp = Blueprint("public", __name__)

_VPN_KEYWORDS = (
    "vpn",
    "mullvad",
    "nordvpn",
    "expressvpn",
    "surfshark",
    "protonvpn",
    "cyberghost",
    "ipvanish",
    "windscribe",
    "tunnelbear",
    "hide.me",
    "purevpn",
    "torguard",
    "ivpn",
    "private internet access",
    "pia vpn",
)
_CLOUD_KEYWORDS = (
    "amazon",
    "google",
    "microsoft",
    "digitalocean",
    "cloudflare",
    "linode",
    "vultr",
    "hetzner",
    "ovh",
    "leaseweb",
    "m247",
    "datacamp",
    "choopa",
    "tzulo",
    "packethub",
)


@bp.route("/", methods=["GET"])
def index():
    if Config.ADMIN_BOOTSTRAP_ENABLED and User.query.count() == 0:
        return redirect(url_for("auth.setup"))
    return redirect(url_for("auth.login"))


@bp.route("/favicon.ico", methods=["GET"])
def favicon():
    favicon_path = Path(current_app.static_folder or "") / "favicon.ico"
    if favicon_path.exists():
        return send_from_directory(current_app.static_folder, "favicon.ico")
    return ("", 204)


def _safe_url_or_none(url: str):
    if not url:
        url = "https://www.google.com"
    try:
        return normalize_destination_url(url)
    except ValueError:
        return None


def _visit_from_form(value):
    try:
        visit_id = int(value)
    except (TypeError, ValueError):
        return None
    return db.session.get(Visit, visit_id)


def _build_public_csp(nonce: str) -> str:
    return (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://challenges.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https://flagcdn.com https://*.gravatar.com; "
        "connect-src 'self' https://challenges.cloudflare.com; "
        "frame-src https://challenges.cloudflare.com;"
    )


def _public_response(template_name: str, status: int = 200, **kwargs):
    if Config.CSP_STRICT:
        nonce = secrets.token_urlsafe(16)
        kwargs["csp_nonce"] = nonce
        response = make_response(render_template(template_name, **kwargs))
        response.headers["Content-Security-Policy"] = _build_public_csp(nonce)
    else:
        response = make_response(render_template(template_name, **kwargs))
    response.status_code = status
    return response


def _detect_vpn_or_cloud(geo: dict) -> bool:
    if geo.get("proxy") or geo.get("hosting"):
        return True
    combined = f"{geo.get('org') or ''} {geo.get('isp') or ''}".lower()
    if any(keyword in combined for keyword in _VPN_KEYWORDS):
        return True
    if any(keyword in combined for keyword in _CLOUD_KEYWORDS):
        return True
    return False


def _cached_link(slug: str):
    cache_key = f"link:{slug}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if slug.lower() in Config.RESERVED_SLUGS:
        abort(404)

    link = Link.query.filter_by(slug=slug).first_or_404()
    payload = link.to_dict()
    cache.set(cache_key, payload, timeout=Config.CACHE_DEFAULT_TIMEOUT)
    return payload


def _is_captcha_enabled(link_data: dict) -> bool:
    return bool(
        link_data.get("enable_captcha")
        and Config.TURNSTILE_SITE_KEY
        and Config.TURNSTILE_SECRET_KEY
    )


def _pick_destination(link_data: dict, user_agent) -> str:
    destination = normalize_destination_url(link_data["destination"])
    if (user_agent.is_mobile or user_agent.is_tablet) and user_agent.os.family == "iOS" and link_data.get("ios_url"):
        return normalize_destination_url(link_data["ios_url"])
    if (
        user_agent.is_mobile or user_agent.is_tablet
    ) and user_agent.os.family == "Android" and link_data.get("android_url"):
        return normalize_destination_url(link_data["android_url"])
    return destination


def _validate_schedule(link_data: dict):
    if link_data.get("schedule_start_hour") is None and link_data.get("schedule_end_hour") is None:
        return None
    tz_name = link_data.get("schedule_timezone") or "UTC"
    try:
        target_tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        target_tz = pytz.UTC

    current_hour = datetime.now(target_tz).hour
    start_hour = link_data.get("schedule_start_hour")
    end_hour = link_data.get("schedule_end_hour")
    if start_hour is not None and current_hour < start_hour:
        return "Link not yet active"
    if end_hour is not None and current_hour >= end_hour:
        return "Link expired (schedule)"
    return None


def _validate_email_policy(link_data: dict, email: str):
    policy = (link_data.get("email_policy") or "all").lower()
    valid, reason = validate_email_strict(email)
    if not valid:
        return reason

    if policy in {"certified", "trackable"} and is_disposable_email(email):
        return "Temporary email providers are not accepted."
    if policy == "trackable" and is_privacy_email(email):
        return "Private or anonymous email providers are restricted."
    return None


@bp.route("/<slug>", methods=["GET"])
@limiter.limit(Config.RATE_LIMIT_REDIRECT)
def redirect_to_url(slug):
    link_data = _cached_link(slug)

    if should_require_consent(request):
        return _public_response("consent.html", next_url=f"/{slug}", hide_nav=True)

    raw_ip = get_client_ip(request, Config.TRUST_PROXY_HEADERS)
    client_ip = anonymize_ip(raw_ip) if Config.ANONYMIZE_IP else raw_ip
    ua_string = request.user_agent.string
    user_agent = parse(ua_string)
    geo = get_geo_data(raw_ip)

    client_etag = request.headers.get("If-None-Match") or generate_slug(16)

    visit = Visit(
        link_id=link_data["id"],
        ip_address=client_ip,
        user_agent=ua_string,
        referrer=request.referrer,
        os_family=user_agent.os.family,
        device_type="Mobile" if user_agent.is_mobile else "Tablet" if user_agent.is_tablet else "Desktop",
        isp=geo.get("isp"),
        org=geo.get("org"),
        country=geo.get("country"),
        city=geo.get("city"),
        country_code=geo.get("countryCode"),
        lat=geo.get("lat"),
        lon=geo.get("lon"),
        etag=client_etag,
    )
    try:
        db.session.add(visit)
        db.session.commit()
    except Exception as exc:
        print(f"Visit log error: {exc}")
        db.session.rollback()
        visit.id = None

    if visit.id:
        try:
            log_queue.put({"type": "enrich_visit", "visit_id": visit.id, "ip": raw_ip, "notify": False})
        except Exception:
            pass

    visit_token = sign_visit_token(visit.id) if visit.id else None

    schedule_error = _validate_schedule(link_data)
    if schedule_error:
        return _public_response("error.html", status=404, message=schedule_error, hide_nav=True)

    allowed_countries = [
        c.strip().upper() for c in
        (link_data.get("allowed_countries") or "").split(",")
        if c.strip() and len(c.strip()) == 2
    ]
    visitor_country = (geo.get("countryCode") or "").upper()
    if allowed_countries:
        if not visitor_country:
            if visit.id:
                visit.is_suspicious = True
                visit.notes = "Blocked: geo lookup failed"
                db.session.commit()
            return _public_response(
                "error.html",
                status=403,
                message="Unable to verify your location.",
                hide_nav=True,
            )
        if visitor_country not in allowed_countries:
            if visit.id:
                visit.is_suspicious = True
                visit.notes = f"Blocked country: {visitor_country}"
                db.session.commit()
            return _public_response(
                "error.html",
                status=403,
                message="Access denied from your location.",
                hide_nav=True,
            )

    try:
        final_destination = _pick_destination(link_data, user_agent)
    except ValueError:
        return _public_response("error.html", status=400, message="Invalid destination URL.", hide_nav=True)

    expire_date = link_data.get("expire_date")
    if expire_date and datetime.utcnow() > expire_date:
        return _public_response("error.html", status=404, message="Link expired.", hide_nav=True)

    expiration_minutes = link_data.get("expiration_minutes") or 0
    created_at = link_data.get("created_at")
    if expiration_minutes and created_at:
        elapsed = (datetime.utcnow() - created_at).total_seconds() / 60
        if elapsed > expiration_minutes:
            return _public_response("error.html", status=404, message="Link expired.", hide_nav=True)

    max_clicks = link_data.get("max_clicks") or 0
    if max_clicks and Visit.query.filter_by(link_id=link_data["id"]).count() > max_clicks:
        return _public_response("error.html", status=404, message="Link limit reached.", hide_nav=True)

    is_vpn_or_cloud = _detect_vpn_or_cloud(geo)
    is_bot = is_bot_ua(ua_string)
    safe_destination = _safe_url_or_none(link_data.get("safe_url"))

    if is_malicious_ip(raw_ip):
        if visit.id:
            visit.is_suspicious = True
            visit.notes = "Blocked malicious IP"
            db.session.commit()
        if safe_destination:
            final_destination = safe_destination
        else:
            return _public_response("error.html", status=403, message="Access denied.", hide_nav=True)

    if link_data.get("block_vpn") and is_vpn_or_cloud:
        if visit.id:
            visit.is_suspicious = True
            visit.is_vpn = True
            visit.is_proxy = bool(geo.get("proxy"))
            visit.is_hosting = bool(geo.get("hosting"))
            visit.notes = "Blocked VPN or hosting provider"
            db.session.commit()
        if safe_destination:
            final_destination = safe_destination
        else:
            return _public_response("error.html", status=403, message="VPN or proxy traffic blocked.", hide_nav=True)

    if link_data.get("block_bots") and is_bot:
        if visit.id:
            visit.is_suspicious = True
            visit.notes = visit.notes or "Blocked bot"
            db.session.commit()
        if safe_destination:
            final_destination = safe_destination
        else:
            return _public_response("error.html", status=403, message="Suspicious traffic blocked.", hide_nav=True)

    if _is_captcha_enabled(link_data):
        cookie_name = f"auth_captcha_{link_data['slug']}"
        expected = hashlib.sha256(f"captcha_ok_{link_data['slug']}{Config.SECRET_KEY}".encode()).hexdigest()
        if request.cookies.get(cookie_name) != expected:
            return _public_response(
                "captcha.html",
                slug=link_data["slug"],
                visit_id=visit.id,
                visit_token=visit_token,
                site_key=Config.TURNSTILE_SITE_KEY,
                hide_nav=True,
            )

    if link_data.get("password_hash"):
        cookie_name = f"auth_pwd_{link_data['slug']}"
        expected = hashlib.sha256(f"{link_data['password_hash']}{Config.SECRET_KEY}".encode()).hexdigest()
        if request.cookies.get(cookie_name) != expected:
            return _public_response(
                "password.html",
                slug=link_data["slug"],
                visit_id=visit.id,
                visit_token=visit_token,
                hide_nav=True,
            )

    if link_data.get("require_email"):
        cookie_name = f"verified_{link_data['slug']}"
        if request.cookies.get(cookie_name) != "1":
            return _public_response(
                "email_gate.html",
                slug=link_data["slug"],
                visit_id=visit.id,
                visit_token=visit_token,
                allow_partial_email_capture=Config.ALLOW_PARTIAL_EMAIL_CAPTURE,
                hide_nav=True,
            )

    response = _public_response(
        "loading.html",
        destination=final_destination,
        visit_id=visit.id,
        visit_token=visit_token,
        allow_no_js=bool(link_data.get("allow_no_js")),
        block_adblock=bool(link_data.get("block_adblock")),
        hide_nav=True,
    )
    response.headers["ETag"] = client_etag
    response.headers["Cache-Control"] = "private, max-age=31536000"
    if visit.id:
        try:
            log_queue.put(
                {
                    "type": "dispatch_visit_after_timeout",
                    "visit_id": visit.id,
                    "wait_seconds": Config.BEACON_WAIT_SECONDS,
                }
            )
        except Exception:
            pass
    return response


@bp.route("/verify_captcha", methods=["POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def verify_captcha():
    slug = sanitize(request.form.get("slug"), 20)
    turnstile_token = request.form.get("cf-turnstile-response")
    visit_id = request.form.get("visit_id")
    canvas_hash = sanitize(request.form.get("canvas_hash"), 64)
    link = Link.query.filter_by(slug=slug).first_or_404()

    if not _is_captcha_enabled(link.to_dict()):
        return redirect(f"/{slug}")

    client_ip = get_client_ip(request, Config.TRUST_PROXY_HEADERS)
    if verify_turnstile(turnstile_token, client_ip):
        visit = _visit_from_form(visit_id)
        if visit is not None:
            if canvas_hash and not visit.canvas_hash:
                visit.canvas_hash = canvas_hash
            db.session.commit()
            try:
                log_queue.put({"type": "mark_visit_complete", "visit_id": visit.id})
            except Exception:
                pass
        auth_hash = hashlib.sha256(f"captcha_ok_{slug}{Config.SECRET_KEY}".encode()).hexdigest()
        response = make_response(redirect(f"/{slug}"))
        response.set_cookie(
            f"auth_captcha_{slug}",
            auth_hash,
            max_age=3600,
            httponly=True,
            secure=Config.SESSION_COOKIE_SECURE,
            samesite="Lax",
        )
        return response

    return _public_response(
        "captcha.html",
        status=400,
        slug=slug,
        visit_id=visit_id,
        visit_token=sign_visit_token(visit_id),
        site_key=Config.TURNSTILE_SITE_KEY,
        error="Verification failed.",
        hide_nav=True,
    )


@bp.route("/verify_password", methods=["POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def verify_password():
    slug = sanitize(request.form.get("slug"), 20)
    password = request.form.get("password", "")
    visit_id = request.form.get("visit_id")

    link = Link.query.filter_by(slug=slug).first_or_404()
    user_hash = hashlib.sha256(password.encode()).hexdigest()
    if user_hash == link.password_hash:
        visit = _visit_from_form(visit_id)
        if visit is not None:
            db.session.commit()
            try:
                log_queue.put({"type": "mark_visit_complete", "visit_id": visit.id})
            except Exception:
                pass
        auth_hash = hashlib.sha256(f"{link.password_hash}{Config.SECRET_KEY}".encode()).hexdigest()
        response = make_response(redirect(f"/{slug}"))
        response.set_cookie(
            f"auth_pwd_{slug}",
            auth_hash,
            max_age=3600,
            httponly=True,
            secure=Config.SESSION_COOKIE_SECURE,
            samesite="Lax",
        )
        return response

    return _public_response(
        "password.html",
        status=401,
        slug=slug,
        visit_id=visit_id,
        visit_token=sign_visit_token(visit_id),
        error="Invalid password.",
        hide_nav=True,
    )


@bp.route("/verify_email", methods=["POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def verify_email():
    slug = sanitize(request.form.get("slug"), 20)
    visit_id = request.form.get("visit_id")
    email = sanitize(request.form.get("email"), 255).lower()

    if not slug or not email:
        return "Missing data", 400

    link = Link.query.filter_by(slug=slug).first_or_404()
    policy_error = _validate_email_policy(link.to_dict(), email)
    if policy_error:
        return _public_response(
            "email_gate.html",
            status=400,
            slug=slug,
            visit_id=visit_id,
            visit_token=sign_visit_token(visit_id),
            allow_partial_email_capture=Config.ALLOW_PARTIAL_EMAIL_CAPTURE,
            error=policy_error,
            hide_nav=True,
        )

    visit = _visit_from_form(visit_id)
    if visit is not None:
        visit.email = email
        db.session.commit()
        if visit.canvas_hash:
            Visit.query.filter(
                Visit.canvas_hash == visit.canvas_hash,
                Visit.email.is_(None),
                Visit.id != visit.id,
            ).update({"email": email}, synchronize_session=False)
            db.session.commit()
        try:
            log_queue.put({"type": "mark_visit_complete", "visit_id": visit.id})
        except Exception:
            pass

    response = make_response(redirect(f"/{slug}"))
    response.set_cookie(
        f"verified_{slug}",
        "1",
        max_age=3600,
        httponly=True,
        secure=Config.SESSION_COOKIE_SECURE,
        samesite="Lax",
    )
    return response


@bp.route("/consent", methods=["POST"])
def record_consent():
    next_url = request.form.get("next", "/")
    if not next_url.startswith("/"):
        next_url = "/"
    response = make_response(redirect(next_url))
    response.set_cookie(
        Config.CONSENT_COOKIE_NAME,
        "1",
        max_age=Config.CONSENT_TTL_DAYS * 86400,
        httponly=True,
        secure=Config.SESSION_COOKIE_SECURE,
        samesite="Lax",
    )
    return response
