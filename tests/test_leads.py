def test_enrich_visit_upserts_lead(app, monkeypatch):
    from server import worker
    from server.extensions import db
    from server.models import Lead, Link, Visit
    from server import utils as server_utils

    monkeypatch.setattr(server_utils, "get_geo_data", lambda ip: {"proxy": False, "hosting": False, "mobile": False})
    monkeypatch.setattr(server_utils, "get_reverse_dns", lambda ip: None)
    monkeypatch.setattr(worker, "_dispatch_telegram", lambda app_obj, visit: None)

    with app.app_context():
        link = Link(slug="lead-a", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        visit = Visit(
            link_id=link.id,
            ip_address="1.1.1.1",
            canvas_hash="hash-1",
            email="lead@example.com",
            device_type="Desktop",
            os_family="Mac OS X",
        )
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id

    worker._handle_task(app, {"type": "enrich_visit", "visit_id": visit_id, "ip": "1.1.1.1", "notify": False})

    with app.app_context():
        lead = Lead.query.filter_by(email="lead@example.com").first()
        assert lead is not None
        assert lead.primary_canvas_hash == "hash-1"
        assert lead.total_visits == 1


def test_lead_upsert_does_not_match_canvas_substrings(app, monkeypatch):
    from server import worker
    from server.extensions import db
    from server.models import Lead, Link, Visit
    from server import utils as server_utils

    monkeypatch.setattr(server_utils, "get_geo_data", lambda ip: {"proxy": False, "hosting": False, "mobile": False})
    monkeypatch.setattr(server_utils, "get_reverse_dns", lambda ip: None)
    monkeypatch.setattr(worker, "_dispatch_telegram", lambda app_obj, visit: None)

    with app.app_context():
        link = Link(slug="lead-substring", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        existing = Lead(
            primary_canvas_hash="xabcx",
            all_canvas_hashes='["xabcx"]',
            total_visits=1,
        )
        visit = Visit(link_id=link.id, ip_address="1.1.1.1", canvas_hash="abc")
        db.session.add_all([existing, visit])
        db.session.commit()
        visit_id = visit.id
        existing_id = existing.id

    worker._handle_task(app, {"type": "enrich_visit", "visit_id": visit_id, "ip": "1.1.1.1", "notify": False})

    with app.app_context():
        existing = db.session.get(Lead, existing_id)
        created = Lead.query.filter_by(primary_canvas_hash="abc").first()
        assert existing.total_visits == 1
        assert created is not None
        assert created.id != existing_id


def test_leads_dashboard_detail_and_update(app, client, auth):
    from server.extensions import db
    from server.models import Lead

    auth.login()
    with app.app_context():
        lead = Lead(
            email="lead@example.com",
            primary_canvas_hash="hash-1",
            all_canvas_hashes='["hash-1"]',
            all_ips='["1.1.1.1"]',
            all_slugs_visited='["alpha"]',
            total_visits=2,
        )
        db.session.add(lead)
        db.session.commit()
        lead_id = lead.id

    list_response = client.get("/dashboard/leads")
    assert list_response.status_code == 200
    assert b"lead@example.com" in list_response.data

    detail_response = client.get(f"/dashboard/leads/{lead_id}")
    assert detail_response.status_code == 200
    assert b"hash-1" in detail_response.data

    update_response = client.post(
        f"/dashboard/leads/{lead_id}/update",
        data={"label": "hot", "notes": "Important lead"},
        follow_redirects=True,
    )
    assert update_response.status_code == 200

    with app.app_context():
        updated = db.session.get(Lead, lead_id)
        assert updated.label == "hot"
        assert updated.notes == "Important lead"


def test_visit_review_labels_visit_and_updates_score(app, client, auth):
    from server.extensions import db
    from server.models import Link, Visit

    auth.login()
    with app.app_context():
        link = Link(slug="review-a", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        visit = Visit(
            link_id=link.id,
            ip_address="1.1.1.1",
            canvas_hash="review-hash",
            beacon_received_at=None,
        )
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id

    response = client.post(
        f"/dashboard/visits/{visit_id}/review",
        data={"review_label": "suspicious", "review_note": "manual review"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        updated = db.session.get(Visit, visit_id)
        assert updated.review_label == "suspicious"
        assert updated.review_note == "manual review"
        assert updated.reviewed_at is not None
        assert updated.risk_score >= 30
        assert "human_marked_suspicious" in updated.match_reasons_json
