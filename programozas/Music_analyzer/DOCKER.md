Docker support with Essentia (Linux-only)

Overview
- Runs the Flask backend in a Linux container with Essentia installed.
- No code changes required; binds on 0.0.0.0 via Flask CLI.

Prerequisites
- Docker and Docker Compose
- Place your backend `.env` next to `docker-compose.yml` (programozas/Music_analyzer/.env).

Build & Run
- From `programozas/Music_analyzer/`:
  - `docker compose up --build`
  - Backend available on `http://localhost:5000`

Volumes
- `./uploads` is mounted into the container at `/app/uploads` for file persistence.

Using Essentia in code
- Inside the container, Essentia (with TensorFlow ops) is installed via conda. Example import:
  ```python
  try:
      import essentia
      import essentia.standard as es
  except ImportError:
      essentia = None
  ```
- You can conditionally use Essentia if available and fallback to librosa on non-Linux hosts.

- Notes
- The container uses conda (miniforge) and installs `essentia-tensorflow` + `tensorflow=2.8`, so `TensorflowPredictEffnetDiscogs` is available.
- The `version:` key in docker-compose is deprecated and removed intentionally; Compose v2 ignores it.
- Discogs400 EffNet genre models (place under `/app/models/discogs400`):
  - Classifier head (.pb): `genre_discogs400-discogs-effnet-1.pb` (classification-heads)
  - Embedding (.pb): `discogs-effnet-bs64-1.pb` (music-style-classification/discogs-effnet)
  - Labels: `genre_discogs400_labels.txt` or `genre_discogs400.labels.txt` or `genre_discogs400-discogs-effnet-1.json` (backend can read classes from JSON)
  Backend uses them via `backend/services/genre_model.py`.

If model download fails during build (404 or network issues)
- Host mount is enabled: `./models` on host is mounted to `/app/models` in the container.
- Manually place files under `models/discogs400/` with one of the accepted names:
  - Classifier: `genre_discogs400-discogs-effnet-1.pb` or `genre_discogs400-effnet-1.pb`
  - Embeddings: `discogs-effnet-bs64-1.pb` or `discogs-effnet-bs64.pb`
  - Labels: `genre_discogs400_labels.txt` or `genre_discogs400.labels.txt` or `genre_discogs400-discogs-effnet-1.json`
- Rebuild: `docker compose up --build`

Troubleshooting
- If the app doesn’t start, check logs: `docker compose logs -f backend`.
- If ports are in use, adjust `5000:5000` mapping in `docker-compose.yml`.
- For GPU/audio drivers, this setup uses CPU-only processing.
