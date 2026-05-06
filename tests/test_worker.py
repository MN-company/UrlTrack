import json


def test_send_telegram_text_falls_back_to_plain(monkeypatch):
    from server import worker

    calls = []

    class _Resp:
        def __init__(self, ok):
            self.ok = ok

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _Resp(ok=len(calls) > 1)

    monkeypatch.setattr(worker.requests, "post", fake_post)

    worker._send_telegram_text("token", "chat", r"👁 *Nuova visita* su `/slug\_1`")

    assert len(calls) == 2
    assert calls[0]["json"]["parse_mode"] == "MarkdownV2"
    assert "parse_mode" not in calls[1]["json"]
    assert "*" not in calls[1]["json"]["text"]
    assert "`" not in calls[1]["json"]["text"]
    assert "\\" not in calls[1]["json"]["text"]


def test_handle_task_preserves_existing_vpn_flags(app, monkeypatch):
    from server import worker
    from server.extensions import db
    from server.models import Link, Visit
    from server import utils as server_utils

    monkeypatch.setattr(server_utils, "get_geo_data", lambda ip: {"proxy": False, "hosting": False, "mobile": False})
    monkeypatch.setattr(server_utils, "get_reverse_dns", lambda ip: None)

    with app.app_context():
        link = Link(slug="vpn-link", destination="https://example.com")
        db.session.add(link)
        db.session.commit()

        visit = Visit(
            link_id=link.id,
            ip_address="1.1.1.1",
            is_vpn=True,
            is_proxy=True,
            is_hosting=True,
        )
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id

    worker._handle_task(app, {"type": "enrich_visit", "visit_id": visit_id, "ip": "1.1.1.1"})

    with app.app_context():
        updated = db.session.get(Visit, visit_id)
        assert updated.is_vpn is True
        assert updated.is_proxy is True
        assert updated.is_hosting is True
        assert updated.is_mobile is False


def test_enrich_visit_does_not_dispatch_telegram_until_complete(app, monkeypatch):
    from server import worker
    from server.extensions import db
    from server.models import Link, Visit
    from server import utils as server_utils

    monkeypatch.setattr(server_utils, "get_geo_data", lambda ip: {"proxy": False, "hosting": False, "mobile": False})
    monkeypatch.setattr(server_utils, "get_reverse_dns", lambda ip: None)

    dispatched = []
    monkeypatch.setattr(worker, "_dispatch_telegram", lambda app_obj, visit: dispatched.append(visit.id))

    with app.app_context():
        link = Link(slug="enrich-only", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        visit = Visit(link_id=link.id, ip_address="1.1.1.1", visit_complete=False)
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id

    worker._handle_task(app, {"type": "enrich_visit", "visit_id": visit_id, "ip": "1.1.1.1", "notify": False})

    assert dispatched == []


def test_mark_visit_complete_sets_flag_and_dispatches_telegram(app, monkeypatch):
    from server import worker
    from server.extensions import db
    from server.models import Link, Visit

    dispatched = []
    monkeypatch.setattr(worker, "_dispatch_telegram", lambda app_obj, visit: dispatched.append(visit.id))

    with app.app_context():
        link = Link(slug="complete", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        visit = Visit(link_id=link.id, ip_address="1.1.1.1", visit_complete=False)
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id

    worker._handle_task(app, {"type": "mark_visit_complete", "visit_id": visit_id})

    with app.app_context():
        updated = db.session.get(Visit, visit_id)
        assert updated.visit_complete is True
        assert updated.notification_sent_at is not None
    assert dispatched == [visit_id]


def test_dispatch_visit_missing_beacon_scores_risk_and_sends_once(app, monkeypatch):
    from server import worker
    from server.extensions import db
    from server.models import Link, Visit

    dispatched = []
    monkeypatch.setattr(worker, "_dispatch_telegram", lambda app_obj, visit: dispatched.append(visit.id))

    with app.app_context():
        link = Link(slug="fallback", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        visit = Visit(link_id=link.id, ip_address="1.1.1.1", visit_complete=False)
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id

    task = {"type": "dispatch_visit", "visit_id": visit_id, "missing_beacon": True}
    worker._handle_task(app, task)
    worker._handle_task(app, task)

    with app.app_context():
        updated = db.session.get(Visit, visit_id)
        reasons = json.loads(updated.match_reasons_json)
        assert updated.visit_complete is True
        assert updated.notification_sent_at is not None
        assert updated.risk_score == 15
        assert reasons["risk"] == ["missing_beacon"]
    assert dispatched == [visit_id]
