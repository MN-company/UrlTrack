from flask import Blueprint, request, render_template, abort, make_response, redirect, render_template_string
from user_agents import parse
from datetime import datetime
from jinja2.sandbox import SandboxedEnvironment
import hashlib
import secrets

from ..models import Link, Visit
from ..extensions import db, limiter
from ..utils import get_geo_data, is_bot_ua, verify_turnstile, parse_referrer, sign_visit_token, anonymize_ip, should_require_consent
from ..config import Config
from ..validators import get_client_ip, normalize_destination_url

bp = Blueprint('public', __name__)

LINK_CACHE = {}
CACHE_TTL = 60


def _safe_url_or_none(url: str):
    if not url:
        return None
    try:
        return normalize_destination_url(url)
    except Exception:
        return None


def _build_public_csp(nonce: str) -> str:
    return (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://challenges.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https://flagcdn.com https://*.gravatar.com; "
        "connect-src 'self' https://challenges.cloudflare.com; "
        "frame-src https://challenges.cloudflare.com;"
    )


def _public_response(template_name: str, status: int = 200, **kwargs):
    if Config.CSP_STRICT:
        nonce = secrets.token_urlsafe(16)
        kwargs['csp_nonce'] = nonce
        resp = make_response(render_template(template_name, **kwargs))
        resp.headers['Content-Security-Policy'] = _build_public_csp(nonce)
    else:
        resp = make_response(render_template(template_name, **kwargs))
    resp.status_code = status
    return resp

@bp.route('/<slug>', methods=['GET'])
def redirect_to_url(slug):
    # 1. Cache
    cached = LINK_CACHE.get(slug)
    link = None
    if cached and (datetime.utcnow().timestamp() - cached['timestamp'] < CACHE_TTL):
        link = cached['link']
    
    if not link:
        # PROTECT RESERVED ROUTES from being caught as slugs
        if slug.lower() in Config.RESERVED_SLUGS:
            abort(404)
            
        link = Link.query.filter_by(slug=slug).first_or_404()
        LINK_CACHE[slug] = {'link': link, 'timestamp': datetime.utcnow().timestamp()}

    # Consent Gate (Optional)
    if should_require_consent(request):
        return _public_response('consent.html', next_url=f'/{slug}', hide_nav=True)

    # Log Visit
    raw_ip = get_client_ip(request, Config.TRUST_PROXY_HEADERS)
    client_ip = anonymize_ip(raw_ip) if Config.ANONYMIZE_IP else raw_ip
    ua_string = request.user_agent.string
    user_agent = parse(ua_string)
    
    # Critical: Geo Data needed for blocking (Cached)
    geo = get_geo_data(raw_ip)
    
    # V27: ETag Zombie Cookie Logic
    client_etag = request.headers.get('If-None-Match')
    if not client_etag:
        import uuid
        client_etag = str(uuid.uuid4())
    
    # 2. Save minimal Visit (Fast)
    visit = Visit(
        link_id=link.id,
        ip_address=client_ip,
        user_agent=ua_string,
        referrer=request.referrer,
        os_family=user_agent.os.family,
        device_type="Mobile" if user_agent.is_mobile else "Tablet" if user_agent.is_tablet else "Desktop",
        isp=geo.get('isp'),
        org=geo.get('org'),
        country=geo.get('country'),
        city=geo.get('city'),
        country_code=geo.get('countryCode'),
        lat=geo.get('lat'),
        lon=geo.get('lon'),
        etag=client_etag
    )
    
    try:
        db.session.add(visit)
        db.session.commit()
    except Exception as e:
        # EMERGENCY FAILSAFE: If DB fails, log error but ALLOW redirect
        print(f"CRITICAL DB ERROR (Visit Log Failed): {e}")
        db.session.rollback()
        # Create a dummy ID for the template to prevent crash
        visit.id = "error_fallback"
    
    # Async Enrichment (DNS, etc)
    if visit.id != "error_fallback":
        from ..extensions import log_queue
        try:
            log_queue.put({'type': 'enrich_visit', 'visit_id': visit.id, 'ip': raw_ip})
        except:
            pass

    visit_token = sign_visit_token(visit.id) if visit.id != "error_fallback" else None
    
    # === LOGIC IMPLEMENTATION (V41) ===
    
    # 1. Scheduling (Time-based Access) - IMPROVED V42
    if link.schedule_start_hour is not None or link.schedule_end_hour is not None:
        try:
            import pytz
            
            # Determine Timezone
            tz_name = link.schedule_timezone or 'UTC'
            try:
                target_tz = pytz.timezone(tz_name)
            except pytz.UnknownTimeZoneError:
                # Fallback to UTC if invalid TZ provided
                target_tz = pytz.UTC
            
            # Get current time in target timezone
            current_time = datetime.now(target_tz)
            current_hour = current_time.hour
            
            # Start Check
            if link.schedule_start_hour is not None:
                if current_hour < link.schedule_start_hour:
                     return _public_response('error.html', status=404, message="Link not yet active", hide_nav=True)
            
            # End Check
            if link.schedule_end_hour is not None:
                if current_hour >= link.schedule_end_hour:
                     return _public_response('error.html', status=404, message="Link expired (Schedule)", hide_nav=True)
        except Exception as e:
            print(f"Scheduling Error: {e}")

    # 2. Allowed Countries (Geo-Fencing)
    if link.allowed_countries:
        allowed_list = [c.strip().upper() for c in link.allowed_countries.split(',') if c.strip()]
        visitor_cc = geo.get('countryCode', '').upper()
        if visitor_cc and allowed_list and visitor_cc not in allowed_list:
            # Blocked Location
            visit.is_suspicious = True
            visit.notes = f"Blocked: Country {visitor_cc} not allowed"
            db.session.commit()
            return _public_response('error.html', status=403, message="Access Denied from your location", visit_id=visit.id, hide_nav=True)

    # Checks
    try:
        final_dest = normalize_destination_url(link.destination)
    except Exception:
        return _public_response('error.html', status=400, message="Invalid destination URL", hide_nav=True)
        
    # 3. Mobile Targeting
    if user_agent.is_mobile or user_agent.is_tablet:
        if user_agent.os.family == 'iOS' and link.ios_url:
            try:
                final_dest = normalize_destination_url(link.ios_url)
            except Exception:
                return _public_response('error.html', status=400, message="Invalid iOS destination URL", hide_nav=True)
            
        elif user_agent.os.family == 'Android' and link.android_url:
            try:
                final_dest = normalize_destination_url(link.android_url)
            except Exception:
                return _public_response('error.html', status=400, message="Invalid Android destination URL", hide_nav=True)
    
    # === LIMITS CHECK (V40) ===
    # 1. Expiration
    if link.expiration_minutes and link.expiration_minutes > 0:
        elapsed = (datetime.utcnow() - link.created_at).total_seconds() / 60
        if elapsed > link.expiration_minutes:
             return _public_response('error.html', status=404, message="Link Expired", hide_nav=True)

    # 2. Max Clicks
    if link.max_clicks and link.max_clicks > 0:
        # Count visits (excluding this current one ideally, but since we already committed it, we check count including it or use <=)
        # We already committed the visit above at line 64. So count will be at least 1.
        # If max_clicks is 1, and we just added 1, count is 1. If we visit again, count is 2.
        # So logic: check count. If count > max_clicks, Block.
        visit_count = Visit.query.filter_by(link_id=link.id).count()
        if visit_count > link.max_clicks:
             return _public_response('error.html', status=404, message="Link Limit Reached", hide_nav=True)
             
    # === SECURITY CHECKS (Correct Order) ===
    # Define cloud providers for VPN/Bot detection - EXPANDED LIST
    cloud_providers = [
        'google', 'amazon', 'microsoft', 'digitalocean', 'oracle', 'aliyun', 'hetzner',
        'ovh', 'linode', 'vultr', 'lease', 'dedibox', 'choopa', 'm247', 'fly.io',
        'datacenter', 'hosting', 'server', 'vpn', 'proxy', 'tor', 'exit', 'node',
        'expressvpn', 'nordvpn', 'cyberghost', 'surfshark', 'cloudflare', 'fastly', 'akamai'
    ]
    
    # 1. VPN/Bot/Malicious Detection
    is_bot = is_bot_ua(ua_string) or geo.get('hosting') == True or geo.get('proxy') == True
    if geo.get('org'):
        org_lower = geo.get('org').lower()
        if any(p in org_lower for p in cloud_providers):
            is_bot = True
            
    is_vpn_or_cloud = geo.get('hosting') == True or geo.get('proxy') == True
    if geo.get('org'):
        org_lower = geo.get('org').lower()
        if any(p in org_lower for p in cloud_providers):
            is_vpn_or_cloud = True
    
    # Check Malicious IP Blocklist
    from ..utils import is_malicious_ip
    is_malicious = is_malicious_ip(raw_ip)
    if is_malicious:
        is_vpn_or_cloud = True
        visit.is_suspicious = True
        visit.notes = "Malicious IP Detected"
        # ALWAYS block malicious IPs regardless of link settings
        db.session.commit()
        safe_dest = _safe_url_or_none(link.safe_url)
        if safe_dest:
            final_dest = safe_dest
        else:
            return _public_response('error.html', status=403, message="Access Denied (IP Reputation)", visit_id=visit.id, hide_nav=True)
    
    # Check VPN block (only if not already blocked by malicious check)
    if link.block_vpn and is_vpn_or_cloud:
        visit.is_suspicious = True
        visit.is_vpn = True
        visit.notes = visit.notes or "Blocked: VPN/Cloud Detected"
        db.session.commit()
        safe_dest = _safe_url_or_none(link.safe_url)
        if safe_dest:
            final_dest = safe_dest
        else:
            return _public_response('error.html', status=403, message="Anonymizer/VPN/Cloud IP Detected", visit_id=visit.id, hide_nav=True)
    
    # Check Bot block
    if link.block_bots and is_bot:
        visit.is_suspicious = True
        visit.notes = "Blocked: Bot Detected"
        db.session.commit()
        safe_dest = _safe_url_or_none(link.safe_url)
        if safe_dest:
            final_dest = safe_dest
        else:
            return _public_response('error.html', status=403, message="Suspicious Traffic", visit_id=visit.id, hide_nav=True)
    
    # 2. Captcha Check
    if link.enable_captcha:
        captcha_cookie = request.cookies.get(f'auth_captcha_{link.slug}')
        expected_hash = hashlib.sha256(f"captcha_ok_{link.slug}{Config.SECRET_KEY}".encode()).hexdigest()
        if captcha_cookie != expected_hash:
            return _public_response(
                'captcha.html',
                slug=link.slug,
                visit_id=visit.id,
                visit_token=visit_token,
                site_key=Config.TURNSTILE_SITE_KEY,
                hide_nav=True
            )
    
    # 3. Password Check
    if link.password_hash:
        auth_cookie = request.cookies.get(f'auth_pwd_{link.slug}')
        expected_hash = hashlib.sha256(f"{link.password_hash}{Config.SECRET_KEY}".encode()).hexdigest()
        if auth_cookie != expected_hash:
            return _public_response(
                'password.html',
                slug=link.slug,
                visit_id=visit.id,
                visit_token=visit_token,
                site_key=Config.TURNSTILE_SITE_KEY,
                hide_nav=True
            )
    
    # 4. Email Gate Check
    if link.require_email:
        verified_cookie = request.cookies.get(f'verified_{link.slug}')
        if not verified_cookie:
            return _public_response(
                'email_gate.html',
                slug=link.slug,
                visit_id=visit.id,
                visit_token=visit_token,
                site_key=Config.TURNSTILE_SITE_KEY,
                allow_partial_email_capture=Config.ALLOW_PARTIAL_EMAIL_CAPTURE,
                hide_nav=True
            )

    # V38 AI Architect Custom Rendering
    if link.custom_html:
        # Inject Tracking Beacon
        tracking_js = f"""
        <script>
            try {{
                navigator.sendBeacon("/api/beacon", JSON.stringify({{
                    visit_id: "{visit.id}",
                    visit_token: "{visit_token}",
                    canvas_hash: "ArchitectFit",
                    webgl_renderer: "CustomLanding"
                }}));
                // Simple version of Session Detector for custom pages
                (function(){{
                    const probes = [{{name:'Github',url:'https://github.com/fluidicon.png'}}];
                    probes.forEach(p => {{
                        new Image().src = p.url;
                    }});
                }})();
            }} catch(e) {{}}
        </script>
        """
        html_content = link.custom_html.replace('</body>', tracking_js + '</body>')
        
        # Security: Use Jinja2 Sandbox to prevent SSTI
        sandbox = SandboxedEnvironment()
        template = sandbox.from_string(html_content)
        html = template.render(destination=final_dest, visit_id=visit.id, visit_token=visit_token)
        resp = make_response(html)
        if Config.CUSTOM_HTML_LOCKDOWN:
            resp.headers['Content-Security-Policy'] = (
                "default-src 'none'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self'; "
                "form-action 'self'; "
                "base-uri 'none'; "
                "frame-ancestors 'none';"
            )
        return resp

    # Success
    resp = _public_response(
        'loading.html',
        destination=final_dest,
        visit_id=visit.id,
        visit_token=visit_token,
        allow_no_js=link.allow_no_js,
        hide_nav=True
    )
    
    # 3. SET THE TRAP (Send ETag back to browser)
    resp.headers['ETag'] = client_etag
    resp.headers['Cache-Control'] = 'private, max-age=31536000' # Force caching
    
    return resp

@bp.route('/verify_captcha', methods=['POST'])
@limiter.limit("5 per minute")
def verify_captcha():
    slug = request.form.get('slug')
    turnstile_token = request.form.get('cf-turnstile-response')
    visit_id = request.form.get('visit_id')
    client_ip = get_client_ip(request, Config.TRUST_PROXY_HEADERS)
    
    link = Link.query.filter_by(slug=slug).first_or_404()
    
    if verify_turnstile(turnstile_token, client_ip):
        auth_hash = hashlib.sha256(f"captcha_ok_{slug}{Config.SECRET_KEY}".encode()).hexdigest()
        resp = make_response(redirect(f"/{slug}"))
        resp.set_cookie(f"auth_captcha_{slug}", auth_hash, max_age=3600, httponly=True, secure=True, samesite='Lax')
        return resp
    else:
        return _public_response('captcha.html', status=400, slug=slug, visit_id=visit_id,
                               visit_token=sign_visit_token(visit_id),
                               site_key=Config.TURNSTILE_SITE_KEY, error="Verification Failed", hide_nav=True)

@bp.route('/verify_password', methods=['POST'])
@limiter.limit("5 per minute")
def verify_password():
    slug = request.form.get('slug')
    password = request.form.get('password')
    turnstile_token = request.form.get('cf-turnstile-response')
    visit_id = request.form.get('visit_id')
    client_ip = get_client_ip(request, Config.TRUST_PROXY_HEADERS)
    
    link = Link.query.filter_by(slug=slug).first_or_404()
    
    # Verify Turnstile
    if not verify_turnstile(turnstile_token, client_ip):
        return _public_response('password.html', status=400, slug=slug, visit_id=visit_id,
                               visit_token=sign_visit_token(visit_id),
                               site_key=Config.TURNSTILE_SITE_KEY, error="Captcha Failed", hide_nav=True)
    
    # Verify Password
    user_hash = hashlib.sha256(password.encode()).hexdigest()
    if user_hash == link.password_hash:
        auth_hash = hashlib.sha256(f"{link.password_hash}{Config.SECRET_KEY}".encode()).hexdigest()
        resp = make_response(redirect(f"/{slug}"))
        resp.set_cookie(f"auth_pwd_{slug}", auth_hash, max_age=3600, httponly=True, secure=True, samesite='Lax')
        return resp
    else:
        return _public_response('password.html', status=401, slug=slug, visit_id=visit_id,
                               visit_token=sign_visit_token(visit_id),
                               site_key=Config.TURNSTILE_SITE_KEY, error="Invalid Password", hide_nav=True)

@bp.route('/verify_email', methods=['POST'])
@limiter.limit("5 per minute")
def verify_email():
    slug = request.form.get('slug')
    visit_id = request.form.get('visit_id')
    email = request.form.get('email')
    turnstile_token = request.form.get('cf-turnstile-response')
    client_ip = get_client_ip(request, Config.TRUST_PROXY_HEADERS)
    
    # 1. Basic Validation
    if not slug or not email:
        return "Missing data", 400
        
    link = Link.query.filter_by(slug=slug).first_or_404()
    visit = Visit.query.get(visit_id)

    # Optional Turnstile check (if configured)
    if Config.TURNSTILE_SECRET_KEY:
        if not verify_turnstile(turnstile_token, client_ip):
            return _public_response('email_gate.html', status=400,
                                 slug=slug, visit_id=visit_id, site_key=Config.TURNSTILE_SITE_KEY,
                                 visit_token=sign_visit_token(visit_id),
                                 allow_partial_email_capture=Config.ALLOW_PARTIAL_EMAIL_CAPTURE,
                                 error="Captcha Failed")
    
    # 2. Email Policy Enforcement (V23)
    from ..utils import is_disposable_email, is_privacy_email, validate_email_strict
    
    # SENIOR VALIDATION: Gibberish & Strict Syntax
    is_valid_strict, strict_reason = validate_email_strict(email)
    if not is_valid_strict:
        return _public_response('email_gate.html', status=400,
                             slug=slug, visit_id=visit_id, site_key=Config.TURNSTILE_SITE_KEY,
                             visit_token=sign_visit_token(visit_id),
                             allow_partial_email_capture=Config.ALLOW_PARTIAL_EMAIL_CAPTURE,
                             error=strict_reason)
    
    # Policy: Certified Only (Block Temp)
    if link.email_policy in ['certified', 'trackable']:
        if is_disposable_email(email):
            return _public_response('email_gate.html', status=400,
                                 slug=slug, visit_id=visit_id, site_key=Config.TURNSTILE_SITE_KEY,
                                 visit_token=sign_visit_token(visit_id),
                                 allow_partial_email_capture=Config.ALLOW_PARTIAL_EMAIL_CAPTURE,
                                 error="Ephemeral/Temporary emails are not accepted. Please use a standard provider.")

    # Policy: Trackable Only (Block Temp + Privacy)
    if link.email_policy == 'trackable':
        if is_privacy_email(email):
            temp_provider = is_disposable_email(email) # Recheck to be sure
            error_msg = "Private/Anonymous email providers are restricted. Please use a standard ISP or Corporate email."
            return _public_response('email_gate.html', status=400,
                                 slug=slug, visit_id=visit_id, site_key=Config.TURNSTILE_SITE_KEY,
                                 visit_token=sign_visit_token(visit_id),
                                 allow_partial_email_capture=Config.ALLOW_PARTIAL_EMAIL_CAPTURE,
                                 error=error_msg)

    # 3. Save Email and Create Lead
    if visit:
        visit.email = email
        db.session.commit()
        
        # Create Lead if not exists
        from ..models import Lead
        lead = Lead.query.filter_by(email=email).first()
        if not lead:
            lead = Lead(email=email, scan_status='pending')
            db.session.add(lead)
            db.session.commit()
        

    
    # 4. Success -> Redirect to Loading
    # Checks
    try:
        final_dest = normalize_destination_url(link.destination)
    except Exception:
        return _public_response('error.html', status=400, message="Invalid destination URL", hide_nav=True)
        
    visit_token = sign_visit_token(visit.id) if visit else None
    return _public_response('loading.html', 
                           destination=final_dest, 
                           visit_id=visit_id, 
                           visit_token=visit_token,
                           allow_no_js=link.allow_no_js, 
                           block_adblock=link.block_adblock,
                           hide_nav=True)


@bp.route('/consent', methods=['POST'])
def record_consent():
    next_url = request.form.get('next', '/')
    if not next_url.startswith('/'):
        next_url = '/'
    resp = make_response(redirect(next_url))
    max_age = Config.CONSENT_TTL_DAYS * 86400
    resp.set_cookie(
        Config.CONSENT_COOKIE_NAME,
        '1',
        max_age=max_age,
        httponly=True,
        secure=Config.SESSION_COOKIE_SECURE,
        samesite='Lax'
    )
    return resp
