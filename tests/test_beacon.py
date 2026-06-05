import json
from pathlib import Path


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
        assert stored.beacon_received_at is not None
        assert stored.fingerprint_version == 1
        assert stored.fingerprint_composite_v1
        assert stored.identity_confidence == 0
        assert stored.risk_score == 8
        reasons = json.loads(stored.match_reasons_json)
        assert reasons["risk"] == ["adblock_or_privacy_extension"]
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
        assert stored.beacon_received_at is not None
        assert stored.dwell_ms is None


def test_beacon_missing_token_returns_403(app, client):
    visit_id = _create_visit(app)
    response = client.post("/api/beacon", json={"visit_id": visit_id, "canvas_hash": "abcd1234"})
    assert response.status_code == 403


def test_thumbmark_fp_endpoint_stores_payload_and_enqueues(app, client, monkeypatch):
    from server.extensions import db
    from server.models import Visit
    from server.routes import public as public_routes
    from server.utils import sign_visit_token

    class QueueRecorder:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)

    queue = QueueRecorder()
    monkeypatch.setattr(public_routes, "log_queue", queue)
    visit_id = _create_visit(app)
    token = sign_visit_token(visit_id)

    response = client.post(
        "/fp",
        json={
            "visit_id": visit_id,
            "visit_token": token,
            "thumbmark_hash": "tm-hash-1",
            "thumbmark_raw": '{"thumbmark":"tm-hash-1","components":{}}',
            "fp_canvas_hash": "canvas-tm",
            "fp_audio_hash": "audio-tm",
            "fp_webgl_hash": "webgl-tm",
            "fp_screen_profile": "1920x1080x24@2",
            "fp_hardware_profile": "8c/16gb/0tp",
            "fp_languages": "it-IT,en-US",
            "fp_timezone": "Europe/Rome",
        },
    )

    assert response.status_code == 204
    assert queue.items == [{"type": "enrich_visit", "visit_id": visit_id, "notify": False, "thumbmark_api": True}]

    with app.app_context():
        stored = db.session.get(Visit, visit_id)
        assert stored.thumbmark_hash == "tm-hash-1"
        assert stored.fp_canvas_hash == "canvas-tm"
        assert stored.canvas_hash == "canvas-tm"
        assert stored.audio_fp == "audio-tm"
        assert stored.screen_res == "1920x1080"
        assert stored.pixel_ratio == 2.0
        assert stored.cpu_cores == 8
        assert stored.ram_gb == 16
        assert stored.beacon_received_at is not None


def test_loading_template_uses_thumbmark_public_api():
    template = (Path(__file__).resolve().parents[1] / "server/templates/loading.html").read_text(encoding="utf-8")
    assert "new ThumbmarkJS.Thumbmark" not in template
    assert "ThumbmarkJS.getFingerprint" in template


def test_thumbmark_api_request_keeps_api_key_out_of_body_and_authorization(app, monkeypatch):
    from server.extensions import db
    from server.models import Link, Visit
    from server.services import thumbmark

    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"visitorId": "tm-api-visitor", "confidence": 0.7}

    def fake_post(url, *, headers, json, timeout):
        captured["headers"] = headers
        captured["json"] = json
        return Response()

    monkeypatch.setattr(thumbmark.requests, "post", fake_post)

    with app.app_context():
        app.config["THUMBMARK_API_KEY"] = "secret-key"
        link = Link(slug="tm-api", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        visit = Visit(
            link_id=link.id,
            thumbmark_hash="tm-hash",
            thumbmark_raw='{"components":{"canvas":"abc"},"version":"1.0"}',
        )
        db.session.add(visit)
        db.session.commit()

        result = thumbmark.call_thumbmark_api(visit)

        assert result["visitorId"] == "tm-api-visitor"
        assert captured["headers"]["x-api-key"] == "secret-key"
        assert "Authorization" not in captured["headers"]
        assert captured["json"]["options"].get("api_key") is None


def test_thumbmark_signals_match_same_visitor(app):
    from server.extensions import db
    from server.models import Link, Visit, VisitorSignal
    from server.services.scoring import apply_visit_scoring

    with app.app_context():
        link = Link(slug="thumbmark-match", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        first = Visit(
            link_id=link.id,
            ip_address="1.1.1.1",
            thumbmark_hash="shared-thumbmark",
            fp_canvas_hash="shared-canvas",
            fp_audio_hash="shared-audio",
            fp_webgl_hash="shared-webgl",
        )
        second = Visit(
            link_id=link.id,
            ip_address="1.1.1.2",
            thumbmark_hash="shared-thumbmark",
            fp_canvas_hash="shared-canvas",
            fp_audio_hash="shared-audio",
            fp_webgl_hash="shared-webgl",
        )
        db.session.add_all([first, second])
        db.session.commit()

        apply_visit_scoring(first)
        apply_visit_scoring(second)
        db.session.commit()

        assert first.visitor_id
        assert second.visitor_id == first.visitor_id
        assert second.identity_confidence >= 60
        signal = VisitorSignal.query.filter_by(
            visitor_id=first.visitor_id,
            signal_type="thumbmark_hash",
            signal_value="shared-thumbmark",
        ).first()
        assert signal is not None
        assert signal.occurrence_count == 2


def test_api_invalid_visit_id_returns_404_not_500(app, client, auth):
    from server.utils import sign_visit_token

    auth.login()
    token = sign_visit_token(123)
    beacon_response = client.post("/api/beacon", json={"visit_id": "not-an-int", "visit_token": token})
    assert beacon_response.status_code == 403

    dwell_response = client.post("/api/dwell", json={"visit_id": "not-an-int", "visit_token": token, "dwell_ms": 1000})
    assert dwell_response.status_code == 403


def test_partial_email_invalid_visit_id_returns_404(app, client, monkeypatch):
    from server.routes import api as api_routes
    from server.utils import sign_visit_token

    monkeypatch.setattr(api_routes.Config, "ALLOW_PARTIAL_EMAIL_CAPTURE", True)
    response = client.post(
        "/api/partial_email",
        data={
            "visit_id": "123",
            "visit_token": sign_visit_token(123),
            "partial_email": "person@example.com",
        },
    )
    assert response.status_code == 404


def test_beacon_same_prior_email_and_fingerprint_scores_identity(app, client, auth):
    from server.extensions import db
    from server.models import Link, Visit
    from server.utils import sign_visit_token

    auth.login()
    with app.app_context():
        link = Link(slug="identity", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        prior = Visit(
            link_id=link.id,
            ip_address="1.1.1.1",
            email="same@example.com",
            canvas_hash="canvas-a",
            audio_fp="audio-a",
            webgl_vendor="vendor",
            webgl_renderer="renderer",
            timezone="Europe/Rome",
            screen_res="1920x1080",
            pixel_ratio=2.0,
            device_type="Desktop",
            os_family="Mac OS X",
        )
        current = Visit(
            link_id=link.id,
            ip_address="1.1.1.2",
            email="same@example.com",
            device_type="Desktop",
            os_family="Mac OS X",
        )
        db.session.add_all([prior, current])
        db.session.commit()
        visit_id = current.id

    token = sign_visit_token(visit_id)
    response = client.post(
        "/api/beacon",
        json={
            "visit_id": visit_id,
            "visit_token": token,
            "canvas_hash": "canvas-a",
            "audio_fp": "audio-a",
            "vendor": "vendor",
            "renderer": "renderer",
            "timezone": "Europe/Rome",
            "screen_res": "1920x1080",
            "pixel_ratio": 2.0,
        },
    )
    assert response.status_code == 200

    with app.app_context():
        stored = db.session.get(Visit, visit_id)
        reasons = json.loads(stored.match_reasons_json)
        assert stored.identity_confidence >= 70
        assert stored.risk_score == 0
        assert "same_email" in reasons["identity"]
        assert "same_canvas" in reasons["identity"]


def test_human_false_match_label_reduces_future_identity_score(app, client, auth):
    from server.extensions import db
    from server.models import Link, Visit
    from server.utils import sign_visit_token

    auth.login()
    with app.app_context():
        link = Link(slug="false-match", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        prior = Visit(
            link_id=link.id,
            ip_address="1.1.1.1",
            email="same@example.com",
            canvas_hash="canvas-x",
            audio_fp="audio-x",
            review_label="false_match",
        )
        current = Visit(link_id=link.id, ip_address="1.1.1.2", email="same@example.com")
        db.session.add_all([prior, current])
        db.session.commit()
        visit_id = current.id

    response = client.post(
        "/api/beacon",
        json={
            "visit_id": visit_id,
            "visit_token": sign_visit_token(visit_id),
            "canvas_hash": "canvas-x",
            "audio_fp": "audio-x",
        },
    )
    assert response.status_code == 200

    with app.app_context():
        stored = db.session.get(Visit, visit_id)
        reasons = json.loads(stored.match_reasons_json)
        assert stored.identity_confidence < 50
        assert "human_marked_false_match" in reasons["conflicts"]
