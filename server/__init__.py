import json
from pathlib import Path

from flask import Flask, redirect, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import cache, csrf, db, limiter, login_manager, migrate
from .models import User, Workspace
from .worker import start_worker

DISPOSABLE_DEFAULTS = [
    "tempmail.com",
    "10minutemail.com",
    "guerrillamail.com",
    "mailinator.com",
    "throwaway.email",
    "getnada.com",
    "temp-mail.org",
    "fakeinbox.com",
    "trashmail.com",
    "maildrop.cc",
    "yopmail.com",
    "sharklasers.com",
    "dispostable.com",
    "mailnesia.com",
    "spamgourmet.com",
    "jetable.org",
    "anonymbox.net",
    "tempmailaddress.com",
    "emailondeck.com",
    "mintemail.com",
]

PRIVACY_DEFAULTS = [
    "icloud.com",
    "me.com",
    "protonmail.com",
    "proton.me",
    "tutanota.com",
    "tutamail.com",
]


def _seed_default_domain_lists(data_dir: Path) -> None:
    for filename, defaults in [
        ("disposable_domains.txt", DISPOSABLE_DEFAULTS),
        ("privacy_domains.txt", PRIVACY_DEFAULTS),
    ]:
        path = data_dir / filename
        if not path.exists() or path.stat().st_size == 0:
            path.write_text("\n".join(defaults), encoding="utf-8")


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(Config.as_flask_config())
    (Path(app.root_path) / "data").mkdir(parents=True, exist_ok=True)
    _seed_default_domain_lists(Path(app.root_path) / "data")

    if Config.TRUST_PROXY_HEADERS:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    cache.init_app(
        app,
        config={
            "CACHE_TYPE": "SimpleCache",
            "CACHE_DEFAULT_TIMEOUT": Config.CACHE_DEFAULT_TIMEOUT,
        },
    )
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    limiter.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.template_filter("markdown")
    def render_markdown(text):
        if not text:
            return ""
        try:
            import markdown

            return markdown.markdown(text)
        except ImportError:
            return text.replace("\n", "<br>")

    @app.template_filter("fromjson")
    def fromjson(value, default=None):
        if not value:
            return default or {}
        try:
            parsed = json.loads(value)
        except Exception:
            return default or {}
        return parsed if parsed is not None else default or {}

    @app.before_request
    def enforce_first_run_setup():
        if request.endpoint is None:
            return None
        if request.endpoint.startswith("static"):
            return None
        if request.blueprint in {"public", "api"}:
            return None
        auth_allowed = {
            "auth.login",
            "auth.logout",
            "auth.register",
            "auth.onboarding",
            "auth.accept_invite",
        }
        if request.endpoint in auth_allowed:
            return None

        if Workspace.query.count() == 0:
            return redirect(url_for("auth.register"))
        return None

    @app.context_processor
    def inject_workspace():
        from .auth_middleware import (
            current_user_email,
            get_current_membership,
            get_current_user,
            get_current_workspace,
        )
        user = get_current_user()
        workspace = None
        role = None
        all_workspaces = []
        if user:
            workspace = get_current_workspace()
            if workspace:
                member = get_current_membership(workspace.id)
                role = member.role if member else None
            from .models import WorkspaceMember

            all_workspaces = WorkspaceMember.query.filter_by(
                user_email=current_user_email(user),
                status="active",
            ).all()
        return {
            "current_workspace": workspace,
            "current_role": role,
            "all_workspaces": all_workspaces,
            "current_user": user,
            "current_user_email": current_user_email(user),
        }

    from .routes import api, auth, public
    from .routes.dashboard import bp as dashboard_bp

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(public.bp)

    @app.after_request
    def security_headers(response):
        response.headers.pop("Server", None)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if "Content-Security-Policy" not in response.headers and Config.CSP_STRICT:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
                "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
                "img-src 'self' data: blob: https://flagcdn.com https://*.gravatar.com; "
                "connect-src 'self' https://challenges.cloudflare.com; "
                "frame-src https://challenges.cloudflare.com;"
            )
        return response

    if not Config.SKIP_BACKGROUND_WORKER:
        start_worker(app)
    return app
