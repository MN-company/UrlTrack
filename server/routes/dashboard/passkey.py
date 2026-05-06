import base64
import json
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from webauthn import generate_registration_options, options_to_json, verify_registration_response
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from ...config import Config
from ...extensions import db
from ...models import User
from ...utils import safe_json, sanitize


bp = Blueprint("dashboard_passkey", __name__)


def _passkey_rp_id() -> str:
    return Config.SERVER_URL.replace("https://", "").replace("http://", "").split(":")[0].split("/")[0]


@bp.route("/passkey/register/options", methods=["POST"])
@login_required
def passkey_register_options():
    user = db.session.get(User, current_user.id)
    existing_credentials = []
    for item in user.passkeys:
        try:
            existing_credentials.append(PublicKeyCredentialDescriptor(id=base64.urlsafe_b64decode(item["id"] + "==")))
        except (KeyError, ValueError):
            continue

    options = generate_registration_options(
        rp_id=_passkey_rp_id(),
        rp_name="UrlTrack Dashboard",
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.username or user.email,
        exclude_credentials=existing_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )

    from flask import session

    session["webauthn_challenge"] = base64.b64encode(options.challenge).decode()
    return jsonify(json.loads(options_to_json(options)))


@bp.route("/passkey/register/verify", methods=["POST"])
@login_required
def passkey_register_verify():
    from flask import session

    payload = request.get_json(silent=True) or {}
    challenge = session.get("webauthn_challenge")
    if not challenge:
        return jsonify({"status": "error", "message": "Session expired"}), 400

    try:
        verification = verify_registration_response(
            credential=payload.get("credential", payload),
            expected_challenge=base64.b64decode(challenge),
            expected_rp_id=_passkey_rp_id(),
            expected_origin=Config.SERVER_URL,
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    user = db.session.get(User, current_user.id)
    credentials = safe_json(user.passkey_credentials, []) or []
    credentials.append(
        {
            "id": base64.urlsafe_b64encode(verification.credential_id).decode().rstrip("="),
            "public_key": base64.urlsafe_b64encode(verification.credential_public_key).decode(),
            "sign_count": verification.sign_count,
            "name": sanitize(payload.get("name"), 120) or "Passkey",
            "created_at": datetime.utcnow().isoformat(),
        }
    )
    user.passkey_credentials = json.dumps(credentials)
    db.session.commit()
    session.pop("webauthn_challenge", None)
    return jsonify({"status": "success", "message": "Passkey registered successfully"})


@bp.route("/passkey/list")
@login_required
def passkey_list():
    user = db.session.get(User, current_user.id)
    return jsonify(user.passkeys)


@bp.route("/passkey/delete/<credential_id>", methods=["POST"])
@login_required
def passkey_delete(credential_id):
    user = db.session.get(User, current_user.id)
    credentials = [item for item in user.passkeys if item.get("id") != credential_id]
    user.passkey_credentials = json.dumps(credentials)
    db.session.commit()
    return jsonify({"success": True})
