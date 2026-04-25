import os
from typing import Optional
from flask import Blueprint, request, jsonify, g, send_from_directory
from sqlalchemy.orm import Session
from ..database import SessionLocal
from backend.services.music_service import get_or_create_song_from_file, recommend_similar_songs
from backend.services.clustering_service import rebuild_clusters, is_available as is_cluster_available
from backend.services.faiss_recommender import rebuild_index, is_available as is_faiss_available
from backend.services.music_analyze import analyze_music                                            
from backend.services.musicbrainz_service import enrich_song_from_musicbrainz, search_best_recording
from backend.services.reccobeats import get_features_by_ids
from backend.models import Song, ExternalLink, PlatformNameEnum
import re

music_bp = Blueprint("music", __name__)
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))
os.makedirs(UPLOAD_DIR, exist_ok=True)

def sanitize_filename(filename):
    return re.sub(r'[^\w\-_\.]', '_', filename)

@music_bp.before_request
def before_request():
    g.db = SessionLocal()

@music_bp.after_request
def after_request(response):
    db = g.get('db')
    if db is not None:
        db.close()
    return response

@music_bp.route("/analyze", methods=["POST"])
def analyze_and_save():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded!"}), 400

    safe_name = sanitize_filename(file.filename)
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    if os.path.exists(filepath):
        os.remove(filepath)
    file.save(filepath)

    db: Session = g.db
    try:
        song_object = get_or_create_song_from_file(filepath, db)
        analysis_data = analyze_music(filepath)
        analysis_data.pop("path", None)
        analysis_data['database_id'] = song_object.id
        analysis_data['message'] = f"Song processed. DB ID: {song_object.id}"
        return jsonify(analysis_data)

    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass

@music_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    if not os.path.exists(os.path.join(UPLOAD_DIR, filename)):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(UPLOAD_DIR, filename, mimetype='audio/mpeg')

@music_bp.route("/recommend/<int:track_id>", methods=["GET"])
def recommend(track_id):
    db: Session = g.db
    try:
        recommendations = recommend_similar_songs(track_id, db)
        return jsonify(recommendations)
    except Exception as e:
        return jsonify({"error": f"Could not generate recommendations: {str(e)}"}), 500

@music_bp.route("/recommend/index/rebuild", methods=["POST"])
def rebuild_recommendation_index():
    db: Session = g.db
    if not is_faiss_available():
        return jsonify({
            "ok": False,
            "message": "FAISS is not installed; index rebuild skipped."
        }), 503
    try:
        stats = rebuild_index(db)
        return jsonify({
            "ok": True,
            "message": "FAISS index rebuilt.",
            "stats": stats,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@music_bp.route("/clusters/rebuild", methods=["POST"])
def rebuild_song_clusters():
    db: Session = g.db
    if not is_cluster_available():
        return jsonify({
            "ok": False,
            "message": "Clustering backend is not installed; rebuild skipped."
        }), 503
    try:
        stats = rebuild_clusters(db)
        return jsonify({
            "ok": True,
            "message": "Song clusters rebuilt.",
            "stats": stats,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@music_bp.route("/musicbrainz/search", methods=["POST"])
def musicbrainz_search():
    data = request.json or {}
    title = (data.get("title") or "").strip()
    artist = (data.get("artist") or "").strip()
    if not title or not artist:
        return jsonify({"error": "Missing title or artist"}), 400

    match = search_best_recording(title, artist)
    if not match:
        return jsonify({"error": "No MusicBrainz match found"}), 404

    return jsonify({
        "mbid": match.get("id"),
        "title": match.get("title"),
        "artist_credit": match.get("artist-credit"),
        "score": match.get("score"),
        "releases": match.get("releases") or [],
    })

@music_bp.route("/musicbrainz/enrich/<int:song_id>", methods=["POST"])
def musicbrainz_enrich_song(song_id: int):
    db: Session = g.db
    song = db.query(Song).filter(Song.id == song_id).first()
    if song is None:
        return jsonify({"error": "Song not found"}), 404

    enriched = enrich_song_from_musicbrainz(song)
    if not enriched:
        return jsonify({"error": "No MusicBrainz match found"}), 404

    song.mbid = enriched.get("mbid") or song.mbid
    if not song.album_name and enriched.get("album_name"):
        song.album_name = enriched.get("album_name")
    if not song.release_year and enriched.get("release_year"):
        song.release_year = enriched.get("release_year")

    db.commit()
    db.refresh(song)

    return jsonify({
        "ok": True,
        "song_id": song.id,
        "mbid": song.mbid,
        "album_name": song.album_name,
        "release_year": song.release_year,
        "match_score": enriched.get("raw_match_score"),
    })

import requests
import base64
from flask import redirect, session
from datetime import datetime
from functools import lru_cache
import io

AUDIUS_SEARCH_URL = "https://discoveryprovider.audius.co/v1/tracks/search"
AUDIUS_APP_NAME = "melodive"

@lru_cache(maxsize=1024)
def get_audius_mood(track_name: str, artist_name: Optional[str] = None) -> Optional[str]:
    if not track_name:
        return None

    query = track_name
    if artist_name:
        query = f"{artist_name} {track_name}"

    try:
        print("Audius mood query:", query)
        params = { "query": query, "app_name": AUDIUS_APP_NAME, "limit": 1 }
        resp = requests.get(AUDIUS_SEARCH_URL, params=params, timeout=5)
        if resp.status_code != 200:
            print("Audius search error:", resp.status_code, resp.text)
            return None

        data = resp.json() or {}
        items = data.get("data") or []
        if not items:
            return None

        mood = items[0].get("mood")
        return mood
    except Exception as e:
        print("Audius mood exception:", e)
        return None

GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")

@music_bp.route("/search-lyrics", methods=["POST"])
def search_lyrics():
    data = request.json
    snippet = data.get("snippet")
    if not snippet:
        return jsonify({"error": "Nem adott meg szöveget"}), 400

    url = "https://api.genius.com/search"
    headers = {"Authorization": f"Bearer {GENIUS_TOKEN}"}
    params = {"q": snippet}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        results = response.json()["response"]["hits"]
        if not results:
            return jsonify({"error": "Nincs találat"}), 404

        songs = []
        for hit in results[:10]:
            song = hit["result"]
            songs.append({
                "title": song["title"],
                "artist": song["primary_artist"]["name"],
                "cover": song["song_art_image_url"],
                "release_date": song["release_date_for_display"],
                "views": song["stats"].get("pageviews", 0),
                "featured_artists": song.get("featured_artists", []),
                "lyrics_url": song["path"],
                "popularity": song["stats"]["hot"]
                })
        return jsonify({"songs": songs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@music_bp.route("/search-artist", methods=["POST"])
def search_artist():
    if not GENIUS_TOKEN:
        return jsonify({"error": "Genius token not configured"}), 500

    data = request.json
    name = data.get("name")
    if not name:
        return jsonify({"error": "Nem adott meg nevet"}), 400

    query_lower = name.lower()
    search_url = f"https://api.genius.com/search"
    try:
        search_res = requests.get(search_url,headers={"Authorization": f"Bearer {GENIUS_TOKEN}"}, params={"q": name})
        search_res.raise_for_status()
        hits = search_res.json()["response"]["hits"]
        if not hits:
            return jsonify({"error": "Nem található ilyen nevű zeneszerző"}), 404

        best_artist_obj = None
        best_score = -1

        for hit in hits:
            result = hit.get("result", {})
            primary = result.get("primary_artist")
            if not primary:
                continue
            artist_name = primary.get("name", "")
            artist_lower = artist_name.lower()

            score = 0
            if artist_lower == query_lower:
                score = 3
            elif artist_lower.startswith(query_lower):
                score = 2
            elif query_lower in artist_lower:
                score = 1

            if score > best_score:
                best_score = score
                best_artist_obj = primary

        if best_artist_obj is None or best_score == 0:
            return jsonify({"error": "Nem található ilyen nevű zeneszerző"}), 404

        artist_id = best_artist_obj["id"]
        artist_url = f"https://api.genius.com/artists/{artist_id}"
        artist_res = requests.get(artist_url, headers={"Authorization": f"Bearer {GENIUS_TOKEN}"})
        artist_res.raise_for_status()
        artist_data = artist_res.json()["response"]["artist"]

        songs_url = f"https://api.genius.com/artists/{artist_id}/songs"
        songs_res = requests.get(songs_url,headers={"Authorization": f"Bearer {GENIUS_TOKEN}"}, params={"sort": "popularity", "per_page": 5})
        songs_res.raise_for_status()
        songs_data = songs_res.json()["response"]["songs"]

        def get_text(node):
            if isinstance(node, str):
                return node
            if isinstance(node, dict):
                return "".join(get_text(child) for child in node.get("children", []))
            if isinstance(node, list):
                return "".join(get_text(child) for child in node)
            return ""

        description_dom = artist_data.get("description", {}).get("dom")
        description_text = get_text(description_dom).strip()

        if len(description_text) > 700:
            description_text = description_text[:700].rsplit(".", 1)[0] + "."

        def spotify_get_artist_brief(artist_name):
            token = get_spotify_token()
            headers = {"Authorization": f"Bearer {token}"}
            params = {"q": artist_name, "type": "artist", "limit": 1}
            r = requests.get("https://api.spotify.com/v1/search", headers=headers, params=params, timeout=8)
            r.raise_for_status()
            items = r.json().get("artists", {}).get("items", [])
            if not items:
                return None
            a = items[0]
            return {
                "spotify_id": a.get("id"),
                "spotify_url": a.get("external_urls", {}).get("spotify"),
                "genres": a.get("genres", []),
                "popularity": a.get("popularity", 0),
                "followers": a.get("followers", {}).get("total", 0),
                "image": (a.get("images") or [{}])[0].get("url"),
            }
        sp = spotify_get_artist_brief(artist_data.get("name"))

        return jsonify({
            "name": artist_data.get("name"),
            "alternate_names": artist_data.get("alternate_names", []),
            "image": artist_data.get("image_url"),
            "description": description_text,
            "genres": sp.get("genres", []),
            "spotify_popularity": sp.get("popularity"),
            "spotify_followers": sp.get("followers"),
            "images": sp.get("images", []),
            "top_songs": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "image": s.get("song_art_image_url"),
                    "release_date": s.get("release_date_for_display"),
                    "views": s.get("stats", {}).get("pageviews", 0)
                } for s in songs_data
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
progress_state = {"current": 0, "total": 0}
@music_bp.route("/search-discover", methods=["POST"])
def discover_music():
    data = request.get_json() or {}

    progress_state["current"] = 0
    progress_state["total"] = 0

    genre = data.get("genre") or "any"
    mood = data.get("mood") or "any"
    popularity_mode = data.get("popularityMode", "any")
    release_range = data.get("releaseRange", "any")
    explicit_mode = data.get("explicitMode", "any")

    def spotify_get(path, params=None):
        SPOTIFY_BASE_URL = "https://api.spotify.com/v1"
        if params is None:
            params = {}

        headers = {
            "Authorization": f"Bearer {get_spotify_token()}"
        }

        url = SPOTIFY_BASE_URL + path
        resp = requests.get(url, headers=headers, params=params, timeout=10)

        if resp.status_code != 200:
            print("Spotify hiba:", resp.status_code, resp.text)
            resp.raise_for_status()

        return resp.json()

    min_pop = None
    max_pop = None
    if popularity_mode == "popular":
        min_pop = 50
        max_pop = 100
    elif popularity_mode == "unpopular":
        min_pop = 0
        max_pop = 49
    else:
        min_pop = 0
        max_pop = 100

    now = datetime.utcnow()
    q_parts = []
    if genre == "any":
        genre = None
    if genre:
        q_parts.append(f'genre:"{genre}"')

    min_year = None
    max_year = None
    if release_range == "new":
        min_year = now.year-1
        max_year = now.year
    elif release_range == "2010s":
        min_year = 2010
        max_year = 2019
    elif release_range == "2000s":
        min_year = 2000
        max_year = 2009
    elif release_range == "old":
        min_year = 1950
        max_year = 1999
    elif release_range == "any":
        min_year = 1950
        max_year = now.year
    else:
        pass

    if min_year is not None or max_year is not None:
        if min_year is None:
            min_year = 1900
        if max_year is None:
            max_year = now.year
        q_parts.append(f"year:{min_year}-{max_year}")

    if not q_parts:
        q_parts.append("year:1950-2025")

    q = " ".join(q_parts)
    print("Discover query:", q)

    LIMIT = 50
    MAX_PAGES = 2
    offset = 0
    filtered_tracks = []

    requested_mood = (mood or "any").lower()

    for page in range(MAX_PAGES):
        try:
            search_data = spotify_get("/search", params={
                "q": q,
                "type": "track",
                "limit": LIMIT,
                "offset": offset,
            })
        except Exception as e:
            progress_state["total"] += len(tracks)
            print("Discover Spotify search error:", e)
            return jsonify({"error": "Spotify search hiba történt"}), 500

        tracks = (search_data.get("tracks") or {}).get("items", [])
        print(f"PAGE {page}, offset={offset}, tracks={len(tracks)}")

        if not tracks:
            break

        progress_state["total"] += len(tracks)
        page_filtered = []

        for t in tracks:
            if not t:
                progress_state["current"] += 1
                continue

            pop = t.get("popularity") or 0
            if min_pop is not None and pop < min_pop:
                progress_state["current"] += 1
                continue
            if max_pop is not None and pop > max_pop:
                progress_state["current"] += 1
                continue

            is_explicit = bool(t.get("explicit"))
            if explicit_mode == "clean" and is_explicit:
                progress_state["current"] += 1
                continue
            if explicit_mode == "explicit" and not is_explicit:
                progress_state["current"] += 1
                continue

            audius_mood = None
            if requested_mood != "any":
                artists = t.get("artists") or []
                primary_artist = artists[0].get("name") if artists else None

                audius_mood = get_audius_mood(t.get("name"), primary_artist)
                print("Audius mood for", t.get("name"), "->", audius_mood)

                if not audius_mood:
                    progress_state["current"] += 1
                    continue

                if audius_mood.lower() != requested_mood:
                    progress_state["current"] += 1
                    continue

            if audius_mood:
                t["_audius_mood"] = audius_mood

            page_filtered.append(t)
            progress_state["current"] += 1

        if page_filtered:
            filtered_tracks = page_filtered
            break
        offset += LIMIT
    if not filtered_tracks:
        return jsonify({"tracks": []})
    progress_state["current"] = progress_state["total"]
    simplified = []
    for t in filtered_tracks:
        album = t.get("album", {})
        images = album.get("images") or []
        image_url = images[0]["url"] if images else None
        mood = t.get("_audius_mood")

        simplified.append({
            "id": t.get("id"),
            "name": t.get("name"),
            "artists": [a.get("name") for a in t.get("artists", [])],
            "album": album.get("name"),
            "release_date": album.get("release_date"),
            "popularity": t.get("popularity"),
            "spotify_url": t.get("external_urls", {}).get("spotify"),
            "image": image_url,
            "mood": mood
        })
    return jsonify({"tracks": simplified})
@music_bp.route("/search-discover/progress")
def discover_progress():
    current = progress_state["current"]
    total = progress_state["total"] or 1
    percent = round(current / total * 100)
    return jsonify({"percent": percent})
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

@music_bp.route("/youtube", methods=["GET"])
def youtube_search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&maxResults=1&q={query}&key={YOUTUBE_API_KEY}"
    )
    res = requests.get(url)
    data = res.json()

    if "items" not in data or not data["items"]:
        return jsonify({"error": "No results"}), 404

    video_id = data["items"][0]["id"]["videoId"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    return jsonify({"video_url": video_url})

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

class SpotifyLookupError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

def get_spotify_token():
    auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {b64_auth_str}"}
    data = {"grant_type": "client_credentials"}

    try:
        res = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data, timeout=10)
    except requests.RequestException as exc:
        raise SpotifyLookupError(f"Spotify token request failed: {exc}", 502) from exc
    if not res.ok:
        raise SpotifyLookupError(res.text.strip() or "Spotify token request failed", res.status_code)
    try:
        payload = res.json()
    except ValueError as exc:
        raise SpotifyLookupError("Spotify token response was not valid JSON", 502) from exc
    access_token = payload.get("access_token")
    if not access_token:
        raise SpotifyLookupError("Spotify token response missing access_token", 502)
    return access_token

def search_spotify_track_meta(query: str) -> Optional[dict]:
    if not query:
        return None
    token = get_spotify_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "type": "track", "limit": 1}
    try:
        res = requests.get("https://api.spotify.com/v1/search", headers=headers, params=params, timeout=10)
    except requests.RequestException as exc:
        raise SpotifyLookupError(f"Spotify search request failed: {exc}", 502) from exc
    if not res.ok:
        raise SpotifyLookupError(res.text.strip() or "Spotify search request failed", res.status_code)
    try:
        data = res.json()
    except ValueError as exc:
        raise SpotifyLookupError("Spotify search response was not valid JSON", 502) from exc
    items = (data.get("tracks") or {}).get("items") or []
    if not items:
        return None
    track = items[0]
    meta = {
        "id": track.get("id"),
        "title": track.get("name"),
        "artist": (track.get("artists") or [{}])[0].get("name"),
        "url": (track.get("external_urls") or {}).get("spotify"),
        "preview_url": track.get("preview_url"),
        "popularity": track.get("popularity"),
    }
    return meta

@music_bp.route("/spotify", methods=["GET"])
def spotify_search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        meta = search_spotify_track_meta(query)
        if not meta:
            return jsonify({"error": "No results"}), 404
        return jsonify({
            "track_url": meta.get("url"),
            "spotify_id": meta.get("id"),
            "artist": meta.get("artist"),
            "title": meta.get("title"),
            "preview_url": meta.get("preview_url"),
        })
    except SpotifyLookupError as e:
        print("Spotify search error:", e.message)
        status = e.status_code if 400 <= e.status_code <= 599 else 502
        return jsonify({"error": "Spotify API unavailable", "details": e.message}), status
    except Exception as e:
        print("Spotify search error:", e)
        return jsonify({"error": "Spotify API error"}), 500

@music_bp.route("/recommend-external", methods=["POST"])
def recommend_external():
    """Local recommender: uses only songs/features stored in our own database."""
    data = request.json or {}
    query = (data.get("query") or "").strip()
    features = data.get("features") or {}
    db: Session = g.db

    if not query and not features:
        return jsonify({"error": "Hiányzó keresési kifejezés"}), 400

    def _norm(text: Optional[str]) -> str:
        return (text or "").strip().lower()

    def _find_seed_song() -> Optional[Song]:
        spotify_id = (features.get("spotify_id") or features.get("track_id") or "").strip()
        if spotify_id:
            by_spotify = (
                db.query(Song)
                .join(ExternalLink, ExternalLink.song_id == Song.id)
                .filter(
                    ExternalLink.platform_name == PlatformNameEnum.spotify,
                    ExternalLink.external_id == spotify_id,
                )
                .first()
            )
            if by_spotify:
                return by_spotify

        artist = _norm(features.get("artist"))
        title = _norm(features.get("title"))
        if artist and title:
            exact = (
                db.query(Song)
                .filter(
                    Song.artist_name.ilike(artist),
                    Song.title.ilike(title),
                )
                .first()
            )
            if exact:
                return exact

            partial = (
                db.query(Song)
                .filter(
                    Song.artist_name.ilike(f"%{artist}%"),
                    Song.title.ilike(f"%{title}%"),
                )
                .first()
            )
            if partial:
                return partial

        if query:
            q = _norm(query)
            if " - " in q:
                maybe_artist, maybe_title = [x.strip() for x in q.split(" - ", 1)]
                hit = (
                    db.query(Song)
                    .filter(
                        Song.artist_name.ilike(f"%{maybe_artist}%"),
                        Song.title.ilike(f"%{maybe_title}%"),
                    )
                    .first()
                )
                if hit:
                    return hit

            fuzzy = (
                db.query(Song)
                .filter(
                    (Song.title.ilike(f"%{q}%")) | (Song.artist_name.ilike(f"%{q}%"))
                )
                .first()
            )
            if fuzzy:
                return fuzzy

        return None

    seed_song = _find_seed_song()
    seed_meta = {
        "id": seed_song.id if seed_song else None,
        "title": seed_song.title if seed_song else (features.get("title") or query),
        "artist": seed_song.artist_name if seed_song else (features.get("artist") or ""),
    }

    if not seed_song:
        return jsonify({
            "seed": seed_meta,
            "recommendations": [],
            "source": "database",
            "error": "Nincs egyező seed dal a helyi adatbázisban.",
        })

    raw_recs = recommend_similar_songs(seed_song.id, db, limit=12)
    if not raw_recs:
        return jsonify({
            "seed": seed_meta,
            "recommendations": [],
            "source": "database",
        })

    rec_ids = [int(r["id"]) for r in raw_recs if r.get("id") is not None]
    links_by_song: dict[int, str] = {}
    if rec_ids:
        links = (
            db.query(ExternalLink.song_id, ExternalLink.platform_name, ExternalLink.external_url)
            .filter(ExternalLink.song_id.in_(rec_ids))
            .all()
        )
        priority = {
            PlatformNameEnum.spotify: 0,
            PlatformNameEnum.youtube: 1,
            PlatformNameEnum.deezer: 2,
        }
        best_rank: dict[int, int] = {}
        for song_id, platform_name, external_url in links:
            rank = priority.get(platform_name, 99)
            prev = best_rank.get(song_id, 999)
            if rank < prev:
                best_rank[song_id] = rank
                links_by_song[song_id] = external_url

    recommendations = []
    for r in raw_recs:
        sid = int(r.get("id", 0))
        recommendations.append({
            "id": sid,
            "title": r.get("title"),
            "artist": r.get("artist"),
            "score": r.get("score"),
            "url": links_by_song.get(sid, ""),
            "source": "database",
        })

    return jsonify({
        "seed": seed_meta,
        "recommendations": recommendations,
        "source": "database",
    })

@music_bp.route("/genius-top", methods=["GET"])
def genius_top_songs():
    import requests
    from datetime import datetime

    try:
        url = "https://genius.com/api/songs/chart?time_period=day&chart_genre=all&per_page=50"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/118.0.5993.88 Safari/537.36",
            "Accept": "application/json",
        }

        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()

        data = res.json()
        chart_items = data.get("response", {}).get("chart_items", [])

        if not chart_items:
            return jsonify({"error": "Nem találtam toplistát a Genius API-n"}), 404

        top_tracks = []
        for i, item in enumerate(chart_items, start=1):
            song = item["item"]
            top_tracks.append({
                "rank": i,
                "title": song["title"],
                "artist": song["primary_artist"]["name"],
                "url": song["url"],
                "image": song["song_art_image_thumbnail_url"]
            })

        return jsonify({
            "date": datetime.today().strftime("%Y-%m-%d"),
            "top_tracks": top_tracks
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
@music_bp.route("/reccobeats-features", methods=["GET"])
def reccobeats_features():
    ids_param = request.args.get("ids")
    spotify_id = request.args.get("spotify_id")
    if not ids_param and not spotify_id:
        return jsonify({"error": "Missing ids or spotify_id"}), 400

    ids = []
    if ids_param:
        ids = [x.strip() for x in ids_param.split(",") if x.strip()]
    elif spotify_id:
        ids = [spotify_id.strip()]

    try:
        data = get_features_by_ids(ids)
        if data is None:
            return jsonify({"error": "ReccoBeats API error"}), 500
        return jsonify(data)
    except Exception as e:
        print("ReccoBeats features error:", e)
        return jsonify({"error": "Unexpected server error"}), 500
