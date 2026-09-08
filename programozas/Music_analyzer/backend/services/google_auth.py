import os
import requests
from urllib.parse import urlencode
from flask import Blueprint, redirect, request, jsonify, g
from dotenv import load_dotenv

from datetime import datetime, timedelta, timezone

from ..database import SessionLocal
from ..models.user import User, UserLinkedAccount, LinkedProviderEnum
from .auth_utils import issue_state, verify_state, issue_app_token, verify_connect_state, require_auth
from . import youtube_service

google_auth_bp = Blueprint("google_auth", __name__)

load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:5000/api/auth/callback"
FRONTEND_REDIRECT = "http://127.0.0.1:3000/profile"


@google_auth_bp.before_request
def before_request():
    g.db = SessionLocal()


@google_auth_bp.after_request
def after_request(response):
    db = g.get('db')
    if db is not None:
        db.close()
    return response


@google_auth_bp.route("/login")
def login():
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid email profile",
        "state": issue_state(),
        "access_type": "online",
        "prompt": "select_account",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return redirect(url)


@google_auth_bp.route("/callback")
def callback():
    if not verify_state(request.args.get("state")):
        return jsonify({"error": "Invalid or expired state parameter"}), 400

    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing authorization code"}), 400

    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    if token_res.status_code != 200:
        return jsonify({"error": "Failed to exchange code", "details": token_res.text}), 400

    google_access_token = token_res.json().get("access_token")

    userinfo_res = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {google_access_token}"},
    )
    if userinfo_res.status_code != 200:
        return jsonify({"error": "Failed to fetch Google userinfo", "details": userinfo_res.text}), 400

    info = userinfo_res.json()
    google_id = info.get("sub")
    email = info.get("email")
    name = info.get("name")
    picture = info.get("picture")

    if not google_id or not email:
        return jsonify({"error": "Google userinfo missing sub/email"}), 400

    db = g.db
    user = db.query(User).filter(User.google_id == google_id).first()
    if user is None:
        user = db.query(User).filter(User.email == email).first()

    if user is None:
        user = User(email=email, google_id=google_id, display_name=name, avatar_url=picture)
        db.add(user)
    else:
        user.google_id = google_id
        user.display_name = name
        user.avatar_url = picture

    db.commit()
    db.refresh(user)

    app_token = issue_app_token(user.id)
    return redirect(f"{FRONTEND_REDIRECT}?token={app_token}")


@google_auth_bp.route("/youtube/connect-init", methods=["POST"])
@require_auth
def youtube_connect_init():
    return jsonify({"authorize_url": youtube_service.build_authorize_url(g.current_user.id)})


@google_auth_bp.route("/youtube/callback")
def youtube_callback():
    user_id = verify_connect_state(request.args.get("state"))
    if user_id is None:
        return redirect(f"{FRONTEND_REDIRECT}?youtube=error")

    code = request.args.get("code")
    if not code:
        return redirect(f"{FRONTEND_REDIRECT}?youtube=error")

    tokens = youtube_service.exchange_code_for_tokens(code)
    if not tokens or "access_token" not in tokens:
        return redirect(f"{FRONTEND_REDIRECT}?youtube=error")

    db = g.db
    account = (
        db.query(UserLinkedAccount)
        .filter(UserLinkedAccount.user_id == user_id, UserLinkedAccount.provider == LinkedProviderEnum.youtube)
        .first()
    )
    if account is None:
        account = UserLinkedAccount(user_id=user_id, provider=LinkedProviderEnum.youtube)
        db.add(account)

    account.access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    if refresh_token:
        # Google only returns a refresh_token on the first/forced-consent grant -
        # keep the previously stored one if this response didn't include a new one.
        account.refresh_token = refresh_token
    expires_in = tokens.get("expires_in", 3600)
    account.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    db.commit()
    return redirect(f"{FRONTEND_REDIRECT}?youtube=connected")
