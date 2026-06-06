import json

from flask import Blueprint, Response, g, jsonify, redirect, render_template, request, stream_with_context, url_for

from ...auth_middleware import workspace_required

from ...config import Config
from ...models import Link, Visit
from ...services.ai_service import AIService


bp = Blueprint("dashboard_ai", __name__)


def _extract_message():
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        return (payload.get("message") or "").strip()
    return (request.form.get("message") or request.args.get("message") or "").strip()


@bp.route("/ai/console")
@workspace_required("analyst")
def ai_console():
    visits = Visit.query.filter_by(workspace_id=g.workspace.id)
    links = Link.query.filter_by(workspace_id=g.workspace.id)
    return render_template(
        "ai_console.html",
        model_name=Config.GEMINI_MODEL,
        total_visits=visits.count(),
        total_links=links.count(),
        identified_visits=visits.filter(Visit.email.isnot(None)).count(),
        high_risk_visits=visits.filter(Visit.risk_score >= 50).count(),
        unreviewed_high_risk=visits.filter(
            Visit.risk_score >= 50, Visit.review_label.is_(None)
        ).count(),
        reviewed_visits=visits.filter(Visit.review_label.isnot(None)).count(),
        recent_visits=visits.order_by(Visit.timestamp.desc()).limit(8).all(),
        initial_message=(request.args.get("message") or "").strip(),
    )


@bp.route("/ai/console/send", methods=["POST"])
@workspace_required("analyst")
def ai_console_send():
    message = _extract_message()
    if not message:
        return jsonify({"error": "No message provided."}), 400
    try:
        return jsonify(AIService.generate_response(message, g.workspace.id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"AI service error: {exc}"}), 500


@bp.route("/ai/console/stream", methods=["POST", "GET"])
@workspace_required("analyst")
def ai_console_stream():
    message = _extract_message()
    if not message:
        return jsonify({"error": "No message provided."}), 400

    def generate():
        yield f"data: {json.dumps({'type': 'meta', 'model': Config.GEMINI_MODEL})}\n\n"
        try:
            for chunk in AIService.generate_stream_response(message, g.workspace.id):
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@bp.route("/ai")
@workspace_required("analyst")
def ai_dashboard():
    return redirect(url_for("dashboard.dashboard_ai.ai_console"))
