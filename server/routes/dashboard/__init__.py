import hashlib

from flask import Blueprint

from .ai_routes import bp as ai_bp
from .exports import bp as exports_bp
from .links import bp as links_bp
from .passkey import bp as passkey_bp
from .security import bp as security_bp
from .stats import bp as stats_bp


bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")
bp.register_blueprint(links_bp)
bp.register_blueprint(ai_bp)
bp.register_blueprint(exports_bp)
bp.register_blueprint(stats_bp)
bp.register_blueprint(security_bp)
bp.register_blueprint(passkey_bp)


def md5_filter(value):
    if not value:
        return ""
    return hashlib.md5(value.lower().encode("utf-8")).hexdigest()


bp.add_app_template_filter(md5_filter, "md5")
