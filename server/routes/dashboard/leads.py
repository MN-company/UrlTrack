import json

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ...extensions import db
from ...models import Lead
from ...utils import sanitize


bp = Blueprint("dashboard_leads", __name__)


def _json_list(value):
    if not value:
        return []
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


@bp.route("/leads")
@login_required
def leads_list():
    leads = Lead.query.order_by(Lead.last_seen.desc().nullslast(), Lead.updated_at.desc()).all()
    return render_template("leads.html", leads=leads)


@bp.route("/leads/<int:lead_id>")
@login_required
def lead_detail(lead_id):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        abort(404)
    return render_template(
        "lead_detail.html",
        lead=lead,
        canvas_hashes=_json_list(lead.all_canvas_hashes),
        ips=_json_list(lead.all_ips),
        slugs=_json_list(lead.all_slugs_visited),
    )


@bp.route("/leads/<int:lead_id>/update", methods=["POST"])
@login_required
def lead_update(lead_id):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        abort(404)
    lead.notes = sanitize(request.form.get("notes", ""), 2000)
    lead.label = sanitize(request.form.get("label", ""), 128)
    db.session.commit()
    flash("Lead updated.", "success")
    return redirect(url_for("dashboard.dashboard_leads.lead_detail", lead_id=lead_id))
