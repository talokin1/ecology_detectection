# Trend Detective SI assistant (ADR-009). Build from the repo root:
#   docker build -f deploy/assistant/Dockerfile -t assistant .
# Only the assistant code and the app's precomputed JSON go into the image (no NASA cache, no secrets).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 \
    ASSISTANT_DATA_DIR=/srv/data ASSISTANT_METHODS=/srv/docs/10-methods.md
WORKDIR /srv
COPY requirements-assistant.txt .
RUN pip install --no-cache-dir -r requirements-assistant.txt
COPY backend/trend_detective/__init__.py app/trend_detective/__init__.py
COPY backend/trend_detective/assistant app/trend_detective/assistant
COPY frontend/public/data/index.json frontend/public/data/catalog.json data/
COPY frontend/public/data/analysis data/analysis
COPY frontend/public/data/compare data/compare
COPY frontend/public/data/map data/map
COPY docs/10-methods.md docs/10-methods.md
RUN useradd --system --uid 10001 app
USER app
CMD exec uvicorn trend_detective.assistant.app:app --app-dir /srv/app --host 0.0.0.0 --port ${PORT}
