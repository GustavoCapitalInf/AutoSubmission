FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 intern

WORKDIR /app

COPY requirements.txt requirements-analysis.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-analysis.txt

COPY --chown=intern:intern . .
# Customer data lives outside the checkout (/app): the app refuses a data folder
# inside it (ocr/private_artifacts.py, visual_pair_private_path_must_be_outside_checkout).
RUN mkdir -p /data && chown intern:intern /data

# No USER here: the container starts as root only to hand the data folder to
# `intern`, because a freshly mounted volume (Fly, or a bind mount) is owned by
# root. The app itself always runs as intern (see CMD).

ENV PYTHONUNBUFFERED=1 \
    WEBAPP_HOST=0.0.0.0 \
    WEBAPP_PORT=5000 \
    WEBAPP_DATA_DIR=/data

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz')"

CMD ["sh", "-c", "chown intern:intern /data && exec setpriv --reuid=intern --regid=intern --init-groups python -m webapp.app"]
