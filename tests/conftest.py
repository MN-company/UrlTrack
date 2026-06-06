import importlib
import sys
from types import SimpleNamespace

import pytest

TEST_USER_ID = "test-user-0001"
TEST_WS_ID = "test-workspace-0001"


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    env_path = tmp_path / ".env"
    env_path.write_text("SECRET_KEY=test-secret\n", encoding="utf-8")

    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SERVER_URL", "https://track.example")
    monkeypatch.setenv("SKIP_BACKGROUND_WORKER", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    monkeypatch.setenv("WEBHOOK_URL", "")
    monkeypatch.setenv("WEBHOOK_SECRET", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")

    for module_name in list(sys.modules):
        if module_name == "server" or module_name.startswith("server."):
            del sys.modules[module_name]

    from sqlalchemy import event

    from server import create_app
    from server.extensions import db
    from server.models import Lead, Link, Visit, Visitor, VisitorSignal, Workspace
    from server.routes.dashboard import links as dashboard_links

    monkeypatch.setattr(dashboard_links, "BASE_DIR", tmp_path, raising=False)

    # Auto-stamp workspace_id on seeded rows so legacy tests stay workspace-scoped.
    def _stamp_workspace(mapper, connection, target):
        if getattr(target, "workspace_id", None) is None:
            target.workspace_id = TEST_WS_ID

    stamped_models = (Link, Visit, Visitor, Lead, VisitorSignal)
    for model in stamped_models:
        event.listen(model, "before_insert", _stamp_workspace)

    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        LOGIN_DISABLED=False,
    )

    with app.app_context():
        db.drop_all()
        db.create_all()
        # Always-present workspace so FK + scoped queries resolve.
        db.session.add(
            Workspace(
                id=TEST_WS_ID,
                name="Test Workspace",
                slug="test-workspace",
                owner_user_id=TEST_USER_ID,
            )
        )
        db.session.commit()

    yield app

    for model in stamped_models:
        event.remove(model, "before_insert", _stamp_workspace)

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(app, client, monkeypatch):
    from werkzeug.security import generate_password_hash

    from server import auth_middleware
    from server.extensions import db
    from server.models import User, WorkspaceMember

    class AuthActions:
        def login(self, email="admin@example.com", role="owner"):
            with app.app_context():
                # Local User row backs the Flask-Login security/passkey routes.
                user = User.query.filter_by(email=email).first()
                if user is None:
                    user = User(
                        email=email,
                        username="admin",
                        password_hash=generate_password_hash("password123456"),
                    )
                    db.session.add(user)
                    db.session.commit()
                local_user_id = user.id

                member = WorkspaceMember.query.filter_by(
                    workspace_id=TEST_WS_ID, user_id=TEST_USER_ID
                ).first()
                if member is None:
                    member = WorkspaceMember(
                        workspace_id=TEST_WS_ID,
                        user_email=email,
                        user_id=TEST_USER_ID,
                        role=role,
                        status="active",
                    )
                    db.session.add(member)
                else:
                    member.role = role
                    member.user_email = email
                db.session.commit()

            fake_user = SimpleNamespace(id=TEST_USER_ID, email=email)
            monkeypatch.setattr(auth_middleware, "get_current_user", lambda: fake_user)

            with client.session_transaction() as session:
                session["supabase_access_token"] = "test-token"
                session["current_workspace_id"] = TEST_WS_ID
                session["_user_id"] = str(local_user_id)
                session["_fresh"] = True
            return TEST_USER_ID

    return AuthActions()
