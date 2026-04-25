import os
import base64
import requests
from urllib.parse import urlencode
from flask import Blueprint, redirect, request, jsonify
from dotenv import load_dotenv

spotify_auth = Blueprint("spotify_auth", __name__)

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:5000/api/spotify/callback"

@spotify_auth.route("/login")
def login():
    scope = "user-read-private user-read-email playlist-read-private playlist-read-collaborative user-library-read"
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": scope,
        "redirect_uri": REDIRECT_URI,
        "show_dialog": "true"
    }
    url = "https://accounts.spotify.com/authorize?" + urlencode(params)
    return redirect(url)

@spotify_auth.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing authorization code"}), 400

    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    token_url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code != 200:
        return jsonify({"error": "Failed to get token", "details": response.text}), 400

    token_info = response.json()

    access_token = token_info.get("access_token")
    refresh_token = token_info.get("refresh_token")

    print("✅ Spotify access token megszerezve:", access_token[:20], "...")

    return redirect(f"http://127.0.0.1:3000/spotify-success?token={access_token}")
