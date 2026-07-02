# StudioSaaS Local Deployment

This guide verifies the local StudioSaaS stack before any AWS deployment work.

## Quick Start

From Terminal:

```bash
cd /Users/llmacbookpro/Documents/studiosaas
./start_studiosaas_local.sh
```

Or double-click:

```text
/Users/llmacbookpro/Documents/studiosaas/START_STUDIOSAAS_LOCAL.command
```

The shortcut checks PostgreSQL, creates `studiosaas_local_test` if needed,
applies schema v1, refreshes randomized demo data, and starts the local API/UI
server on `http://localhost:8899`.

If `8899` is already occupied, the shortcut automatically tries the next
available port and prints the actual URLs.

If demo seeding fails, the shortcut prints a warning and still starts the web
server. This prevents a data-generation bug from hiding the UI/API startup
status.

## 1. Requirements

- Python 3.11+ with the project virtual environment installed.
- PostgreSQL 16+ or 18 via Homebrew.
- The repository checked out at `/Users/llmacbookpro/Documents/studiosaas`.

Install Python dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
```

Start PostgreSQL:

```bash
brew services start postgresql@18
pg_isready -h localhost -p 5432
```

## 2. Create a Clean Local Database

```bash
dropdb -h localhost -p 5432 --if-exists studiosaas_local_test
createdb -h localhost -p 5432 studiosaas_local_test
psql -h localhost -p 5432 -d studiosaas_local_test \
  -v ON_ERROR_STOP=1 \
  -f backend/db/schema_v1.sql
```

Confirm the schema and seed plans:

```bash
psql -h localhost -p 5432 -d studiosaas_local_test \
  -c "select code, name, student_limit, user_limit, storage_limit_mb from plans order by monthly_price_aud;"
```

Expected plans:

- `starter`
- `studio`
- `growth`

## 3. Import Legacy Let’s Paint Data

Use the checked-in sample first:

```bash
cd backend
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/import_lets_paint_json.py \
  testdata/legacy_database_sample.json \
  lets-paint-studio \
  "Let's Paint Studio"
```

Seed both local demo tenants, including `Let's Play Piano`:

```bash
cd backend
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_local_test_tenants.py
```

Seed randomized relational demo data for UI testing:

```bash
cd backend
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_random_demo_data.py --students-per-tenant 24
```

Verify imported records and workspace mapping:

```bash
psql -h localhost -p 5432 -d studiosaas_local_test \
  -c "select slug, name, settings->>'workspace_path' as workspace_path from tenants order by slug;"
```

The import script is designed to be safe to rerun against the same tenant slug.
The random demo seed uses real v1 relationships across tenants, courses,
packages, students, credit accounts, registrations, media, portfolio, audit,
subscriptions, and usage.

## 4. Run Legacy Smoke Tests

The original CMS remains the safety net while the SaaS layer is built.

```bash
cd backend
../.venv/bin/python test_cms.py
```

Expected result: all smoke tests pass.

## 5. Start the Local App

```bash
cd backend
PORT=8899 \
CMS_DATA_DIR=/private/tmp/studiosaas_cms_data \
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
STUDIOSAAS_PUBLIC_BASE_DOMAIN=localhost \
../.venv/bin/python server.py
```

Open:

- `http://localhost:8899` - Super Admin dashboard
- `http://localhost:8899/super-admin` - Super Admin dashboard alias
- `http://localhost:8899/lets-paint-studio` - Let's Paint Studio CMS
- `http://localhost:8899/lets-play-piano` - Let's Play Piano CMS
- `http://localhost:8899/lets-play-game` - Let's Play Game CMS
- `http://localhost:8899/lets-paint-studio/studio-admin`
- `http://localhost:8899/lets-paint-studio/register`
- `http://localhost:8899/studio-admin` - shared Studio Admin console

Do not use `http://localhost:8899/register`. Root registration is intentionally
closed because each tenant has its own generated registration page.


## 6. API Checks

If the pages still show the old behavior after code changes, confirm that port
`8899` is running the current checkout, not a stale Python process from an
older run.

Health:

```bash
curl -sS http://localhost:8899/v1/health
```

Tenant via header:

```bash
curl -sS \
  -H 'X-Tenant-Slug: lets-paint-studio' \
  http://localhost:8899/v1/tenant/brand
```

Tenant via slug path:

```bash
curl -sS http://localhost:8899/s/lets-paint-studio/v1/tenant/brand
```

Tenant via subdomain-style Host header:

```bash
curl -sS \
  -H 'Host: lets-paint-studio.localhost:8899' \
  http://localhost:8899/v1/tenant/brand
```

Students:

```bash
curl -sS \
  -H 'X-Tenant-Slug: lets-paint-studio' \
  http://localhost:8899/v1/students
```

Legacy CMS bridge:

```bash
curl -sS http://localhost:8899/lets-paint-studio/cms
curl -sS http://localhost:8899/s/lets-paint-studio/v1/legacy-cms/data
```

Current local smoke expectation:

```bash
cd backend
../.venv/bin/python test_cms.py
```

Expected result: 73 checks passing, 0 failing.

Parent balance query:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{"name":"Amy Wang","phone":"0412 345 678"}' \
  http://localhost:8899/v1/public/lets-paint-studio/balance-query
```

## 7. Troubleshooting

Website did not start:

- Confirm the Terminal output reached `Starting StudioSaaS`.
- If it stopped before that, PostgreSQL/schema setup failed.
- If it reached `Starting StudioSaaS`, use the printed URL; the port may not be
  `8899` if that port was already occupied.
- Run `./start_studiosaas_local.sh` from the project root instead of starting
  `server.py` manually.

Demo seed error:

- The web server should still start.
- Run the printed seed command manually after checking PostgreSQL.
- The seed script is safe to rerun; it refreshes its own randomized demo rows.

PostgreSQL is not accepting connections:

```bash
brew services list | grep postgres
brew services restart postgresql@18
```

`psql` cannot connect over localhost:

- Confirm PostgreSQL is running.
- Confirm local network access is allowed in the current Codex session.
- Try the Unix socket path with `psql -h /tmp -p 5432`.

Vendor JavaScript returns `404`:

- The legacy page falls back to CDN scripts.
- For offline/AWS-hardening, run the existing vendor download workflow or replace the legacy page with a bundled frontend build.

`/s/<tenant_slug>/v1/...` returns 404:

- Confirm the server is running the latest code.
- Confirm the slug is lowercase and exists in the `tenants` table.

## 8. AWS Later

Do not start AWS work until the local checklist above passes. Later AWS mapping:

- PostgreSQL local test database -> RDS PostgreSQL.
- Local photo and portfolio directories -> S3.
- Local environment variables -> SSM Parameter Store or Secrets Manager.
- Waitress local process -> Lightsail systemd service or ECS service.
- `localhost` tenant routing -> Route 53 subdomains and CloudFront.
