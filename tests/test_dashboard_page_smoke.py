def test_dashboard_primary_pages_render_after_ux_refresh(app, client, auth):
    from server.extensions import db
    from server.models import Lead, Link, Visit

    auth.login()
    with app.app_context():
        link = Link(slug="ux-smoke", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        visit = Visit(
            link_id=link.id,
            ip_address="9.9.9.9",
            email="ux@example.com",
            canvas_hash="ux-canvas",
            fingerprint_composite_v1="ux-composite",
            identity_confidence=70,
            risk_score=20,
        )
        lead = Lead(
            email="ux@example.com",
            primary_canvas_hash="ux-canvas",
            all_canvas_hashes='["ux-canvas"]',
            all_ips='["9.9.9.9"]',
            all_slugs_visited='["ux-smoke"]',
            total_visits=1,
        )
        db.session.add_all([visit, lead])
        db.session.commit()
        lead_id = lead.id

    pages = [
        "/dashboard",
        "/dashboard/links",
        "/dashboard/create_full",
        "/dashboard/edit/ux-smoke",
        "/dashboard/stats/ux-smoke",
        "/dashboard/timeline",
        "/dashboard/cross",
        "/dashboard/global-intel",
        "/dashboard/graph",
        "/dashboard/device/ux-canvas",
        "/dashboard/leads",
        f"/dashboard/leads/{lead_id}",
        "/dashboard/ai/console",
        "/dashboard/settings",
        "/dashboard/security",
        "/dashboard/search?q=ux",
        "/dashboard/qr_view/ux-smoke",
    ]

    for path in pages:
        response = client.get(path)
        assert response.status_code == 200, path
        assert b"app-topbar" in response.data, path
