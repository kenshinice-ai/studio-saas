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

# curl: healthcheck. postgresql-client: pg_dump/pg_restore so
# backup_postgres.py can run INSIDE the container
# (`docker compose exec app python backend/scripts/...`) — the deploy audit
# found the backup path otherwise impossible on the Docker route.
#
# The client major version is PINNED to the server's (PostgreSQL 16). The
# unpinned `postgresql-client` on this base image resolves to 17, and a 17
# pg_restore emits `SET transaction_timeout = 0` — a PG17-only GUC — which a
# PG16 server rejects, so every restore rehearsal failed while the daily dump
# looked fine. A backup that cannot be restored is not a backup, so the pairing
# is asserted at build time rather than discovered during an incident.
# When the server moves to 17, bump PG_MAJOR here in the same change.
ARG PG_MAJOR=16
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && install -d -m 0755 /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
         https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
         > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends "postgresql-client-${PG_MAJOR}" \
    && apt-get purge -y --auto-remove gnupg \
    && rm -rf /var/lib/apt/lists/* \
    && pg_dump --version && pg_restore --version

WORKDIR /app

# Exact production pins (deploy/aws/requirements.lock); backend/requirements.txt
# keeps the wide development ranges.
COPY deploy/aws/requirements.lock deploy/aws/requirements.lock
RUN pip install -r deploy/aws/requirements.lock

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

# deep=1 probes the database too — the container goes unhealthy during an
# RDS outage instead of reporting green while every real request 500s.
HEALTHCHECK --interval=30s --timeout=8s --start-period=25s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/v1/health?deep=1" || exit 1

ENTRYPOINT ["/app/deploy/aws/entrypoint.sh"]
