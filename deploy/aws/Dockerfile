# StudioSaaS production image (Stage 2 — AWS EC2/ECS).
# Build from the repository root:
#   docker build -f deploy/aws/Dockerfile -t studiosaas:latest .
#
# The app serves the whole project tree (tenants/, legacy-root/, super-admin.html)
# via allowlisted routes in backend/server.py, so the image carries the full tree.
# Mutable state lives OUTSIDE the image:
#   CMS_DATA_DIR            -> /data   (legacy CMS json, secrets, photos, backups)
#   STUDIOSAAS_MEDIA_DIR    -> /media  (tenant portfolio media, S3 adapter later)

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# libpq is not needed (psycopg[binary] bundles it); curl only for the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 studiosaas \
    && mkdir -p /data /media \
    && chown -R studiosaas:studiosaas /data /media /app
USER studiosaas

ENV PORT=8899 \
    STUDIOSAAS_ENV=production \
    STUDIOSAAS_PROJECT_ROOT=/app \
    CMS_DATA_DIR=/data \
    STUDIOSAAS_MEDIA_DIR=/media

EXPOSE 8899

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/v1/health" || exit 1

ENTRYPOINT ["/app/deploy/aws/entrypoint.sh"]
