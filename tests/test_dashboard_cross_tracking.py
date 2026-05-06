from datetime import datetime


def test_timeline_filters_by_link_risk_review_and_beacon(app, client, auth):
    from server.extensions import db
    from server.models import Link, Visit

    auth.login()
    with app.app_context():
        alpha = Link(slug="alpha-filter", destination="https://example.com/a")
        beta = Link(slug="beta-filter", destination="https://example.com/b")
        db.session.add_all([alpha, beta])
        db.session.commit()

        expected = Visit(
            link_id=alpha.id,
            ip_address="1.1.1.1",
            email="wanted@example.com",
            risk_score=80,
            identity_confidence=55,
            review_label="suspicious",
            beacon_received_at=None,
        )
        wrong_link = Visit(
            link_id=beta.id,
            ip_address="2.2.2.2",
            email="wrong-link@example.com",
            risk_score=90,
            identity_confidence=80,
            review_label="suspicious",
            beacon_received_at=None,
        )
        wrong_risk = Visit(
            link_id=alpha.id,
            ip_address="3.3.3.3",
            email="wrong-risk@example.com",
            risk_score=10,
            identity_confidence=80,
            review_label="suspicious",
            beacon_received_at=None,
        )
        wrong_beacon = Visit(
            link_id=alpha.id,
            ip_address="4.4.4.4",
            email="wrong-beacon@example.com",
            risk_score=80,
            identity_confidence=80,
            review_label="suspicious",
            beacon_received_at=datetime.utcnow(),
        )
        db.session.add_all([expected, wrong_link, wrong_risk, wrong_beacon])
        db.session.commit()

    response = client.get(
        "/dashboard/timeline?slug=alpha-filter&risk_min=50&review_label=suspicious&beacon=missing"
    )
    assert response.status_code == 200
    assert b"wanted@example.com" in response.data
    assert b"wrong-link@example.com" not in response.data
    assert b"wrong-risk@example.com" not in response.data
    assert b"wrong-beacon@example.com" not in response.data


def test_timeline_signal_filter_finds_fingerprints_and_searches_composite(app, client, auth):
    from server.extensions import db
    from server.models import Link, Visit

    auth.login()
    with app.app_context():
        link = Link(slug="signal-filter", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        fingerprinted = Visit(
            link_id=link.id,
            ip_address="5.5.5.5",
            email="fingerprinted@example.com",
            fingerprint_composite_v1="composite-search-token",
        )
        anonymous = Visit(link_id=link.id, ip_address="6.6.6.6", email="anonymous@example.com")
        db.session.add_all([fingerprinted, anonymous])
        db.session.commit()

    signal_response = client.get("/dashboard/timeline?signal=fingerprint")
    assert signal_response.status_code == 200
    assert b"fingerprinted@example.com" in signal_response.data
    assert b"anonymous@example.com" not in signal_response.data

    search_response = client.get("/dashboard/timeline?q=composite-search-token")
    assert search_response.status_code == 200
    assert b"fingerprinted@example.com" in search_response.data


def test_cross_tracking_finds_shared_canvas_across_links(app, client, auth):
    from server.extensions import db
    from server.models import Link, Visit

    auth.login()
    with app.app_context():
        first = Link(slug="cross-a", destination="https://example.com/a")
        second = Link(slug="cross-b", destination="https://example.com/b")
        single = Link(slug="cross-single", destination="https://example.com/c")
        db.session.add_all([first, second, single])
        db.session.commit()

        db.session.add_all(
            [
                Visit(
                    link_id=first.id,
                    ip_address="7.7.7.1",
                    email="shared-a@example.com",
                    canvas_hash="shared-canvas",
                    identity_confidence=70,
                    risk_score=15,
                ),
                Visit(
                    link_id=second.id,
                    ip_address="7.7.7.2",
                    email="shared-b@example.com",
                    canvas_hash="shared-canvas",
                    identity_confidence=65,
                    risk_score=25,
                ),
                Visit(
                    link_id=single.id,
                    ip_address="8.8.8.8",
                    email="single@example.com",
                    canvas_hash="single-canvas",
                    identity_confidence=90,
                    risk_score=5,
                ),
            ]
        )
        db.session.commit()

    response = client.get("/dashboard/cross?group_by=canvas&min_links=2")
    assert response.status_code == 200
    assert b"shared-canvas" in response.data
    assert b"/cross-a" in response.data
    assert b"/cross-b" in response.data
    assert b"single-canvas" not in response.data


def test_cross_tracking_filters_by_min_risk(app, client, auth):
    from server.extensions import db
    from server.models import Link, Visit

    auth.login()
    with app.app_context():
        first = Link(slug="risk-a", destination="https://example.com/a")
        second = Link(slug="risk-b", destination="https://example.com/b")
        db.session.add_all([first, second])
        db.session.commit()
        db.session.add_all(
            [
                Visit(link_id=first.id, email="safe@example.com", risk_score=10),
                Visit(link_id=second.id, email="safe@example.com", risk_score=10),
                Visit(link_id=first.id, email="hot@example.com", risk_score=80),
                Visit(link_id=second.id, email="hot@example.com", risk_score=90),
            ]
        )
        db.session.commit()

    response = client.get("/dashboard/cross?group_by=email&risk_min=50&min_links=2")
    assert response.status_code == 200
    assert b"hot@example.com" in response.data
    assert b"safe@example.com" not in response.data
