import os
from functools import wraps
from typing import Optional

from flask import request, jsonify, g, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from backend.database import SessionLocal
from backend.models.user import User

STATE_SALT = "google-oauth-state"
STATE_MAX_AGE = 600  # 10 minutes - plenty for a login redirect round-trip

TOKEN_SALT = "app-auth-token"
TOKEN_MAX_AGE = 7 * 24 * 3600  # 7 days

CONNECT_STATE_SALT = "youtube-connect-state"
CONNECT_STATE_MAX_AGE = 600  # 10 minutes


def _serializer(salt: str) -> URLSafeTimedSerializer:
    secret = current_app.secret_key
    return URLSafeTimedSerializer(secret, salt=salt)


def issue_state() -> str:
    return _serializer(STATE_SALT).dumps(os.urandom(16).hex())


def verify_state(state: Optional[str]) -> bool:
    if not state:
        return False
    try:
        _serializer(STATE_SALT).loads(state, max_age=STATE_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


def issue_app_token(user_id: int) -> str:
    return _serializer(TOKEN_SALT).dumps({"user_id": user_id})


def verify_app_token(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    try:
        data = _serializer(TOKEN_SALT).loads(token, max_age=TOKEN_MAX_AGE)
        return data.get("user_id")
    except (BadSignature, SignatureExpired):
        return None


def issue_connect_state(user_id: int) -> str:
    return _serializer(CONNECT_STATE_SALT).dumps({"user_id": user_id})


def verify_connect_state(state: Optional[str]) -> Optional[int]:
    if not state:
        return None
    try:
        data = _serializer(CONNECT_STATE_SALT).loads(state, max_age=CONNECT_STATE_MAX_AGE)
        return data.get("user_id")
    except (BadSignature, SignatureExpired):
        return None


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        token = auth_header[len("Bearer "):].strip()
        user_id = verify_app_token(token)
        if user_id is None:
            return jsonify({"error": "Invalid or expired token"}), 401

        db = g.get("db")
        owns_session = db is None
        if owns_session:
            db = SessionLocal()

        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            if owns_session:
                db.close()
            return jsonify({"error": "User not found"}), 401

        g.current_user = user
        try:
            return f(*args, **kwargs)
        finally:
            if owns_session:
                db.close()

    return wrapper
