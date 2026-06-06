import base64
import json
from datetime import datetime

import bcrypt
import pyotp
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import login_user, logout_user
from sqlalchemy import or_
from webauthn import generate_authentication_options, options_to_json, verify_authentication_response
from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth_middleware import current_user_email, ensure_local_user, get_current_user
from ..config import Config
from ..extensions import db, limiter
from ..models import User, Workspace, WorkspaceMember
from ..supabase_client import get_supabase, supabase_enabled
from ..utils import safe_json, sanitize

bp = Blueprint("auth", __name__)


def _member_for(email: str, external_id: str = ""):
    filters = [WorkspaceMember.user_email == email]
    if external_id:
        filters.append(WorkspaceMember.user_id == external_id)
    return WorkspaceMember.query.filter(
        or_(*filters),
        WorkspaceMember.status == "active",
    ).first()


def _start_session(local_user: User, external_id: str = "", access_token: str = "", refresh_token: str = ""):
    login_user(local_user, remember=True)
    session.permanent = True
    if external_id:
        session["auth_external_user_id"] = external_id
    if access_token:
        session["supabase_access_token"] = access_token
    if refresh_token:
        session["supabase_refresh_token"] = refresh_token

    member = _member_for(local_user.email, external_id)
    if member:
        session["current_workspace_id"] = member.workspace_id
    return member


def _pending_2fa(local_user: User, external_id: str = "", access_token: str = "", refresh_token: str = ""):
    session["pending_2fa_user_id"] = local_user.id
    session["pending_external_user_id"] = external_id
    session["pending_supabase_access_token"] = access_token
    session["pending_supabase_refresh_token"] = refresh_token


def _finish_pending_2fa(local_user: User):
    member = _start_session(
        local_user,
        str(session.pop("pending_external_user_id", "") or ""),
        str(session.pop("pending_supabase_access_token", "") or ""),
        str(session.pop("pending_supabase_refresh_token", "") or ""),
    )
    session.pop("pending_2fa_user_id", None)
    return member


def _passkey_rp_id() -> str:
    return Config.SERVER_URL.replace("https://", "").replace("http://", "").split(":")[0].split("/")[0]


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def login():
    if get_current_user():
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    if request.method == "POST" and ("totp_code" in request.form or "backup_code" in request.form):
        local_user = db.session.get(User, session.get("pending_2fa_user_id"))
        if not local_user:
            flash("Sessione MFA scaduta. Accedi di nuovo.", "error")
            return redirect(url_for("auth.login"))

        verified = False
        if "totp_code" in request.form:
            code = sanitize(request.form.get("totp_code"), 6)
            verified = bool(
                local_user.totp_enabled
                and local_user.totp_secret
                and pyotp.TOTP(local_user.totp_secret).verify(code, valid_window=1)
            )
        else:
            candidate = sanitize(request.form.get("backup_code"), 64).replace("-", "")
            remaining = []
            for stored_hash in local_user.backup_code_hashes:
                if not verified and bcrypt.checkpw(candidate.encode(), stored_hash.encode()):
                    verified = True
                    continue
                remaining.append(stored_hash)
            if verified:
                local_user.backup_codes = json.dumps(remaining)
                db.session.commit()

        if verified:
            member = _finish_pending_2fa(local_user)
            flash("Accesso verificato.", "success")
            return redirect(
                url_for("dashboard.dashboard_links.dashboard_home")
                if member
                else url_for("auth.onboarding")
            )
        flash("Codice di verifica non valido.", "error")
        return render_template("2fa_verify.html", email=local_user.email, has_passkey=bool(local_user.passkeys))

    if request.method == "POST":
        email = sanitize(request.form.get("email"), 255).lower()
        password = request.form.get("password", "")
        try:
            external_id = ""
            access_token = ""
            refresh_token = ""
            if supabase_enabled():
                result = get_supabase().auth.sign_in_with_password({"email": email, "password": password})
                external_id = str(result.user.id)
                access_token = result.session.access_token
                refresh_token = result.session.refresh_token
                local_user = ensure_local_user(email, generate_password_hash(password))
            else:
                local_user = User.query.filter_by(email=email).first()
                if not local_user or not check_password_hash(local_user.password_hash, password):
                    raise ValueError("Invalid credentials")

            if local_user.totp_enabled:
                _pending_2fa(local_user, external_id, access_token, refresh_token)
                return render_template("2fa_verify.html", email=email, has_passkey=bool(local_user.passkeys))

            member = _start_session(local_user, external_id, access_token, refresh_token)
            return redirect(
                url_for("dashboard.dashboard_links.dashboard_home")
                if member
                else url_for("auth.onboarding")
            )
        except Exception:
            flash("Email o password errati.", "error")
    return render_template("login.html", mode="login", supabase_enabled=supabase_enabled())


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def register():
    if Workspace.query.first():
        flash("La registrazione è disponibile solo tramite invito.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = sanitize(request.form.get("email"), 255).lower()
        password = request.form.get("password", "")
        if "@" not in email or len(password) < 12:
            flash("Inserisci un'email valida e una password di almeno 12 caratteri.", "error")
            return render_template("login.html", mode="register", supabase_enabled=supabase_enabled())
        try:
            local_user = ensure_local_user(email, generate_password_hash(password))
            if supabase_enabled():
                result = get_supabase().auth.sign_up({"email": email, "password": password})
                if not result.session:
                    flash("Account creato. Conferma l'email, poi accedi.", "success")
                    return redirect(url_for("auth.login"))
                _start_session(
                    local_user,
                    str(result.user.id),
                    result.session.access_token,
                    result.session.refresh_token,
                )
            else:
                _start_session(local_user)
            return redirect(url_for("auth.onboarding"))
        except Exception as exc:
            flash(str(exc), "error")
    return render_template("login.html", mode="register", supabase_enabled=supabase_enabled())


@bp.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    email = current_user_email(user)
    external_id = str(session.get("auth_external_user_id") or user.id)
    member = _member_for(email, external_id)
    if member:
        session["current_workspace_id"] = member.workspace_id
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    if request.method == "POST":
        name = sanitize(request.form.get("workspace_name"), 128)
        if len(name) < 2:
            flash("Il nome del workspace deve essere di almeno 2 caratteri.", "error")
            return render_template("onboarding.html")

        base_slug = "".join(c for c in name.lower().replace(" ", "-")[:32] if c.isalnum() or c == "-") or "workspace"
        slug = base_slug
        counter = 1
        while Workspace.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        workspace = Workspace(name=name, slug=slug, owner_user_id=external_id)
        db.session.add(workspace)
        db.session.flush()
        db.session.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_email=email,
                user_id=external_id,
                role="owner",
                status="active",
                joined_at=datetime.utcnow(),
            )
        )
        db.session.commit()
        session["current_workspace_id"] = workspace.id
        flash(f"Workspace '{name}' creato.", "success")
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))
    return render_template("onboarding.html")


@bp.route("/logout")
def logout():
    if supabase_enabled() and session.get("supabase_access_token"):
        try:
            get_supabase().auth.sign_out()
        except Exception:
            pass
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/accept-invite", methods=["GET", "POST"])
def accept_invite():
    token = request.args.get("token") or request.form.get("token")
    member = WorkspaceMember.query.filter_by(invite_token=token, status="pending").first() if token else None
    if not member:
        flash("Link di invito scaduto o non valido.", "error")
        return redirect(url_for("auth.login"))
    workspace = db.session.get(Workspace, member.workspace_id)

    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 12:
            flash("La password deve essere di almeno 12 caratteri.", "error")
            return render_template("accept_invite.html", member=member, workspace=workspace, token=token)
        try:
            local_user = ensure_local_user(member.user_email, generate_password_hash(password))
            external_id = str(local_user.id)
            access_token = ""
            refresh_token = ""
            if supabase_enabled():
                try:
                    result = get_supabase().auth.sign_in_with_password(
                        {"email": member.user_email, "password": password}
                    )
                except Exception:
                    result = get_supabase().auth.sign_up(
                        {"email": member.user_email, "password": password}
                    )
                external_id = str(result.user.id)
                if result.session:
                    access_token = result.session.access_token
                    refresh_token = result.session.refresh_token
            member.user_id = external_id
            member.status = "active"
            member.joined_at = datetime.utcnow()
            member.invite_token = None
            db.session.commit()
            _start_session(local_user, external_id, access_token, refresh_token)
            session["current_workspace_id"] = member.workspace_id
            return redirect(url_for("dashboard.dashboard_links.dashboard_home"))
        except Exception as exc:
            flash(str(exc), "error")
    return render_template("accept_invite.html", member=member, workspace=workspace, token=token)


@bp.route("/switch-workspace/<workspace_id>")
def switch_workspace(workspace_id: str):
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))
    member = WorkspaceMember.query.filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.status == "active",
        or_(
            WorkspaceMember.user_email == current_user_email(user),
            WorkspaceMember.user_id == str(session.get("auth_external_user_id") or user.id),
        ),
    ).first()
    if not member:
        abort(403)
    session["current_workspace_id"] = workspace_id
    return redirect(url_for("dashboard.dashboard_links.dashboard_home"))


@bp.route("/auth/passkey/options", methods=["POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def passkey_auth_options():
    email = sanitize((request.get_json(silent=True) or {}).get("email"), 255).lower()
    user = User.query.filter_by(email=email).first()
    if not user or not user.passkeys:
        return jsonify({"error": "Nessuna passkey registrata."}), 404
    credentials = [
        PublicKeyCredentialDescriptor(id=base64.urlsafe_b64decode(item["id"] + "=="))
        for item in user.passkeys
        if item.get("id")
    ]
    options = generate_authentication_options(
        rp_id=_passkey_rp_id(),
        allow_credentials=credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    session["webauthn_challenge"] = base64.b64encode(options.challenge).decode()
    session["webauthn_user_id"] = user.id
    return jsonify(json.loads(options_to_json(options)))


@bp.route("/auth/passkey/verify", methods=["POST"])
@limiter.limit(Config.RATE_LIMIT_AUTH)
def passkey_auth_verify():
    payload = request.get_json(silent=True) or {}
    user = db.session.get(User, session.get("webauthn_user_id"))
    challenge = session.get("webauthn_challenge")
    if not user or not challenge:
        return jsonify({"verified": False, "error": "Sessione scaduta."}), 400
    credentials = safe_json(user.passkey_credentials, []) or []
    credential_id = payload.get("id") or payload.get("rawId")
    matching = next((item for item in credentials if item.get("id") == credential_id), None)
    if not matching:
        return jsonify({"verified": False, "error": "Passkey non trovata."}), 404
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
    member = _start_session(user)
    session.pop("webauthn_challenge", None)
    session.pop("webauthn_user_id", None)
    return jsonify(
        {
            "verified": True,
            "redirect": url_for("dashboard.dashboard_links.dashboard_home")
            if member
            else url_for("auth.onboarding"),
        }
    )
