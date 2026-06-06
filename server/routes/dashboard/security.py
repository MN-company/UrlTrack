import base64
import io
import json
import secrets

import bcrypt
import pyotp
import qrcode
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash

from ...extensions import db
from ...models import User
from ...supabase_client import get_supabase, supabase_enabled
from ...utils import sanitize


bp = Blueprint("dashboard_security", __name__)


@bp.route("/security")
@login_required
def security_settings():
    user = db.session.get(User, current_user.id)
    return render_template(
        "security_settings.html",
        user=user,
        backup_count=len(user.backup_code_hashes),
        passkey_count=len(user.passkeys),
        passkeys=user.passkeys,
    )


@bp.route("/security/2fa/setup")
@login_required
def setup_2fa():
    user = db.session.get(User, current_user.id)
    if user.totp_enabled:
        flash("2FA is already enabled.", "warning")
        return redirect(url_for("dashboard.dashboard_security.security_settings"))

    secret = pyotp.random_base32()
    session["temp_totp_secret"] = secret
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="UrlTrack Dashboard")

    qr_code = qrcode.QRCode(version=1, box_size=10, border=4)
    qr_code.add_data(provisioning_uri)
    qr_code.make(fit=True)

    image = qr_code.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return render_template(
        "2fa_setup.html",
        secret=secret,
        qr_code=base64.b64encode(buffer.getvalue()).decode(),
        email=user.email,
    )


@bp.route("/security/2fa/verify_setup", methods=["POST"])
@login_required
def verify_2fa_setup():
    user = db.session.get(User, current_user.id)
    secret = session.get("temp_totp_secret")
    if not secret:
        flash("Session expired. Please start setup again.", "error")
        return redirect(url_for("dashboard.dashboard_security.security_settings"))

    code = sanitize(request.form.get("totp_code"), 6)
    if pyotp.TOTP(secret).verify(code, valid_window=1):
        backup_codes = [secrets.token_hex(6).upper() for _ in range(10)]
        hashed_codes = [bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode() for code in backup_codes]

        user.totp_secret = secret
        user.totp_enabled = True
        user.backup_codes = json.dumps(hashed_codes)
        db.session.commit()

        session.pop("temp_totp_secret", None)
        session["new_backup_codes"] = backup_codes
        flash("2FA enabled successfully.", "success")
        return redirect(url_for("dashboard.dashboard_security.show_backup_codes"))

    flash("Invalid verification code.", "error")
    return redirect(url_for("dashboard.dashboard_security.setup_2fa"))


@bp.route("/security/2fa/backup_codes")
@login_required
def show_backup_codes():
    backup_codes = session.pop("new_backup_codes", None)
    if not backup_codes:
        flash("Backup codes are only shown immediately after generation.", "warning")
        return redirect(url_for("dashboard.dashboard_security.security_settings"))
    return render_template("backup_codes.html", backup_codes=backup_codes)


@bp.route("/security/2fa/regenerate_backup", methods=["POST"])
@login_required
def regenerate_backup_codes():
    user = db.session.get(User, current_user.id)
    if not user.totp_enabled:
        flash("2FA is not enabled.", "error")
        return redirect(url_for("dashboard.dashboard_security.security_settings"))

    backup_codes = [secrets.token_hex(6).upper() for _ in range(10)]
    hashed_codes = [bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode() for code in backup_codes]
    user.backup_codes = json.dumps(hashed_codes)
    db.session.commit()

    session["new_backup_codes"] = backup_codes
    flash("Backup codes regenerated.", "success")
    return redirect(url_for("dashboard.dashboard_security.show_backup_codes"))


@bp.route("/security/2fa/disable", methods=["POST"])
@login_required
def disable_2fa():
    user = db.session.get(User, current_user.id)
    password = request.form.get("password", "")
    if not check_password_hash(user.password_hash, password):
        flash("Incorrect password.", "error")
        return redirect(url_for("dashboard.dashboard_security.security_settings"))

    user.totp_enabled = False
    user.totp_secret = None
    user.backup_codes = None
    db.session.commit()
    flash("2FA disabled.", "success")
    return redirect(url_for("dashboard.dashboard_security.security_settings"))


@bp.route("/security/password", methods=["POST"])
@login_required
def change_password():
    user = db.session.get(User, current_user.id)
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not check_password_hash(user.password_hash, current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("dashboard.dashboard_security.security_settings"))
    if len(new_password) < 12:
        flash("Password must be at least 12 characters long.", "error")
        return redirect(url_for("dashboard.dashboard_security.security_settings"))
    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("dashboard.dashboard_security.security_settings"))

    if supabase_enabled() and session.get("supabase_access_token"):
        try:
            client = get_supabase()
            client.auth.set_session(
                session["supabase_access_token"],
                session.get("supabase_refresh_token", ""),
            )
            result = client.auth.update_user({"password": new_password})
            result_session = getattr(result, "session", None)
            if result_session:
                session["supabase_access_token"] = result_session.access_token
                session["supabase_refresh_token"] = result_session.refresh_token
        except Exception:
            flash("Supabase non ha accettato il cambio password. Nessuna modifica applicata.", "error")
            return redirect(url_for("dashboard.dashboard_security.security_settings"))

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash("Password updated successfully.", "success")
    return redirect(url_for("dashboard.dashboard_security.security_settings"))
