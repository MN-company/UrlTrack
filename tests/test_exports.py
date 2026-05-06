def test_csv_export_neutralizes_formula_values(app, client, auth):
    from server.extensions import db
    from server.models import Link, Visit

    auth.login()
    with app.app_context():
        link = Link(slug="export-safe", destination="https://example.com")
        db.session.add(link)
        db.session.commit()
        visit = Visit(
            link_id=link.id,
            ip_address="1.1.1.1",
            email="=cmd|calc@example.com",
            referrer="@malicious",
            city="+Rome",
            country="-IT",
        )
        db.session.add(visit)
        db.session.commit()

    response = client.get("/dashboard/export/export-safe/csv")
    assert response.status_code == 200
    body = response.data.decode()
    assert "'=cmd|calc@example.com" in body
    assert "'@malicious" in body
    assert "'+Rome" in body
    assert "'-IT" in body


def test_html_report_escapes_visit_values(app, client, auth):
    from server.extensions import db
    from server.models import Link, Visit

    auth.login()
    with app.app_context():
        link = Link(slug="html-safe", destination="https://example.com/?q=<script>")
        db.session.add(link)
        db.session.commit()
        visit = Visit(link_id=link.id, ip_address="1.1.1.1", email="<script>alert(1)</script>")
        db.session.add(visit)
        db.session.commit()

    response = client.get("/dashboard/export/html-safe/pdf")
    assert response.status_code == 200
    body = response.data.decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
