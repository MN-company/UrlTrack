import functools

from flask import abort, g, redirect, session, url_for

from .extensions import db
from .models import Workspace, WorkspaceMember

ROLE_HIERARCHY = ["viewer", "analyst", "editor", "admin", "owner"]


def get_current_user():
    token = session.get("supabase_access_token")
    if not token:
        return None
    try:
        from .supabase_client import get_supabase
        user = get_supabase().auth.get_user(token)
        return user.user if user else None
    except Exception:
        session.pop("supabase_access_token", None)
        return None


def get_current_workspace():
    user = get_current_user()
    if not user:
        return None

    workspace_id = session.get("current_workspace_id")
    if workspace_id:
        member = WorkspaceMember.query.filter_by(
            workspace_id=workspace_id,
            user_id=user.id,
            status="active",
        ).first()
        if member:
            return db.session.get(Workspace, workspace_id)

    member = WorkspaceMember.query.filter_by(
        user_id=user.id,
        status="active",
    ).first()
    if member:
        session["current_workspace_id"] = member.workspace_id
        return db.session.get(Workspace, member.workspace_id)
    return None


def has_permission(role: str, required_role: str) -> bool:
    try:
        return ROLE_HIERARCHY.index(role) >= ROLE_HIERARCHY.index(required_role)
    except ValueError:
        return False


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("auth.login"))
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def workspace_required(min_role: str = "viewer"):
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect(url_for("auth.login"))
            g.current_user = user

            workspace = get_current_workspace()
            if not workspace:
                return redirect(url_for("auth.onboarding"))
            g.workspace = workspace

            member = WorkspaceMember.query.filter_by(
                workspace_id=workspace.id,
                user_id=user.id,
                status="active",
            ).first()
            if not member:
                return redirect(url_for("auth.onboarding"))
            g.member = member
            g.role = member.role

            if not has_permission(member.role, min_role):
                abort(403)

            return f(*args, **kwargs)
        return decorated
    return decorator
