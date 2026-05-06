import json
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import Link, Visit
from ...utils import safe_json, sanitize


bp = Blueprint("dashboard_stats", __name__)


def _safe_int(value, default: int, min_value: int = 0, max_value: int = 10_000) -> int:
    try:
        parsed = int(sanitize(value, 8) or default)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(parsed, max_value))


def _visit_search_filter(search_term: str):
    return db.or_(
        Visit.ip_address.ilike(search_term),
        Visit.email.ilike(search_term),
        Visit.hostname.ilike(search_term),
        Visit.org.ilike(search_term),
        Visit.city.ilike(search_term),
        Visit.country.ilike(search_term),
        Visit.canvas_hash.ilike(search_term),
        Visit.audio_fp.ilike(search_term),
        Visit.webgl_renderer.ilike(search_term),
        Visit.webgl_vendor.ilike(search_term),
        Visit.fingerprint_composite_v1.ilike(search_term),
        Visit.etag.ilike(search_term),
        Visit.review_label.ilike(search_term),
        Visit.match_reasons_json.ilike(search_term),
    )


def _apply_visit_filters(visit_query, filters: dict):
    days = filters.get("days", 7)
    if days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        visit_query = visit_query.filter(Visit.timestamp >= cutoff)

    if filters.get("q"):
        visit_query = visit_query.filter(_visit_search_filter(f"%{filters['q']}%"))
    if filters.get("country"):
        visit_query = visit_query.filter(Visit.country == filters["country"])
    if filters.get("device"):
        visit_query = visit_query.filter(Visit.device_type == filters["device"])
    if filters.get("slug"):
        visit_query = visit_query.filter(Visit.link.has(Link.slug == filters["slug"]))

    risk_min = filters.get("risk_min", 0)
    if risk_min > 0:
        visit_query = visit_query.filter(Visit.risk_score.isnot(None), Visit.risk_score >= risk_min)

    identity_min = filters.get("identity_min", 0)
    if identity_min > 0:
        visit_query = visit_query.filter(
            Visit.identity_confidence.isnot(None),
            Visit.identity_confidence >= identity_min,
        )

    beacon = filters.get("beacon", "all")
    if beacon == "received":
        visit_query = visit_query.filter(Visit.beacon_received_at.isnot(None))
    elif beacon == "missing":
        visit_query = visit_query.filter(Visit.beacon_received_at.is_(None))

    review_label = filters.get("review_label", "")
    if review_label == "__none":
        visit_query = visit_query.filter(Visit.review_label.is_(None))
    elif review_label:
        visit_query = visit_query.filter(Visit.review_label == review_label)

    signal = filters.get("signal", "all")
    if signal == "vpn":
        visit_query = visit_query.filter(
            db.or_(Visit.is_vpn.is_(True), Visit.is_proxy.is_(True), Visit.is_hosting.is_(True))
        )
    elif signal == "bot":
        visit_query = visit_query.filter(Visit.browser_bot.is_(True))
    elif signal == "adblock":
        visit_query = visit_query.filter(
            db.or_(Visit.adblock.is_(True), Visit.extensions_detected.ilike("%adblock%"))
        )
    elif signal == "conflict":
        visit_query = visit_query.filter(
            db.or_(Visit.cluster_conflict.is_(True), Visit.conflict_reason.isnot(None))
        )
    elif signal == "email":
        visit_query = visit_query.filter(Visit.email.isnot(None), Visit.email != "")
    elif signal == "fingerprint":
        visit_query = visit_query.filter(
            db.or_(
                Visit.fingerprint_composite_v1.isnot(None),
                Visit.canvas_hash.isnot(None),
                Visit.etag.isnot(None),
            )
        )
    elif signal == "missing_beacon":
        visit_query = visit_query.filter(Visit.beacon_received_at.is_(None))

    return visit_query


def _visit_sort(visit_query, sort: str):
    if sort == "risk":
        return visit_query.order_by(Visit.risk_score.desc().nullslast(), Visit.timestamp.desc())
    if sort == "identity":
        return visit_query.order_by(Visit.identity_confidence.desc().nullslast(), Visit.timestamp.desc())
    return visit_query.order_by(Visit.timestamp.desc())


@bp.route("/search")
@login_required
def global_search():
    query = sanitize(request.args.get("q"), 255)
    if not query:
        flash("Please enter a search term.", "warning")
        return redirect(url_for("dashboard.dashboard_stats.global_timeline"))

    search_term = f"%{query}%"
    visits = (
        Visit.query.filter(_visit_search_filter(search_term))
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
    filters = {
        "q": sanitize(request.args.get("q"), 255),
        "country": sanitize(request.args.get("country"), 64),
        "device": sanitize(request.args.get("device"), 64),
        "slug": sanitize(request.args.get("slug"), 80),
        "days": _safe_int(request.args.get("days"), 7, min_value=0, max_value=3650),
        "risk_min": _safe_int(request.args.get("risk_min"), 0, min_value=0, max_value=100),
        "identity_min": _safe_int(request.args.get("identity_min"), 0, min_value=0, max_value=100),
        "beacon": sanitize(request.args.get("beacon"), 16) or "all",
        "review_label": sanitize(request.args.get("review_label"), 32),
        "signal": sanitize(request.args.get("signal"), 32) or "all",
        "sort": sanitize(request.args.get("sort"), 16) or "newest",
    }
    if filters["beacon"] not in {"all", "received", "missing"}:
        filters["beacon"] = "all"
    if filters["signal"] not in {
        "all",
        "vpn",
        "bot",
        "adblock",
        "conflict",
        "email",
        "fingerprint",
        "missing_beacon",
    }:
        filters["signal"] = "all"
    if filters["sort"] not in {"newest", "risk", "identity"}:
        filters["sort"] = "newest"

    visit_query = _apply_visit_filters(Visit.query.options(joinedload(Visit.link)), filters)
    visits = _visit_sort(visit_query, filters["sort"]).limit(200).all()
    countries = [value for (value,) in db.session.query(Visit.country).distinct().all() if value]
    devices = [value for (value,) in db.session.query(Visit.device_type).distinct().all() if value]
    slugs = [value for (value,) in db.session.query(Link.slug).order_by(Link.slug.asc()).all() if value]
    review_labels = [
        value for (value,) in db.session.query(Visit.review_label).distinct().all() if value
    ]
    return render_template(
        "timeline.html",
        visits=visits,
        filters=filters,
        q=filters["q"],
        country=filters["country"],
        device=filters["device"],
        days=filters["days"],
        countries=countries,
        devices=devices,
        slugs=slugs,
        review_labels=sorted(review_labels),
    )


@bp.route("/stats/<slug>")
@login_required
def stats(slug: str):
    link = Link.query.filter_by(slug=slug).first_or_404()
    visits = Visit.query.filter_by(link_id=link.id).order_by(Visit.timestamp.desc()).all()
    avg_dwell_ms = (
        db.session.query(func.avg(Visit.dwell_ms))
        .filter(Visit.link_id == link.id, Visit.dwell_ms.isnot(None))
        .scalar()
    )
    engaged_count = (
        db.session.query(func.count(Visit.id))
        .filter(Visit.link_id == link.id, Visit.dwell_ms.isnot(None), Visit.dwell_ms > 5000)
        .scalar()
        or 0
    )

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
        avg_dwell_ms=float(avg_dwell_ms) if avg_dwell_ms is not None else None,
        engaged_count=engaged_count,
    )


@bp.route("/device/<fingerprint>")
@login_required
def device_profile(fingerprint: str):
    visits = (
        Visit.query.filter(
            db.or_(
                Visit.canvas_hash == fingerprint,
                Visit.etag == fingerprint,
                Visit.fingerprint_composite_v1 == fingerprint,
                Visit.audio_fp == fingerprint,
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
    visit_details = []
    for visit in visits[:50]:
        fonts = [font for font in (visit.fonts or "").split(",") if font]
        webrtc_ips = safe_json(visit.webrtc_ips, []) or []
        if not isinstance(webrtc_ips, list):
            webrtc_ips = []
        extensions = safe_json(visit.extensions_detected, []) or []
        if not isinstance(extensions, list):
            extensions = []
        real_ip_detected = any(
            ip and ip != (visit.ip_address or "")
            for ip in webrtc_ips
        )
        visit_details.append(
            {
                "visit": visit,
                "fonts": fonts,
                "font_count": len(fonts),
                "webrtc_ips": webrtc_ips,
                "extensions": extensions,
                "real_ip_detected": real_ip_detected,
            }
        )

    return render_template(
        "device_profile.html",
        fingerprint=fingerprint,
        visits=visits[:50],
        visit_details=visit_details,
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


@bp.route("/cross")
@login_required
def cross_tracking():
    group_by = sanitize(request.args.get("group_by"), 32) or "email"
    groups = {
        "email": {
            "label": "Email",
            "column": Visit.email,
            "node_prefix": "email",
        },
        "canvas": {
            "label": "Canvas hash",
            "column": Visit.canvas_hash,
            "node_prefix": "hash",
        },
        "composite": {
            "label": "Composite fingerprint",
            "column": Visit.fingerprint_composite_v1,
            "node_prefix": "composite",
        },
        "ip": {
            "label": "IP address",
            "column": Visit.ip_address,
            "node_prefix": "ip",
        },
        "etag": {
            "label": "ETag",
            "column": Visit.etag,
            "node_prefix": "etag",
        },
    }
    if group_by not in groups:
        group_by = "email"

    days = _safe_int(request.args.get("days"), 30, min_value=0, max_value=3650)
    min_links = _safe_int(request.args.get("min_links"), 2, min_value=1, max_value=100)
    risk_min = _safe_int(request.args.get("risk_min"), 0, min_value=0, max_value=100)
    identity_min = _safe_int(request.args.get("identity_min"), 0, min_value=0, max_value=100)
    query = sanitize(request.args.get("q"), 255)
    column = groups[group_by]["column"]

    base_filters = [column.isnot(None), column != ""]
    if days > 0:
        base_filters.append(Visit.timestamp >= datetime.utcnow() - timedelta(days=days))
    if risk_min > 0:
        base_filters.extend([Visit.risk_score.isnot(None), Visit.risk_score >= risk_min])
    if identity_min > 0:
        base_filters.extend([Visit.identity_confidence.isnot(None), Visit.identity_confidence >= identity_min])
    if query:
        base_filters.append(column.ilike(f"%{query}%"))

    rows = (
        db.session.query(
            column.label("identifier"),
            func.count(Visit.id).label("visit_count"),
            func.count(func.distinct(Visit.link_id)).label("link_count"),
            func.avg(Visit.identity_confidence).label("avg_identity"),
            func.avg(Visit.risk_score).label("avg_risk"),
            func.max(Visit.timestamp).label("last_seen"),
        )
        .filter(*base_filters)
        .group_by(column)
        .having(func.count(func.distinct(Visit.link_id)) >= min_links)
        .order_by(func.count(func.distinct(Visit.link_id)).desc(), func.count(Visit.id).desc())
        .limit(100)
        .all()
    )

    identities = []
    for row in rows:
        related_visits = (
            Visit.query.options(joinedload(Visit.link))
            .filter(*base_filters, column == row.identifier)
            .order_by(Visit.timestamp.desc())
            .limit(12)
            .all()
        )
        slugs = sorted({visit.link.slug for visit in related_visits if visit.link})
        emails = sorted({visit.email for visit in related_visits if visit.email})
        countries = sorted({visit.country for visit in related_visits if visit.country})
        identities.append(
            {
                "identifier": row.identifier,
                "short_identifier": row.identifier[:18] + "..." if len(row.identifier) > 22 else row.identifier,
                "visit_count": row.visit_count,
                "link_count": row.link_count,
                "avg_identity": int(row.avg_identity or 0),
                "avg_risk": int(row.avg_risk or 0),
                "last_seen": row.last_seen,
                "slugs": slugs,
                "emails": emails,
                "countries": countries,
                "visits": related_visits,
                "profile_url": url_for(
                    "dashboard.dashboard_stats.device_profile",
                    fingerprint=row.identifier,
                )
                if group_by in {"canvas", "composite", "etag"}
                else url_for("dashboard.dashboard_stats.global_timeline", q=row.identifier),
            }
        )

    return render_template(
        "cross_tracking.html",
        identities=identities,
        group_by=group_by,
        groups=groups,
        days=days,
        min_links=min_links,
        risk_min=risk_min,
        identity_min=identity_min,
        q=query,
    )


@bp.route("/graph")
@login_required
def graph():
    visits = (
        Visit.query.options(joinedload(Visit.link))
        .filter(
            db.or_(
                Visit.canvas_hash.isnot(None),
                Visit.fingerprint_composite_v1.isnot(None),
                Visit.etag.isnot(None),
                Visit.email.isnot(None),
                Visit.ip_address.isnot(None),
            )
        )
        .order_by(Visit.timestamp.desc())
        .all()
    )

    nodes = {}
    edge_weights = defaultdict(int)

    for visit in visits:
        if not visit.link:
            continue

        slug_value = visit.link.slug
        slug_id = f"slug:{slug_value}"
        nodes[slug_id] = {
            "id": slug_id,
            "type": "slug",
            "label": slug_value,
            "url": url_for("dashboard.dashboard_stats.stats", slug=slug_value),
        }

        signal_nodes = []
        signal_values = [
            ("hash", visit.canvas_hash, visit.canvas_hash),
            ("composite", visit.fingerprint_composite_v1, visit.fingerprint_composite_v1),
            ("etag", visit.etag, visit.etag),
            ("ip", visit.ip_address, None),
        ]
        for signal_type, signal_value, profile_fingerprint in signal_values:
            if not signal_value:
                continue
            signal_id = f"{signal_type}:{signal_value}"
            nodes[signal_id] = {
                "id": signal_id,
                "type": signal_type,
                "label": signal_value[:10] if signal_type != "ip" else signal_value,
                "url": (
                    url_for("dashboard.dashboard_stats.device_profile", fingerprint=profile_fingerprint)
                    if profile_fingerprint
                    else url_for("dashboard.dashboard_stats.global_timeline", q=signal_value)
                ),
            }
            edge_weights[(signal_id, slug_id)] += 1
            signal_nodes.append(signal_id)

        if visit.email:
            email_value = visit.email
            email_id = f"email:{email_value}"
            nodes[email_id] = {
                "id": email_id,
                "type": "email",
                "label": email_value,
                "url": url_for("dashboard.dashboard_stats.global_search", q=email_value),
            }
            edge_weights[(email_id, slug_id)] += 1
            for signal_id in signal_nodes:
                edge_weights[(signal_id, email_id)] += 1

    degrees = defaultdict(int)
    for (source, target), weight in edge_weights.items():
        degrees[source] += weight
        degrees[target] += weight

    top_node_ids = {
        node_id
        for node_id, _degree in sorted(
            degrees.items(),
            key=lambda item: (-item[1], item[0]),
        )[:500]
    }

    filtered_nodes = [node for node_id, node in nodes.items() if node_id in top_node_ids]
    filtered_links = [
        {"source": source, "target": target, "weight": weight}
        for (source, target), weight in edge_weights.items()
        if source in top_node_ids and target in top_node_ids
    ]

    graph_data = json.dumps({"nodes": filtered_nodes, "links": filtered_links})
    return render_template("graph.html", graph_data=graph_data)
