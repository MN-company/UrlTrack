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
