import os
import secrets
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ...auth_middleware import workspace_required
from ...extensions import db
from ...models import Workspace, WorkspaceMember

bp = Blueprint("team", __name__)

VALID_ROLES = ["admin", "editor", "analyst", "viewer"]


@bp.route("/settings/team")
@workspace_required("admin")
def team_settings():
    members = WorkspaceMember.query.filter_by(
        workspace_id=g.workspace.id
    ).order_by(WorkspaceMember.invited_at.asc()).all()
    return render_template("team_settings.html", members=members, workspace=g.workspace)


@bp.route("/settings/team/invite", methods=["POST"])
@workspace_required("admin")
def invite_member():
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "editor")

    if not email or "@" not in email:
        flash("Email non valida.", "error")
        return redirect(url_for("dashboard.team.team_settings"))

    if role not in VALID_ROLES:
        flash("Ruolo non valido.", "error")
        return redirect(url_for("dashboard.team.team_settings"))

    existing = WorkspaceMember.query.filter_by(
        workspace_id=g.workspace.id, user_email=email
    ).first()
    if existing:
        flash(f"{email} è già nel workspace.", "error")
        return redirect(url_for("dashboard.team.team_settings"))

    token = secrets.token_urlsafe(32)
    member = WorkspaceMember(
        workspace_id=g.workspace.id,
        user_email=email,
        role=role,
        invited_by=g.current_user.id,
        invite_token=token,
        status="pending",
    )
    db.session.add(member)
    db.session.commit()

    invite_url = url_for("auth.accept_invite", token=token, _external=True)
    try:
        _send_invite_email(email, invite_url, g.workspace.name, g.current_user.email)
        flash(f"Invito inviato a {email}.", "success")
    except Exception as e:
        flash(f"Membro aggiunto ma invio email fallito: {e}", "warning")

    return redirect(url_for("dashboard.team.team_settings"))


@bp.route("/settings/team/role/<member_id>", methods=["POST"])
@workspace_required("admin")
def change_role(member_id: str):
    member = WorkspaceMember.query.filter_by(
        id=member_id, workspace_id=g.workspace.id
    ).first_or_404()

    if member.role == "owner":
        flash("Non puoi cambiare il ruolo dell'owner.", "error")
        return redirect(url_for("dashboard.team.team_settings"))

    new_role = request.form.get("role")
    if new_role not in VALID_ROLES:
        flash("Ruolo non valido.", "error")
        return redirect(url_for("dashboard.team.team_settings"))

    if new_role == "admin" and g.role != "owner":
        flash("Solo l'owner può assegnare il ruolo admin.", "error")
        return redirect(url_for("dashboard.team.team_settings"))

    member.role = new_role
    db.session.commit()
    flash(f"Ruolo aggiornato a {new_role}.", "success")
    return redirect(url_for("dashboard.team.team_settings"))


@bp.route("/settings/team/remove/<member_id>", methods=["POST"])
@workspace_required("admin")
def remove_member(member_id: str):
    member = WorkspaceMember.query.filter_by(
        id=member_id, workspace_id=g.workspace.id
    ).first_or_404()

    if member.role == "owner":
        flash("Non puoi rimuovere l'owner del workspace.", "error")
        return redirect(url_for("dashboard.team.team_settings"))

    if str(member.user_id or "") == str(g.current_user.id):
        flash("Non puoi rimuovere te stesso.", "error")
        return redirect(url_for("dashboard.team.team_settings"))

    db.session.delete(member)
    db.session.commit()
    flash(f"{member.user_email} rimosso dal workspace.", "success")
    return redirect(url_for("dashboard.team.team_settings"))


@bp.route("/settings/team/resend/<member_id>", methods=["POST"])
@workspace_required("admin")
def resend_invite(member_id: str):
    member = WorkspaceMember.query.filter_by(
        id=member_id, workspace_id=g.workspace.id, status="pending"
    ).first_or_404()

    member.invite_token = secrets.token_urlsafe(32)
    member.invited_at = datetime.utcnow()
    db.session.commit()

    invite_url = url_for("auth.accept_invite", token=member.invite_token, _external=True)
    try:
        _send_invite_email(member.user_email, invite_url, g.workspace.name, g.current_user.email)
        flash(f"Invito reinviato a {member.user_email}.", "success")
    except Exception as e:
        flash(f"Errore invio email: {e}", "error")

    return redirect(url_for("dashboard.team.team_settings"))


def _send_invite_email(to_email: str, invite_url: str, workspace_name: str, invited_by: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user or "noreply@urltrack.io")

    subject = f"Sei stato invitato nel workspace '{workspace_name}' su UrlTrack"
    body = (
        f"Ciao,\n\n{invited_by} ti ha invitato nel workspace '{workspace_name}' su UrlTrack.\n\n"
        f"Clicca il link per accettare:\n{invite_url}\n\n"
        "Il link scade dopo 7 giorni.\n"
    )

    if smtp_host and smtp_user and smtp_pass:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to_email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    else:
        print(f"\n[INVITE] To: {to_email}\nURL: {invite_url}\n")
