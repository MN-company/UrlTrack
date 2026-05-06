def _create_link(app, **kwargs):
    from server.extensions import db
    from server.models import Link

    defaults = {
        "slug": "alpha",
        "destination": "https://example.com",
    }
    defaults.update(kwargs)

    with app.app_context():
        link = Link(**defaults)
        db.session.add(link)
        db.session.commit()
        return link.id


class _QueueRecorder:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def test_redirect_with_email_gate_enqueues_only_after_verify_email(app, client, monkeypatch):
    from server.models import Visit
    from server.routes import public as public_routes

    queue = _QueueRecorder()
    monkeypatch.setattr(public_routes, "log_queue", queue)
    monkeypatch.setattr(public_routes, "get_geo_data", lambda ip: {"countryCode": "IT"})
    monkeypatch.setattr(public_routes, "is_malicious_ip", lambda ip: False)

    link_id = _create_link(app, slug="mailgate", require_email=True)

    response = client.get("/mailgate")
    assert response.status_code == 200
    assert len(queue.items) == 1
    assert queue.items[0]["type"] == "enrich_visit"
    assert queue.items[0]["notify"] is False

    with app.app_context():
        visit = Visit.query.filter_by(link_id=link_id).order_by(Visit.id.desc()).first()
        visit_id = visit.id

    verify_response = client.post(
        "/verify_email",
        data={"slug": "mailgate", "visit_id": visit_id, "email": "user@example.com"},
        follow_redirects=False,
    )
    assert verify_response.status_code == 302
    assert len(queue.items) == 2
    assert queue.items[1]["type"] == "mark_visit_complete"
    assert queue.items[1]["visit_id"] == visit_id


def test_verify_email_backfills_same_canvas_hash(app, client, monkeypatch):
    from server.extensions import db
    from server.models import Link, Visit
    from server.routes import public as public_routes

    monkeypatch.setattr(public_routes, "log_queue", _QueueRecorder())

    with app.app_context():
        link = Link(slug="ghost", destination="https://example.com")
        db.session.add(link)
        db.session.commit()

        old_visit = Visit(link_id=link.id, ip_address="1.1.1.1", canvas_hash="same-hash")
        new_visit = Visit(link_id=link.id, ip_address="1.1.1.2", canvas_hash="same-hash")
        db.session.add_all([old_visit, new_visit])
        db.session.commit()
        old_visit_id = old_visit.id
        new_visit_id = new_visit.id

    response = client.post(
        "/verify_email",
        data={"slug": "ghost", "visit_id": new_visit_id, "email": "ghost@example.com"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        updated_old = db.session.get(Visit, old_visit_id)
        updated_new = db.session.get(Visit, new_visit_id)
        assert updated_new.email == "ghost@example.com"
        assert updated_old.email == "ghost@example.com"


def test_public_gate_invalid_visit_id_does_not_500(app, client, monkeypatch):
    from server.routes import public as public_routes

    monkeypatch.setattr(public_routes, "log_queue", _QueueRecorder())
    _create_link(app, slug="bad-visit", require_email=True)

    email_response = client.post(
        "/verify_email",
        data={"slug": "bad-visit", "visit_id": "not-an-int", "email": "valid@example.com"},
        follow_redirects=False,
    )
    assert email_response.status_code == 302

    password_response = client.post(
        "/verify_password",
        data={"slug": "bad-visit", "visit_id": "not-an-int", "password": "wrong"},
        follow_redirects=False,
    )
    assert password_response.status_code == 401


def test_redirect_geo_allowlist_fail_closed_marks_visit(app, client, monkeypatch):
    from server.models import Visit
    from server.routes import public as public_routes

    queue = _QueueRecorder()
    monkeypatch.setattr(public_routes, "log_queue", queue)
    monkeypatch.setattr(public_routes, "get_geo_data", lambda ip: {})
    monkeypatch.setattr(public_routes, "is_malicious_ip", lambda ip: False)

    link_id = _create_link(app, slug="geo", allowed_countries="IT")

    response = client.get("/geo")
    assert response.status_code == 403
    assert b"Unable to verify your location." in response.data
    assert len(queue.items) == 1
    assert queue.items[0]["type"] == "enrich_visit"
    assert queue.items[0]["notify"] is False

    with app.app_context():
        visit = Visit.query.filter_by(link_id=link_id).order_by(Visit.id.desc()).first()
        assert visit.is_suspicious is True
        assert visit.notes == "Blocked: geo lookup failed"


def test_block_bots_does_not_block_cloud_visitor_without_block_vpn(app, client, monkeypatch):
    from server.routes import public as public_routes

    queue = _QueueRecorder()
    monkeypatch.setattr(public_routes, "log_queue", queue)
    monkeypatch.setattr(
        public_routes,
        "get_geo_data",
        lambda ip: {"countryCode": "IT", "org": "Amazon AWS", "isp": "Amazon"},
    )
    monkeypatch.setattr(public_routes, "is_malicious_ip", lambda ip: False)

    _create_link(app, slug="cloud-ok", block_bots=True, block_vpn=False)

    response = client.get("/cloud-ok")
    assert response.status_code == 200
    assert len(queue.items) == 2
    assert queue.items[0]["type"] == "enrich_visit"
    assert queue.items[0]["notify"] is False
    assert queue.items[1]["type"] == "dispatch_visit_after_timeout"
