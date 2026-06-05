import base64
import json

import bcrypt
import pyotp
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from webauthn import (
    generate_authentication_options,
    options_to_json,
    verify_authentication_response,
)
from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth_middleware import current_user, ensure_local_user, login_required
from ..config import Config
from ..extensions import db, limiter
from ..models import SetupState, User
from ..supabase_client import get_supabase
from ..utils import generate_secret_code, sanitize, safe_json


bp = Blueprint("auth", __name__)


def _setup_state() -> SetupState:
    state = db.session.get(SetupState, 1)
    if state is None:
        state = SetupState(id=1, setup_completed=False)
        db.session.add(state)
        db.session.commit()
    return state


def _passkey_rp_id() -> str:
    return Config.SERVER_URL.replace("https://", "").replace("http://", "").split(":")[0].split("/")[0]


def _session_user(value):
    try:
        return db.session.get(User, int(value))
    except (TypeError, ValueError):
        return None


def _sync_local_user(email: str, password: str = "") -> User:
    password_hash = generate_password_hash(password) if password else "supabase-auth"
    return ensure_local_user(email=email, password_hash=password_hash)


@bp.route("/setup", methods=["GET", "POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def setup():
    if not Config.ADMIN_BOOTSTRAP_ENABLED:
        return redirect(url_for("auth.login"))
    if User.query.count() > 0:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = sanitize(request.form.get("email"), 255).lower()
        username = sanitize(request.form.get("username"), 80)
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or "@" not in email:
            flash("A valid admin email is required.", "error")
            return render_template("setup.html", hide_nav=True)
        if len(password) < 12:
            flash("Password must be at least 12 characters long.", "error")
            return render_template("setup.html", hide_nav=True)
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("setup.html", hide_nav=True)

        generated_secret = generate_secret_code(Config.SETUP_SECRET_LENGTH)
        state = _setup_state()
        state.setup_completed = True
        state.admin_secret_hash = generate_password_hash(generated_secret)

        admin = User(
            email=email,
            username=username or email.split("@", 1)[0],
            password_hash=generate_password_hash(password),
        )
        db.session.add(admin)
        db.session.commit()

        session["setup_secret_code"] = generated_secret
        try:
            get_supabase().auth.sign_up({"email": email, "password": password})
            flash("Admin created. Check Supabase email confirmation if required, then sign in.", "success")
        except Exception as exc:
            flash(f"Local admin created, but Supabase signup failed: {exc}", "warning")
        return redirect(url_for("auth.login"))

    return render_template("setup.html", hide_nav=True)


@bp.route("/setup/secret")
@login_required
def show_setup_secret():
    secret_code = session.pop("setup_secret_code", None)
    if not secret_code:
        flash("The setup secret is no longer available.", "warning")
        return redirect(url_for("dashboard.dashboard_security.security_settings"))
    return render_template("setup_secret.html", hide_nav=True, secret_code=secret_code)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def login():
    if not Config.SUPABASE_URL and User.query.count() == 0 and Config.ADMIN_BOOTSTRAP_ENABLED:
        return redirect(url_for("auth.setup"))
    if current_user() is not None:
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    if request.method == "POST":
        if "email" in request.form and "password" in request.form:
            email = sanitize(request.form.get("email"), 255).lower()
            password = request.form.get("password", "")
            try:
                result = get_supabase().auth.sign_in_with_password({"email": email, "password": password})
                session["supabase_access_token"] = result.session.access_token
                session["supabase_refresh_token"] = result.session.refresh_token
                _sync_local_user(email, password)
                flash("Login successful.", "success")
                return redirect(url_for("dashboard.dashboard_links.dashboard_home"))
            except Exception as exc:
                flash(str(exc), "error")

        elif "totp_code" in request.form or "backup_code" in request.form:
            user_id = session.get("pending_2fa_user_id")
            if not user_id:
                flash("Session expired. Please login again.", "error")
                return redirect(url_for("auth.login"))

            user = _session_user(user_id)
            if user is None:
                flash("User not found.", "error")
                return redirect(url_for("auth.login"))

            if "totp_code" in request.form:
                code = sanitize(request.form.get("totp_code"), 6)
                totp = pyotp.TOTP(user.totp_secret or "")
                if user.totp_enabled and totp.verify(code, valid_window=1):
                    session.pop("pending_2fa_user_id", None)
                    flash("Use Supabase email/password login for this V3 session.", "warning")
                    return redirect(url_for("auth.login"))
                flash("Invalid verification code.", "error")
                return render_template(
                    "2fa_verify.html",
                    email=user.email,
                    has_passkey=bool(user.passkeys),
                    hide_nav=True,
                )

            backup_code = sanitize(request.form.get("backup_code"), 64).replace("-", "")
            remaining_codes = []
            matched = False
            for stored_code in user.backup_code_hashes:
                if not matched and bcrypt.checkpw(backup_code.encode(), stored_code.encode()):
                    matched = True
                    continue
                remaining_codes.append(stored_code)

            if matched:
                user.backup_codes = json.dumps(remaining_codes)
                db.session.commit()
                session.pop("pending_2fa_user_id", None)
                flash("Use Supabase email/password login for this V3 session.", "warning")
                return redirect(url_for("auth.login"))

            flash("Invalid backup code.", "error")
            return render_template(
                "2fa_verify.html",
                email=user.email,
                has_passkey=bool(user.passkeys),
                hide_nav=True,
            )

    return render_template("login.html", hide_nav=True)


@bp.route("/signup", methods=["GET", "POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def signup():
    if request.method == "POST":
        email = sanitize(request.form.get("email"), 255).lower()
        password = request.form.get("password", "")
        if not email or "@" not in email:
            flash("A valid email is required.", "error")
            return render_template("login.html", hide_nav=True, mode="signup")
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("login.html", hide_nav=True, mode="signup")
        try:
            get_supabase().auth.sign_up({"email": email, "password": password})
            _sync_local_user(email, password)
            flash("Check your email to confirm the registration, then sign in.", "success")
            return redirect(url_for("auth.login"))
        except Exception as exc:
            flash(str(exc), "error")
    return render_template("login.html", hide_nav=True, mode="signup")


@bp.route("/auth/passkey/options", methods=["POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def passkey_auth_options():
    payload = request.get_json(silent=True) or {}
    email = sanitize(payload.get("email"), 255).lower()
    if not email:
        return jsonify({"error": "Email required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.passkeys:
        return jsonify({"error": "No passkeys registered"}), 404

    allow_credentials = []
    for credential in user.passkeys:
        try:
            allow_credentials.append(
                PublicKeyCredentialDescriptor(id=base64.urlsafe_b64decode(credential["id"] + "=="))
            )
        except (KeyError, ValueError):
            continue

    if not allow_credentials:
        return jsonify({"error": "No valid passkeys registered"}), 404

    options = generate_authentication_options(
        rp_id=_passkey_rp_id(),
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    session["webauthn_challenge"] = base64.b64encode(options.challenge).decode()
    session["webauthn_user_id"] = user.id
    return jsonify(json.loads(options_to_json(options)))


@bp.route("/auth/passkey/verify", methods=["POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def passkey_auth_verify():
    payload = request.get_json(silent=True) or {}
    challenge = session.get("webauthn_challenge")
    user_id = session.get("webauthn_user_id")
    if not challenge or not user_id:
        return jsonify({"verified": False, "error": "Session expired"}), 400

    user = _session_user(user_id)
    if user is None:
        return jsonify({"verified": False, "error": "User not found"}), 404

    credentials = safe_json(user.passkey_credentials, []) or []
    credential_id = payload.get("id") or payload.get("rawId")
    matching = next((item for item in credentials if item["id"] == credential_id), None)
    if matching is None:
        return jsonify({"verified": False, "error": "Credential not found"}), 404

    try:
        verification = verify_authentication_response(
            credential=payload,
            expected_challenge=base64.b64decode(challenge),
            expected_rp_id=_passkey_rp_id(),
            expected_origin=Config.SERVER_URL,
            credential_public_key=base64.urlsafe_b64decode(matching["public_key"] + "=="),
            credential_current_sign_count=matching.get("sign_count", 0),
        )
    except Exception as exc:
        return jsonify({"verified": False, "error": str(exc)}), 400

    matching["sign_count"] = verification.new_sign_count
    user.passkey_credentials = json.dumps(credentials)
    db.session.commit()
    session.pop("webauthn_challenge", None)
    session.pop("webauthn_user_id", None)
    session.pop("pending_2fa_user_id", None)
    return jsonify(
        {
            "verified": False,
            "error": "Passkey-only login is disabled in V3. Use Supabase email/password login.",
        }
    ), 400


@bp.route("/logout")
@login_required
def logout():
    session.pop("setup_secret_code", None)
    session.pop("pending_2fa_user_id", None)
    session.pop("webauthn_challenge", None)
    session.pop("webauthn_user_id", None)
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    session.pop("supabase_access_token", None)
    session.pop("supabase_refresh_token", None)
    flash("Logged out.", "success")
    return redirect(url_for("auth.login"))
