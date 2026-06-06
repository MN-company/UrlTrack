import secrets
from datetime import datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from ..auth_middleware import get_current_user, workspace_required
from ..extensions import db
from ..models import Workspace, WorkspaceMember
from ..supabase_client import get_supabase

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        try:
            sb = get_supabase()
            result = sb.auth.sign_in_with_password({"email": email, "password": password})
            session["supabase_access_token"] = result.session.access_token
            session["supabase_refresh_token"] = result.session.refresh_token
            session.permanent = True

            member = WorkspaceMember.query.filter_by(
                user_id=result.user.id,
                status="active",
            ).first()
            if not member:
                return redirect(url_for("auth.onboarding"))
            session["current_workspace_id"] = member.workspace_id
            return redirect(url_for("dashboard.dashboard_links.dashboard_home"))
        except Exception:
            flash("Email o password errati.", "error")
    return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    existing = Workspace.query.first()
    if existing:
        flash("La registrazione è disponibile solo tramite invito.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("La password deve essere di almeno 8 caratteri.", "error")
            return render_template("login.html", mode="register")
        try:
            sb = get_supabase()
            result = sb.auth.sign_up({"email": email, "password": password})
            if result.user:
                if result.session:
                    session["supabase_access_token"] = result.session.access_token
                flash("Account creato. Controlla la tua email per confermare.", "success")
                return redirect(url_for("auth.onboarding"))
        except Exception as e:
            flash(str(e), "error")
    return render_template("login.html", mode="register")


@bp.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    member = WorkspaceMember.query.filter_by(user_id=user.id, status="active").first()
    if member:
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    if request.method == "POST":
        name = request.form.get("workspace_name", "").strip()
        if not name or len(name) < 2:
            flash("Il nome del workspace deve essere di almeno 2 caratteri.", "error")
            return render_template("onboarding.html")

        slug = "".join(c for c in name.lower().replace(" ", "-")[:32] if c.isalnum() or c == "-")
        base_slug = slug
        counter = 1
        while Workspace.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        workspace = Workspace(name=name, slug=slug, owner_user_id=user.id)
        db.session.add(workspace)
        db.session.flush()

        new_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_email=user.email,
            user_id=user.id,
            role="owner",
            status="active",
            joined_at=datetime.utcnow(),
        )
        db.session.add(new_member)
        db.session.commit()

        session["current_workspace_id"] = workspace.id
        flash(f"Workspace '{name}' creato con successo.", "success")
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    return render_template("onboarding.html")


@bp.route("/logout")
def logout():
    try:
        token = session.get("supabase_access_token")
        if token:
            get_supabase().auth.sign_out()
    except Exception:
        pass
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/accept-invite", methods=["GET", "POST"])
def accept_invite():
    token = request.args.get("token") or request.form.get("token")
    if not token:
        flash("Link di invito non valido.", "error")
        return redirect(url_for("auth.login"))

    member = WorkspaceMember.query.filter_by(invite_token=token, status="pending").first()
    if not member:
        flash("Link di invito scaduto o già utilizzato.", "error")
        return redirect(url_for("auth.login"))

    workspace = db.session.get(Workspace, member.workspace_id)

    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("La password deve essere di almeno 8 caratteri.", "error")
            return render_template("accept_invite.html", member=member, workspace=workspace, token=token)

        try:
            sb = get_supabase()
            try:
                result = sb.auth.sign_in_with_password(
                    {"email": member.user_email, "password": password}
                )
            except Exception:
                result = sb.auth.sign_up(
                    {"email": member.user_email, "password": password}
                )

            if result.user:
                member.user_id = result.user.id
                member.status = "active"
                member.joined_at = datetime.utcnow()
                member.invite_token = None
                db.session.commit()

                if result.session:
                    session["supabase_access_token"] = result.session.access_token
                    session["current_workspace_id"] = member.workspace_id

                flash("Benvenuto nel workspace!", "success")
                return redirect(url_for("dashboard.dashboard_links.dashboard_home"))
        except Exception as e:
            flash(str(e), "error")

    return render_template("accept_invite.html", member=member, workspace=workspace, token=token)


@bp.route("/switch-workspace/<workspace_id>")
def switch_workspace(workspace_id: str):
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))
    member = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id, user_id=user.id, status="active"
    ).first()
    if not member:
        abort(403)
    session["current_workspace_id"] = workspace_id
    return redirect(url_for("dashboard.dashboard_links.dashboard_home"))
