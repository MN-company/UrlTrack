import importlib
import sys

import pytest
from werkzeug.security import generate_password_hash


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

    from server import create_app
    from server.extensions import db
    from server.routes.dashboard import links as dashboard_links

    monkeypatch.setattr(dashboard_links, "BASE_DIR", tmp_path, raising=False)

    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        LOGIN_DISABLED=False,
    )

    with app.app_context():
        db.drop_all()
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(app, client):
    from server.extensions import db
    from server.models import User

    class AuthActions:
        def login(self, email="admin@example.com"):
            with app.app_context():
                user = User.query.filter_by(email=email).first()
                if user is None:
                    user = User(
                        email=email,
                        username="admin",
                        password_hash=generate_password_hash("password123456"),
                    )
                    db.session.add(user)
                    db.session.commit()
                user_id = user.id

            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True
            return user_id

    return AuthActions()
