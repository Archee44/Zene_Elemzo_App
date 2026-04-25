from flask import Flask
from flask import send_from_directory, Response
from backend.database import init_db
from backend.scripts.import_from_csv import seed_if_empty
from backend.routes.music_routes import music_bp
from backend.services.spotify_auth import spotify_auth
from flask_cors import CORS
import sys
from pathlib import Path
import os
from backend.routes.spotify_routes import spotify_bp

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="None"
)
init_db()
seed_if_empty()
CORS(app)

# betölti a .env fájl tartalmát
from dotenv import load_dotenv
load_dotenv()

import os
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")


# Blueprintek regisztrálása
app.register_blueprint(music_bp, url_prefix="/api/music")
app.register_blueprint(spotify_auth, url_prefix="/api/spotify")
app.register_blueprint(spotify_bp, url_prefix="/api/spotify")


# OpenAPI spec and Swagger UI
@app.route("/api/openapi.json")
def openapi_spec():
    spec_dir = project_root / "backend"
    return send_from_directory(str(spec_dir), "openapi.json", mimetype="application/json")


@app.route("/api/swagger")
def swagger_ui():
    html = f"""
    <!doctype html>
    <html lang=\"en\">
      <head>
        <meta charset=\"utf-8\" />
        <title>API Docs</title>
        <link rel=\"stylesheet\" href=\"https://unpkg.com/swagger-ui-dist@4/swagger-ui.css\" />
        <style>body {{ margin:0; padding:0; }} #swagger-ui {{ width:100%; height:100vh; }}</style>
      </head>
      <body>
        <div id=\"swagger-ui\"></div>
        <script src=\"https://unpkg.com/swagger-ui-dist@4/swagger-ui-bundle.js\"></script>
        <script>
          window.ui = SwaggerUIBundle({{
            url: '/api/openapi.json',
            dom_id: '#swagger-ui',
            presets: [SwaggerUIBundle.presets.apis],
          }});
        </script>
      </body>
    </html>
    """
    return Response(html, mimetype="text/html")


@app.route("/")
def home():
    return {"message": "Music recommender API running"}

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
