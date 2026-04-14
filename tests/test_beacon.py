import json


def _create_visit(app):
    from server.extensions import db
    from server.models import Link, Visit

    with app.app_context():
        link = Link(slug="alpha", destination="https://example.com")
        db.session.add(link)
        db.session.commit()

        visit = Visit(link_id=link.id, ip_address="1.1.1.1")
        db.session.add(visit)
        db.session.commit()
        return visit.id


def test_beacon_accepts_new_fields(app, client, auth):
    from server.extensions import db
    from server.models import Visit
    from server.utils import sign_visit_token

    auth.login()
    visit_id = _create_visit(app)
    token = sign_visit_token(visit_id)

    payload = {
        "visit_id": visit_id,
        "visit_token": token,
        "screen_res": "1920x1080",
        "screen_depth": 24,
        "pixel_ratio": 2.0,
        "timezone": "Europe/Rome",
        "platform": "MacIntel",
        "touch_points": 0,
        "dark_mode": True,
        "reduced_motion": False,
        "connection_type": "4g",
        "language": "en-US",
        "do_not_track": "1",
        "adblock": True,
        "canvas_hash": "abcd1234",
        "audio_fp": "audio123",
        "fonts": "Arial,Helvetica Neue,Monaco",
        "vendor": "Vendor Inc",
        "renderer": "Renderer 9000",
        "extensions_hash": "deadbeef",
        "max_texture": 4096,
        "client_rects_fp": "beadfeed",
        "webrtc_ips": ["10.0.0.8", "172.16.0.1"],
        "extensions_detected": ["uBlock Origin", "MetaMask"],
        "cpu_cores": 8,
        "ram_gb": 16,
        "taskbar_size": 0,
        "ua_brands": '[{"brand":"Chromium"}]',
        "webdriver": False,
        "dwell_ms": 4200,
    }

    response = client.post("/api/beacon", json=payload)
    assert response.status_code == 200

    with app.app_context():
        stored = db.session.get(Visit, visit_id)
        assert stored.screen_depth == 24
        assert stored.pixel_ratio == 2.0
        assert stored.touch_points == 0
        assert stored.canvas_hash == "abcd1234"
        assert stored.audio_fp == "audio123"
        assert stored.webgl_vendor == "Vendor Inc"
        assert stored.webgl_renderer == "Renderer 9000"
        assert stored.webgl_extensions_hash == "deadbeef"
        assert stored.webgl_max_texture == 4096
        assert stored.client_rects_fp == "beadfeed"
        assert stored.webrtc_ips == json.dumps(["10.0.0.8", "172.16.0.1"])
        assert stored.extensions_detected == json.dumps(["uBlock Origin", "MetaMask"])
        assert stored.taskbar_size == 0
        assert stored.dwell_ms == 4200


def test_beacon_rejects_invalid_dwell(app, client, auth):
    from server.extensions import db
    from server.models import Visit
    from server.utils import sign_visit_token

    auth.login()
    visit_id = _create_visit(app)
    token = sign_visit_token(visit_id)

    response = client.post(
        "/api/beacon",
        json={
            "visit_id": visit_id,
            "visit_token": token,
            "canvas_hash": "abcd1234",
            "dwell_ms": 999999,
        },
    )
    assert response.status_code == 200

    with app.app_context():
        stored = db.session.get(Visit, visit_id)
        assert stored.canvas_hash == "abcd1234"
        assert stored.dwell_ms is None


def test_beacon_missing_token_returns_403(app, client):
    visit_id = _create_visit(app)
    response = client.post("/api/beacon", json={"visit_id": visit_id, "canvas_hash": "abcd1234"})
    assert response.status_code == 403
