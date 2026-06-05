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


def test_create_full_normalizes_allowed_countries_and_safe_url(app, client, auth):
    from server.models import Link

    auth.login()
    response = client.post(
        "/dashboard/create_full",
        data={
            "slug": "geo-safe",
            "destination": "https://example.com",
            "safe_url": "",
            "allowed_countries": "it;us, de, XXX,1a,fr",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        link = Link.query.filter_by(slug="geo-safe").first()
        assert link is not None
        assert link.allowed_countries == "IT,US,DE,FR"
        assert link.safe_url == "https://www.google.com"


def test_create_full_handles_invalid_numeric_fields(app, client, auth):
    from server.models import Link

    auth.login()
    response = client.post(
        "/dashboard/create_full",
        data={
            "slug": "badnums",
            "destination": "https://example.com",
            "max_clicks": "nope",
            "expiration_minutes": "-99",
            "schedule_start_hour": "99",
            "schedule_end_hour": "wat",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        link = Link.query.filter_by(slug="badnums").first()
        assert link is not None
        assert link.max_clicks == 0
        assert link.expiration_minutes == 0
        assert link.schedule_start_hour is None
        assert link.schedule_end_hour is None


def test_qr_missing_slug_returns_404(app, client, auth):
    auth.login()
    response = client.get("/dashboard/qr/missing-slug")
    assert response.status_code == 404


def test_qr_code_supports_svg_and_custom_png(app, client, auth):
    from server.extensions import db
    from server.models import Link

    auth.login()
    with app.app_context():
        link = Link(slug="qr-custom", destination="https://example.com")
        db.session.add(link)
        db.session.commit()

    png_response = client.get(
        "/dashboard/qr/qr-custom?fg_color=%2300C853&bg_color=%23ffffff&gradient_color=%2300BCD4&dot_style=circle"
    )
    assert png_response.status_code == 200
    assert png_response.headers["Content-Type"] == "image/png"
    assert png_response.data.startswith(b"\x89PNG")

    svg_response = client.get("/dashboard/qr/qr-custom?format=svg&transparent_bg=1")
    assert svg_response.status_code == 200
    assert svg_response.headers["Content-Type"] == "image/svg+xml"
    assert b"<svg" in svg_response.data


def test_qr_save_persists_config(app, client, auth):
    import json

    from server.extensions import db
    from server.models import Link

    auth.login()
    with app.app_context():
        link = Link(slug="qr-save", destination="https://example.com")
        db.session.add(link)
        db.session.commit()

    response = client.post(
        "/dashboard/qr_save/qr-save",
        data={
            "fg_color": "#111111",
            "bg_color": "#eeeeee",
            "enable_gradient": "on",
            "gradient_color": "#00C853",
            "gradient_direction": "vertical",
            "error_correction": "Q",
            "dot_style": "rounded",
            "transparent_bg": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        link = Link.query.filter_by(slug="qr-save").first()
        config = json.loads(link.qr_config)
        assert config["fg_color"] == "#111111"
        assert config["bg_color"] == "#EEEEEE"
        assert config["gradient_color"] == "#00C853"
        assert config["gradient_direction"] == "vertical"
        assert config["error_correction"] == "Q"
        assert config["dot_style"] == "rounded"
        assert config["transparent_bg"] is True


def test_edit_page_exposes_country_picker_and_safe_url(app, client, auth):
    from server.extensions import db
    from server.models import Link

    auth.login()
    with app.app_context():
        link = Link(
            slug="editable",
            destination="https://example.com",
            safe_url="https://safe.example.com",
            allowed_countries="IT,US",
        )
        db.session.add(link)
        db.session.commit()

    response = client.get("/dashboard/edit/editable")
    assert response.status_code == 200
    assert b'const EDIT_ALLOWED_COUNTRIES = "IT,US";' in response.data
    assert b'name="safe_url"' in response.data
    assert b'id="countriesSelect"' in response.data
