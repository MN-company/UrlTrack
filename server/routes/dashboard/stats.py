from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func

from ...extensions import db
from ...models import Link, Visit
from ...utils import sanitize


bp = Blueprint("dashboard_stats", __name__)


@bp.route("/search")
@login_required
def global_search():
    query = sanitize(request.args.get("q"), 255)
    if not query:
        flash("Please enter a search term.", "warning")
        return redirect(url_for("dashboard.dashboard_stats.global_timeline"))

    search_term = f"%{query}%"
    visits = (
        Visit.query.filter(
            db.or_(
                Visit.ip_address.ilike(search_term),
                Visit.email.ilike(search_term),
                Visit.hostname.ilike(search_term),
                Visit.org.ilike(search_term),
                Visit.city.ilike(search_term),
                Visit.country.ilike(search_term),
                Visit.canvas_hash.ilike(search_term),
                Visit.webgl_renderer.ilike(search_term),
                Visit.etag.ilike(search_term),
            )
        )
        .order_by(Visit.timestamp.desc())
        .limit(100)
        .all()
    )
    links = (
        Link.query.filter(
            db.or_(
                Link.slug.ilike(search_term),
                Link.destination.ilike(search_term),
                Link.public_masked_url.ilike(search_term),
            )
        )
        .limit(50)
        .all()
    )
    return render_template("search_results.html", q=query, visits=visits, links=links)


@bp.route("/timeline")
@login_required
def global_timeline():
    query = sanitize(request.args.get("q"), 255)
    country = sanitize(request.args.get("country"), 64)
    device = sanitize(request.args.get("device"), 64)
    days = int(sanitize(request.args.get("days"), 3) or 7)

    visit_query = Visit.query
    if days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        visit_query = visit_query.filter(Visit.timestamp >= cutoff)
    if query:
        search_term = f"%{query}%"
        visit_query = visit_query.filter(
            db.or_(
                Visit.ip_address.ilike(search_term),
                Visit.email.ilike(search_term),
                Visit.hostname.ilike(search_term),
                Visit.org.ilike(search_term),
                Visit.city.ilike(search_term),
                Visit.country.ilike(search_term),
                Visit.canvas_hash.ilike(search_term),
                Visit.etag.ilike(search_term),
            )
        )
    if country:
        visit_query = visit_query.filter(Visit.country == country)
    if device:
        visit_query = visit_query.filter(Visit.device_type == device)

    visits = visit_query.order_by(Visit.timestamp.desc()).limit(200).all()
    countries = [value for (value,) in db.session.query(Visit.country).distinct().all() if value]
    devices = [value for (value,) in db.session.query(Visit.device_type).distinct().all() if value]
    return render_template(
        "timeline.html",
        visits=visits,
        q=query,
        country=country,
        device=device,
        days=days,
        countries=countries,
        devices=devices,
    )


@bp.route("/stats/<slug>")
@login_required
def stats(slug: str):
    link = Link.query.filter_by(slug=slug).first_or_404()
    visits = Visit.query.filter_by(link_id=link.id).order_by(Visit.timestamp.desc()).all()

    now = datetime.utcnow()
    dates = [(now - timedelta(days=index)).strftime("%Y-%m-%d") for index in range(6, -1, -1)]
    clicks_map = defaultdict(int)
    for visit in visits:
        clicks_map[visit.timestamp.strftime("%Y-%m-%d")] += 1
    chart_values = [clicks_map[day] for day in dates]

    top_countries = (
        db.session.query(Visit.country, Visit.country_code, func.count(Visit.id))
        .filter(Visit.link_id == link.id)
        .group_by(Visit.country, Visit.country_code)
        .order_by(func.count(Visit.id).desc())
        .limit(5)
        .all()
    )
    top_referrers = (
        db.session.query(Visit.referrer, func.count(Visit.id))
        .filter(Visit.link_id == link.id)
        .group_by(Visit.referrer)
        .order_by(func.count(Visit.id).desc())
        .limit(5)
        .all()
    )

    ip_addresses = {visit.ip_address for visit in visits if visit.ip_address}
    cross_link_data = {}
    if ip_addresses:
        cross_visits = Visit.query.filter(Visit.ip_address.in_(ip_addresses), Visit.link_id != link.id).all()
        for cross_visit in cross_visits:
            cross_link_data.setdefault(cross_visit.ip_address, [])
            if cross_visit.link.slug not in [item["slug"] for item in cross_link_data[cross_visit.ip_address]]:
                cross_link_data[cross_visit.ip_address].append(
                    {
                        "slug": cross_visit.link.slug,
                        "timestamp": cross_visit.timestamp,
                        "email": cross_visit.email,
                    }
                )

    return render_template(
        "stats.html",
        link=link,
        visits=visits[:100],
        chart_labels=dates,
        chart_values=chart_values,
        top_countries=top_countries,
        top_referrers=top_referrers,
        cross_link_data=cross_link_data,
    )


@bp.route("/device/<fingerprint>")
@login_required
def device_profile(fingerprint: str):
    visits = (
        Visit.query.filter(
            db.or_(
                Visit.canvas_hash == fingerprint,
                Visit.etag == fingerprint,
            )
        )
        .order_by(Visit.timestamp.desc())
        .all()
    )
    if not visits:
        flash("No device found with that fingerprint.", "error")
        return redirect(url_for("dashboard.dashboard_links.dashboard_home"))

    emails = sorted({visit.email for visit in visits if visit.email})
    ips = sorted({visit.ip_address for visit in visits if visit.ip_address})
    links_visited = sorted({visit.link.slug for visit in visits if visit.link})
    countries = sorted({visit.country for visit in visits if visit.country})
    devices = sorted({f"{visit.os_family or 'Unknown'} / {visit.device_type or 'Unknown'}" for visit in visits})
    primary_email = emails[0] if emails else None
    ai_summary = next((visit.ai_summary for visit in visits if visit.ai_summary), None)
    webgl = next((visit.webgl_renderer for visit in visits if visit.webgl_renderer), None)

    return render_template(
        "device_profile.html",
        fingerprint=fingerprint,
        visits=visits[:50],
        emails=emails,
        ips=ips,
        links_visited=links_visited,
        countries=countries,
        devices=devices,
        primary_email=primary_email,
        ai_summary=ai_summary,
        webgl=webgl,
        total_visits=len(visits),
    )
