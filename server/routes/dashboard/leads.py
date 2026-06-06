import json
from datetime import datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ...auth_middleware import workspace_required

from ...extensions import db
from ...models import Lead, Visit
from ...services.scoring import apply_visit_scoring
from ...utils import sanitize


bp = Blueprint("dashboard_leads", __name__)

VISIT_REVIEW_LABELS = {
    "same_user",
    "false_match",
    "bot",
    "clean",
    "suspicious",
    "important",
}


def _json_list(value):
    if not value:
        return []
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _lead_visits(lead: Lead, limit: int = 100):
    filters = []
    canvas_hashes = _json_list(lead.all_canvas_hashes)
    ips = _json_list(lead.all_ips)
    if lead.email:
        filters.append(Visit.email == lead.email)
    if canvas_hashes:
        filters.append(Visit.canvas_hash.in_(canvas_hashes))
    if ips:
        filters.append(Visit.ip_address.in_(ips))
    if not filters:
        return []
    return (
        Visit.query.filter(Visit.workspace_id == lead.workspace_id, db.or_(*filters))
        .order_by(Visit.timestamp.desc())
        .limit(limit)
        .all()
    )


def _avg(values):
    values = [value for value in values if isinstance(value, int)]
    if not values:
        return None
    return round(sum(values) / len(values))


def _reason_json(visit: Visit):
    try:
        data = json.loads(visit.match_reasons_json or "{}")
    except (TypeError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


@bp.route("/leads")
@workspace_required("analyst")
def leads_list():
    leads = Lead.query.filter_by(workspace_id=g.workspace.id).order_by(Lead.last_seen.desc().nullslast(), Lead.updated_at.desc()).all()
    lead_cards = []
    for lead in leads:
        visits = _lead_visits(lead, limit=30)
        avg_identity = _avg([visit.identity_confidence for visit in visits])
        avg_risk = _avg([visit.risk_score for visit in visits])
        reviewed_count = len([visit for visit in visits if visit.review_label])
        lead_cards.append(
            {
                "lead": lead,
                "avg_identity": avg_identity,
                "avg_risk": avg_risk,
                "reviewed_count": reviewed_count,
                "open_review_count": max(0, len(visits) - reviewed_count),
            }
        )
    return render_template("leads.html", lead_cards=lead_cards)


@bp.route("/leads/<int:lead_id>")
@workspace_required("analyst")
def lead_detail(lead_id):
    lead = Lead.query.filter_by(id=lead_id, workspace_id=g.workspace.id).first()
    if not lead:
        abort(404)
    visits = _lead_visits(lead)
    avg_identity = _avg([visit.identity_confidence for visit in visits])
    avg_risk = _avg([visit.risk_score for visit in visits])
    return render_template(
        "lead_detail.html",
        lead=lead,
        canvas_hashes=_json_list(lead.all_canvas_hashes),
        ips=_json_list(lead.all_ips),
        slugs=_json_list(lead.all_slugs_visited),
        visits=visits,
        avg_identity=avg_identity,
        avg_risk=avg_risk,
        reason_json=_reason_json,
        review_labels=sorted(VISIT_REVIEW_LABELS),
    )


@bp.route("/leads/<int:lead_id>/update", methods=["POST"])
@workspace_required("editor")
def lead_update(lead_id):
    lead = Lead.query.filter_by(id=lead_id, workspace_id=g.workspace.id).first()
    if not lead:
        abort(404)
    lead.notes = sanitize(request.form.get("notes", ""), 2000)
    lead.label = sanitize(request.form.get("label", ""), 128)
    db.session.commit()
    flash("Lead updated.", "success")
    return redirect(url_for("dashboard.dashboard_leads.lead_detail", lead_id=lead_id))


@bp.route("/visits/<int:visit_id>/review", methods=["POST"])
@workspace_required("editor")
def visit_review(visit_id):
    visit = Visit.query.filter_by(id=visit_id, workspace_id=g.workspace.id).first()
    if not visit:
        abort(404)
    label = sanitize(request.form.get("review_label"), 32)
    if label and label not in VISIT_REVIEW_LABELS:
        flash("Invalid review label.", "error")
        return redirect(request.referrer or url_for("dashboard.dashboard_stats.global_timeline"))

    visit.review_label = label or None
    visit.review_note = sanitize(request.form.get("review_note", ""), 1000) or None
    visit.reviewed_at = datetime.utcnow() if visit.review_label else None
    apply_visit_scoring(visit, missing_beacon=not bool(visit.beacon_received_at))
    db.session.commit()
    flash("Visit review saved. Future matches can use this human feedback.", "success")
    return redirect(request.referrer or url_for("dashboard.dashboard_stats.global_timeline"))
