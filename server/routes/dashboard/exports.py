import csv
import html
import json
from io import StringIO

from flask import Blueprint, g, make_response

from ...auth_middleware import workspace_required
from ...extensions import limiter
from ...models import Link, Visit


bp = Blueprint("dashboard_exports", __name__)


def _csv_safe(value) -> str:
    text = "" if value is None else str(value)
    if text[:1] in {"=", "+", "-", "@"}:
        return f"'{text}"
    return text


def _html_safe(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


@bp.route("/export/<slug>/json")
@workspace_required("analyst")
@limiter.limit("5 per minute")
def export_json(slug):
    link = Link.query.filter_by(slug=slug).first_or_404()
    visits = Visit.query.filter_by(link_id=link.id).order_by(Visit.timestamp.desc()).all()
    payload = {
        "link": {
            "slug": link.slug,
            "destination": link.destination,
            "created_at": link.created_at.isoformat(),
            "total_visits": len(visits),
        },
        "visits": [visit.to_dict() for visit in visits],
    }
    response = make_response(json.dumps(payload, indent=2, default=str))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = f"attachment; filename=stats_{slug}.json"
    return response


@bp.route("/export/<slug>/csv")
@workspace_required("analyst")
@limiter.limit("5 per minute")
def export_csv(slug):
    link = Link.query.filter_by(slug=slug).first_or_404()
    visits = Visit.query.filter_by(link_id=link.id).order_by(Visit.timestamp.desc()).all()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "ID",
            "Timestamp",
            "IP",
            "Hostname",
            "ISP",
            "Org",
            "City",
            "Country",
            "OS",
            "Device",
            "Screen",
            "Email",
            "Fingerprint",
            "ETag",
            "Suspicious",
            "Referrer",
        ]
    )

    for visit in visits:
        writer.writerow(
            [
                visit.id,
                visit.timestamp.isoformat(),
                _csv_safe(visit.ip_address),
                _csv_safe(visit.hostname),
                _csv_safe(visit.isp),
                _csv_safe(visit.org),
                _csv_safe(visit.city),
                _csv_safe(visit.country),
                _csv_safe(visit.os_family),
                _csv_safe(visit.device_type),
                _csv_safe(visit.screen_res),
                _csv_safe(visit.email),
                _csv_safe(visit.canvas_hash),
                _csv_safe(visit.etag),
                "yes" if visit.is_suspicious else "no",
                _csv_safe(visit.referrer),
            ]
        )

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f"attachment; filename={slug}_export.csv"
    return response


@bp.route("/export/<slug>/pdf")
@workspace_required("analyst")
@limiter.limit("5 per minute")
def export_pdf(slug):
    link = Link.query.filter_by(slug=slug).first_or_404()
    visits = Visit.query.filter_by(link_id=link.id).order_by(Visit.timestamp.desc()).limit(100).all()

    html = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>UrlTrack Report</title>",
        "<style>body{font-family:Arial,sans-serif;padding:24px;color:#111}table{width:100%;border-collapse:collapse;margin-top:16px}th,td{border:1px solid #ddd;padding:8px;font-size:12px;text-align:left}th{background:#111;color:#fff}</style>",
        "</head><body>",
        f"<h1>UrlTrack Report for /{_html_safe(link.slug)}</h1>",
        f"<p><strong>Destination:</strong> {_html_safe(link.destination)}</p>",
        f"<p><strong>Total visits:</strong> {Visit.query.filter_by(link_id=link.id).count()}</p>",
        "<table><thead><tr><th>Time</th><th>IP</th><th>Location</th><th>Device</th><th>Email</th></tr></thead><tbody>",
    ]

    for visit in visits:
        html.append(
            "<tr>"
            f"<td>{visit.timestamp:%Y-%m-%d %H:%M}</td>"
            f"<td>{_html_safe(visit.ip_address)}</td>"
            f"<td>{_html_safe(visit.city)}, {_html_safe(visit.country)}</td>"
            f"<td>{_html_safe(visit.os_family)} / {_html_safe(visit.device_type)}</td>"
            f"<td>{_html_safe(visit.email)}</td>"
            "</tr>"
        )

    html.append("</tbody></table></body></html>")
    response = make_response("".join(html))
    response.headers["Content-Type"] = "text/html"
    response.headers["Content-Disposition"] = f"attachment; filename={slug}_report.html"
    return response
