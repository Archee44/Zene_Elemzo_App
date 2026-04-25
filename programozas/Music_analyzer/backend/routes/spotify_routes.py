import os
import requests
from flask import Blueprint, redirect, request, jsonify
import urllib.parse

spotify_bp = Blueprint("spotify", __name__)

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL")

@spotify_bp.route("/login")
def login():
    scopes = "user-read-private user-read-private playlist-read-private"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": scopes,
        "show_dialog": "true"
    }
    auth_url = f"https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
    return redirect(auth_url)

@spotify_bp.route("/callback")
def callback():
    code = request.args.get("code")
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    response = requests.post(token_url, data=payload)
    token_info = response.json()

    access_token = token_info.get("access_token")
    return redirect(f"{FRONTEND_URL}/spotify-success?token={access_token}")

