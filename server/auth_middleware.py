import functools

from flask import g, redirect, session, url_for

from .extensions import db
from .models import User
from .supabase_client import get_supabase


def _user_attr(user, name: str, default=None):
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(name, default)
    return getattr(user, name, default)


def get_current_user():
    token = session.get("supabase_access_token")
    if not token:
        return None
    try:
        user_response = get_supabase().auth.get_user(token)
        return user_response.user if user_response else None
    except Exception:
        session.pop("supabase_access_token", None)
        session.pop("supabase_refresh_token", None)
        return None


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("auth.login"))
        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def current_user():
    return getattr(g, "current_user", None) or get_current_user()


def current_user_email() -> str:
    return _user_attr(current_user(), "email", "") or ""


def current_local_user() -> User | None:
    email = current_user_email().lower()
    if not email:
        return None
    return User.query.filter_by(email=email).first()


def ensure_local_user(email: str, username: str = "", password_hash: str = "") -> User:
    normalized = (email or "").strip().lower()
    user = User.query.filter_by(email=normalized).first()
    if user is not None:
        return user
    user = User(
        email=normalized,
        username=username or normalized.split("@", 1)[0],
        password_hash=password_hash or "supabase-auth",
    )
    db.session.add(user)
    db.session.commit()
    return user
