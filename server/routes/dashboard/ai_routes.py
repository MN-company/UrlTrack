import json

from flask import Blueprint, Response, jsonify, redirect, render_template, request, stream_with_context, url_for
from flask_login import login_required

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
@login_required
def ai_console():
    return render_template(
        "ai_console.html",
        model_name=Config.GEMINI_MODEL,
        total_visits=Visit.query.count(),
        total_links=Link.query.count(),
        identified_visits=Visit.query.filter(Visit.email.isnot(None)).count(),
        recent_visits=Visit.query.order_by(Visit.timestamp.desc()).limit(8).all(),
    )


@bp.route("/ai/console/send", methods=["POST"])
@login_required
def ai_console_send():
    message = _extract_message()
    if not message:
        return jsonify({"error": "No message provided."}), 400
    try:
        return jsonify(AIService.generate_response(message))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"AI service error: {exc}"}), 500


@bp.route("/ai/console/stream", methods=["POST", "GET"])
@login_required
def ai_console_stream():
    message = _extract_message()
    if not message:
        return jsonify({"error": "No message provided."}), 400

    def generate():
        yield f"data: {json.dumps({'type': 'meta', 'model': Config.GEMINI_MODEL})}\n\n"
        try:
            for chunk in AIService.generate_stream_response(message):
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@bp.route("/ai")
@login_required
def ai_dashboard():
    return redirect(url_for("dashboard.dashboard_ai.ai_console"))
