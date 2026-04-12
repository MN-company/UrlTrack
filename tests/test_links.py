from pathlib import Path


def test_create_link_returns_full_url(app, client, auth):
    auth.login()
    response = client.post(
        "/dashboard/create",
        data={"slug": "alpha", "destination": "https://example.com"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"https://track.example/alpha" in response.data


def test_settings_post_updates_config(app, client, auth):
    from flask import current_app
    from server.routes.dashboard import links as dashboard_links

    auth.login()
    response = client.post(
        "/dashboard/settings",
        data={
            "settings_scope": "runtime",
            "server_url": "https://new-track.example",
            "gemini_model": "gemini-2.0-pro",
            "webhook_url": "https://hooks.example/ingest",
            "telegram_chat_id": "123456",
            "visit_retention_days": "30",
            "mask_with_isgd": "on",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        assert current_app.config["GEMINI_MODEL"] == "gemini-2.0-pro"
        assert current_app.config["WEBHOOK_URL"] == "https://hooks.example/ingest"
        assert current_app.config["TELEGRAM_CHAT_ID"] == "123456"
        assert current_app.config["VISIT_RETENTION_DAYS"] == 30
        assert current_app.config["MASK_WITH_ISGD"] is True
        assert current_app.config["SERVER_URL"] == "https://track.example"

    env_text = (Path(dashboard_links.BASE_DIR) / ".env").read_text(encoding="utf-8")
    assert "GEMINI_MODEL='gemini-2.0-pro'" in env_text
    assert "WEBHOOK_URL='https://hooks.example/ingest'" in env_text
