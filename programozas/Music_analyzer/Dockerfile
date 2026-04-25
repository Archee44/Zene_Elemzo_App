# Base Linux image to enable Essentia (Linux-only)
FROM python:3.9-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app

# System libs required by Essentia wheel and audio processing
RUN set -eux; \
    apt-get update -y; \
    apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        libfftw3-3 \
        libsamplerate0 \
        libchromaprint1 \
        curl \
        ca-certificates \
        libtag1v5 \
    || apt-get -o Acquire::Retries=3 install -y --no-install-recommends libtag1v5-vanilla; \
    rm -rf /var/lib/apt/lists/*

# Python deps first (cache-friendly layer)
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt && \
    python -m pip install --upgrade --force-reinstall "numpy==1.23.5" && \
    python -m pip install "tensorflow==2.8.4" "essentia-tensorflow==2.1b6.dev858" && \
    python -m pip install --no-deps "faiss-cpu==1.7.4"

# App code
COPY . /app

EXPOSE 5000
ENV FLASK_APP=app:app
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]
