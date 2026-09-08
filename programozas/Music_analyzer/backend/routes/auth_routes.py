import re

from flask import Blueprint, jsonify, g, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models.user import User, UserLinkedAccount, LinkedProviderEnum
from ..services.auth_utils import require_auth

auth_bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]{3,24}$")


@auth_bp.before_request
def before_request():
    g.db = SessionLocal()


@auth_bp.after_request
def after_request(response):
    db = g.get('db')
    if db is not None:
        db.close()
    return response


def _serialize_user(user: User, db: Session) -> dict:
    youtube_account = (
        db.query(UserLinkedAccount)
        .filter(UserLinkedAccount.user_id == user.id, UserLinkedAccount.provider == LinkedProviderEnum.youtube)
        .first()
    )
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "google_connected": bool(user.google_id),
        "youtube_connected": bool(youtube_account and youtube_account.access_token),
    }


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    return jsonify(_serialize_user(g.current_user, g.db))


@auth_bp.route("/me", methods=["PATCH"])
@require_auth
def update_me():
    data = request.get_json(silent=True) or {}
    if "username" not in data:
        return jsonify({"error": "Nothing to update"}), 400

    username = (data.get("username") or "").strip()
    if not USERNAME_RE.match(username):
        return jsonify({
            "error": "A felhasználónév 3-24 karakter lehet: betűk, számok, '_', '.', '-'."
        }), 400

    db: Session = g.db
    user = g.current_user

    taken = (
        db.query(User)
        .filter(func.lower(User.username) == username.lower(), User.id != user.id)
        .first()
    )
    if taken:
        return jsonify({"error": "Ez a felhasználónév már foglalt."}), 409

    user.username = username
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify({"error": "Ez a felhasználónév már foglalt."}), 409

    db.refresh(user)
    return jsonify(_serialize_user(user, db))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    # Stateless bearer token - the client just discards it. Nothing to revoke
    # server-side yet; if that's ever needed, add a revoked-tokens table.
    return jsonify({"ok": True})


@auth_bp.route("/youtube/disconnect", methods=["DELETE"])
@require_auth
def youtube_disconnect():
    db: Session = g.db
    account = (
        db.query(UserLinkedAccount)
        .filter(UserLinkedAccount.user_id == g.current_user.id, UserLinkedAccount.provider == LinkedProviderEnum.youtube)
        .first()
    )
    if account:
        db.delete(account)
        db.commit()
    return jsonify({"ok": True})
