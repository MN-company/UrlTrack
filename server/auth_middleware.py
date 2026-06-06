import functools

from flask import abort, g, redirect, session, url_for
from flask_login import current_user as flask_current_user
from sqlalchemy import or_

from .extensions import db
from .models import User, Workspace, WorkspaceMember

ROLE_HIERARCHY = ["viewer", "analyst", "editor", "admin", "owner"]


def _attr(user, name: str, default=None):
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(name, default)
    return getattr(user, name, default)


def get_current_user():
    if flask_current_user.is_authenticated:
        return flask_current_user

    token = session.get("supabase_access_token")
    if not token:
        return None
    try:
        from .supabase_client import get_supabase

        response = get_supabase().auth.get_user(token)
        remote_user = response.user if response else None
        if remote_user and _attr(remote_user, "email"):
            return ensure_local_user(_attr(remote_user, "email"))
    except Exception:
        session.pop("supabase_access_token", None)
        session.pop("supabase_refresh_token", None)
    return None


def current_user_email(user=None) -> str:
    return (_attr(user or get_current_user(), "email", "") or "").strip().lower()


def ensure_local_user(email: str, password_hash: str = "", username: str = "") -> User:
    normalized = (email or "").strip().lower()
    user = User.query.filter_by(email=normalized).first()
    if user is not None:
        if password_hash and user.password_hash == "supabase-auth":
            user.password_hash = password_hash
            db.session.commit()
        return user
    user = User(
        email=normalized,
        username=username or normalized.split("@", 1)[0],
        password_hash=password_hash or "supabase-auth",
    )
    db.session.add(user)
    db.session.commit()
    return user


def _membership_query(user, workspace_id: str | None = None):
    identity_values = {str(_attr(user, "id", "") or "")}
    external_id = str(session.get("auth_external_user_id") or "")
    if external_id:
        identity_values.add(external_id)
    identity_values.discard("")

    identity_filter = WorkspaceMember.user_email == current_user_email(user)
    if identity_values:
        identity_filter = or_(
            identity_filter,
            WorkspaceMember.user_id.in_(sorted(identity_values)),
        )

    query = WorkspaceMember.query.filter(
        identity_filter,
        WorkspaceMember.status == "active",
    )
    if workspace_id:
        query = query.filter(WorkspaceMember.workspace_id == workspace_id)
    return query


def get_current_membership(workspace_id: str | None = None):
    user = get_current_user()
    if not user:
        return None
    return _membership_query(user, workspace_id).first()


def get_current_workspace():
    user = get_current_user()
    if not user:
        return None

    workspace_id = session.get("current_workspace_id")
    member = _membership_query(user, workspace_id).first() if workspace_id else None
    if member is None:
        member = _membership_query(user).first()
    if member is None:
        return None

    session["current_workspace_id"] = member.workspace_id
    return db.session.get(Workspace, member.workspace_id)


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

            member = get_current_membership(workspace.id)
            if not member:
                return redirect(url_for("auth.onboarding"))
            g.member = member
            g.role = member.role

            if not has_permission(member.role, min_role):
                abort(403)
            return f(*args, **kwargs)

        return decorated

    return decorator
