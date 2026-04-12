import io
from pathlib import Path

import segno
from dotenv import set_key
from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import distinct, func

from ...config import BASE_DIR, Config
from ...extensions import cache, db
from ...models import Link, Visit
from ...utils import sanitize, shorten_with_isgd
from ...validators import normalize_destination_url, normalize_optional_url, parse_bool, validate_slug


bp = Blueprint("dashboard_links", __name__)


def _mask_url_for_link(slug: str) -> str | None:
    if not Config.MASK_WITH_ISGD:
        return None
    full_url = f"{Config.SERVER_URL.rstrip('/')}/{slug}"
    return shorten_with_isgd(full_url)


def _invalidate_link_cache(slug: str) -> None:
    cache.delete(f"link:{slug}")


def _set_runtime_value(key: str, value):
    current_app.config[key] = value
    setattr(Config, key, value)


def _link_form_values(form):
    return {
        "destination": normalize_destination_url(sanitize(form.get("destination"), 2048)),
        "ios_url": normalize_optional_url(sanitize(form.get("ios_url"), 2048)),
        "android_url": normalize_optional_url(sanitize(form.get("android_url"), 2048)),
        "safe_url": normalize_optional_url(sanitize(form.get("safe_url"), 2048)),
        "block_bots": parse_bool(form.get("block_bots")) or "block_bots" in form,
        "block_vpn": parse_bool(form.get("block_vpn")) or "block_vpn" in form,
        "block_adblock": parse_bool(form.get("block_adblock")) or "block_adblock" in form,
        "allow_no_js": parse_bool(form.get("allow_no_js")) or "allow_no_js" in form,
        "enable_captcha": parse_bool(form.get("enable_captcha")) or "enable_captcha" in form,
        "require_email": parse_bool(form.get("require_email")) or "require_email" in form,
        "email_policy": sanitize(form.get("email_policy"), 20) or "all",
        "allowed_countries": sanitize(form.get("allowed_countries"), 50).upper() or None,
        "schedule_timezone": sanitize(form.get("schedule_timezone"), 64) or "UTC",
        "schedule_start_hour": int(form.get("schedule_start_hour")) if sanitize(form.get("schedule_start_hour"), 2) else None,
        "schedule_end_hour": int(form.get("schedule_end_hour")) if sanitize(form.get("schedule_end_hour"), 2) else None,
        "max_clicks": int(sanitize(form.get("max_clicks"), 10) or 0),
        "expiration_minutes": int(sanitize(form.get("expiration_minutes"), 10) or 0),
    }


@bp.route("/")
@bp.route("")
@login_required
def dashboard_home():
    links = Link.query.order_by(Link.created_at.desc()).all()
    visits = Visit.query.order_by(Visit.timestamp.desc()).limit(25).all()
    identified_visitors = (
        db.session.query(func.count(distinct(Visit.email)))
        .filter(Visit.email.isnot(None))
        .scalar()
        or 0
    )
    return render_template(
        "dashboard.html",
        links=links,
        visits=visits,
        identified_visitors=identified_visitors,
        total_visits=Visit.query.count(),
    )


@bp.route("/links")
@login_required
def links():
    return render_template("links.html", links=Link.query.order_by(Link.created_at.desc()).all())


@bp.route("/create", methods=["POST"])
@login_required
def create_link():
    slug = sanitize(request.form.get("slug"), 20)
    destination = sanitize(request.form.get("destination"), 2048)

    if not destination:
        flash("Destination is required.", "error")
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    if not slug:
        from ...utils import generate_slug

        for _ in range(10):
            candidate = generate_slug()
            if validate_slug(candidate, Config.RESERVED_SLUGS) is None and not Link.query.filter_by(slug=candidate).first():
                slug = candidate
                break
    error = validate_slug(slug, Config.RESERVED_SLUGS)
    if error:
        flash(error, "error")
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))
    if Link.query.filter_by(slug=slug).first():
        flash("Slug already exists.", "error")
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    try:
        link = Link(
            slug=slug,
            destination=normalize_destination_url(destination),
            enable_captcha=parse_bool(request.form.get("enable_captcha")),
            require_email=parse_bool(request.form.get("require_email")),
            email_policy=sanitize(request.form.get("email_policy"), 20) or "all",
            block_bots=True,
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    link.public_masked_url = _mask_url_for_link(slug)
    db.session.add(link)
    db.session.commit()
    flash(f"Link created: /{slug}", "success")
    return redirect(url_for("dashboard.dashboard_links.dashboard_home"))


@bp.route("/create_full", methods=["GET", "POST"])
@login_required
def create_full():
    if request.method == "POST":
        slug = sanitize(request.form.get("slug"), 20)
        if not slug:
            from ...utils import generate_slug

            for _ in range(10):
                candidate = generate_slug()
                if validate_slug(candidate, Config.RESERVED_SLUGS) is None and not Link.query.filter_by(slug=candidate).first():
                    slug = candidate
                    break
        error = validate_slug(slug, Config.RESERVED_SLUGS)
        if error:
            flash(error, "error")
            return redirect(url_for("dashboard.dashboard_links.create_full"))
        if Link.query.filter_by(slug=slug).first():
            flash("Slug already exists.", "error")
            return redirect(url_for("dashboard.dashboard_links.create_full"))

        try:
            values = _link_form_values(request.form)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("dashboard.dashboard_links.create_full"))

        link = Link(slug=slug, **values)
        password = request.form.get("password", "")
        if sanitize(password, 255):
            import hashlib

            link.password_hash = hashlib.sha256(password.encode()).hexdigest()
        link.public_masked_url = _mask_url_for_link(slug)
        db.session.add(link)
        db.session.commit()
        flash(f"Link created: /{slug}", "success")
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    return render_template("create_full.html", mask_with_isgd=Config.MASK_WITH_ISGD)


@bp.route("/delete/<int:link_id>", methods=["POST"])
@login_required
def delete_link(link_id: int):
    link = db.session.get(Link, link_id)
    if link is not None:
        slug = link.slug
        db.session.delete(link)
        db.session.commit()
        _invalidate_link_cache(slug)
        flash("Link deleted.", "success")
    return redirect(url_for("dashboard.dashboard_links.dashboard_home"))


@bp.route("/edit/<slug>", methods=["GET", "POST"])
@login_required
def edit_link(slug: str):
    link = Link.query.filter_by(slug=slug).first_or_404()

    if request.method == "POST":
        try:
            values = _link_form_values(request.form)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("dashboard.dashboard_links.edit_link", slug=slug))

        for key, value in values.items():
            setattr(link, key, value)

        password = request.form.get("password", "")
        if sanitize(password, 255):
            import hashlib

            link.password_hash = hashlib.sha256(password.encode()).hexdigest()
        elif "remove_password" in request.form:
            link.password_hash = None

        link.public_masked_url = _mask_url_for_link(link.slug)
        db.session.commit()
        _invalidate_link_cache(link.slug)
        flash("Link updated.", "success")
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    return render_template("edit.html", link=link, mask_with_isgd=Config.MASK_WITH_ISGD)


@bp.route("/qr/<slug>")
@login_required
def qr_code(slug: str):
    full_url = f"{Config.SERVER_URL.rstrip('/')}/{slug}"
    qr = segno.make(full_url)
    buffer = io.BytesIO()
    qr.save(buffer, kind="png", scale=10)
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "image/png"
    response.headers["Content-Disposition"] = f"inline; filename={slug}_qr.png"
    return response


@bp.route("/qr_view/<slug>")
@login_required
def qr_view(slug: str):
    return render_template("qr_view.html", link=Link.query.filter_by(slug=slug).first_or_404())


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    data_dir = Path(current_app.root_path) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    disposable_path = data_dir / "disposable_domains.txt"
    privacy_path = data_dir / "privacy_domains.txt"
    disposable_path.touch(exist_ok=True)
    privacy_path.touch(exist_ok=True)
    dotenv_path = BASE_DIR / ".env"
    dotenv_path.touch(exist_ok=True)

    if request.method == "POST":
        settings_scope = sanitize(request.form.get("settings_scope"), 20) or "domains"
        if settings_scope == "runtime":
            server_url = sanitize(request.form.get("server_url"), 2048)
            gemini_api_key = sanitize(request.form.get("gemini_api_key"), 512)
            gemini_model = sanitize(request.form.get("gemini_model"), 255)
            telegram_bot_token = sanitize(request.form.get("telegram_bot_token"), 512)
            telegram_chat_id = sanitize(request.form.get("telegram_chat_id"), 255)
            mask_with_isgd = "mask_with_isgd" in request.form
            trust_proxy_headers = "trust_proxy_headers" in request.form
            visit_retention_days = int(sanitize(request.form.get("visit_retention_days"), 10) or Config.VISIT_RETENTION_DAYS)

            restart_required = False
            if server_url:
                set_key(dotenv_path, "SERVER_URL", server_url)
                restart_required = True

            if gemini_api_key:
                set_key(dotenv_path, "GEMINI_API_KEY", gemini_api_key)
                _set_runtime_value("GEMINI_API_KEY", gemini_api_key)
            if gemini_model:
                set_key(dotenv_path, "GEMINI_MODEL", gemini_model)
                _set_runtime_value("GEMINI_MODEL", gemini_model)

            if telegram_bot_token:
                set_key(dotenv_path, "TELEGRAM_BOT_TOKEN", telegram_bot_token)
                _set_runtime_value("TELEGRAM_BOT_TOKEN", telegram_bot_token)
            if telegram_chat_id:
                set_key(dotenv_path, "TELEGRAM_CHAT_ID", telegram_chat_id)
                _set_runtime_value("TELEGRAM_CHAT_ID", telegram_chat_id)

            set_key(dotenv_path, "MASK_WITH_ISGD", "true" if mask_with_isgd else "false")
            set_key(dotenv_path, "TRUST_PROXY_HEADERS", "true" if trust_proxy_headers else "false")
            set_key(dotenv_path, "VISIT_RETENTION_DAYS", str(visit_retention_days))

            _set_runtime_value("MASK_WITH_ISGD", mask_with_isgd)
            _set_runtime_value("TRUST_PROXY_HEADERS", trust_proxy_headers)
            _set_runtime_value("VISIT_RETENTION_DAYS", visit_retention_days)

            flash("Runtime settings updated.", "success")
            if restart_required:
                flash("SERVER_URL changed. Restart required.", "warning")
        else:
            disposable_domains = request.form.get("disposable_domains", "")
            privacy_domains = request.form.get("privacy_domains", "")
            disposable_lines = [sanitize(line, 255).lower() for line in disposable_domains.splitlines() if sanitize(line, 255)]
            privacy_lines = [sanitize(line, 255).lower() for line in privacy_domains.splitlines() if sanitize(line, 255)]
            disposable_path.write_text("\n".join(disposable_lines), encoding="utf-8")
            privacy_path.write_text("\n".join(privacy_lines), encoding="utf-8")
            flash("Domain lists updated. Restart the app to reload them.", "success")
        return redirect(url_for("dashboard.dashboard_links.settings"))

    return render_template(
        "settings.html",
        server_url=Config.SERVER_URL,
        gemini_model=Config.GEMINI_MODEL,
        telegram_chat_id=Config.TELEGRAM_CHAT_ID,
        mask_with_isgd=Config.MASK_WITH_ISGD,
        trust_proxy_headers=Config.TRUST_PROXY_HEADERS,
        visit_retention_days=Config.VISIT_RETENTION_DAYS,
        disposable_domains=disposable_path.read_text(encoding="utf-8"),
        privacy_domains=privacy_path.read_text(encoding="utf-8"),
    )
