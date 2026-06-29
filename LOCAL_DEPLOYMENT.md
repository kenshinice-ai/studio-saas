# StudioSaaS Local Deployment

This guide verifies the local StudioSaaS stack before any AWS deployment work.

## 1. Requirements

- Python 3.11+ with the project virtual environment installed.
- PostgreSQL 16+ or 18 via Homebrew.
- The repository checked out at `/Users/llmacbookpro/Documents/studiosaas`.

Install Python dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r letspaint-cms-release/requirements.txt
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
  -f letspaint-cms-release/db/schema_v1.sql
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
cd letspaint-cms-release
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/import_lets_paint_json.py \
  testdata/legacy_database_sample.json \
  lets-paint-local-test
```

Verify imported records:

```bash
psql -h localhost -p 5432 -d studiosaas_local_test \
  -c "select 'tenants' table_name, count(*) from tenants union all select 'students', count(*) from students union all select 'packages', count(*) from packages union all select 'registrations', count(*) from registrations union all select 'credit_transactions', count(*) from credit_transactions order by table_name;"
```

The import script is designed to be safe to rerun against the same tenant slug.

## 4. Run Legacy Smoke Tests

The original CMS remains the safety net while the SaaS layer is built.

```bash
cd letspaint-cms-release
../.venv/bin/python test_cms.py
```

Expected result: all smoke tests pass.

## 5. Start the Local App

```bash
cd letspaint-cms-release
PORT=8899 \
CMS_DATA_DIR=/private/tmp/studiosaas_cms_data \
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
STUDIOSAAS_PUBLIC_BASE_DOMAIN=localhost \
../.venv/bin/python server.py
```

Open:

- `http://localhost:8899`
- `http://localhost:8899/super-admin`
- `http://localhost:8899/studio-admin`
- `http://localhost:8899/parent-portal`

## 6. API Checks

Health:

```bash
curl -sS http://localhost:8899/v1/health
```

Tenant via header:

```bash
curl -sS \
  -H 'X-Tenant-Slug: lets-paint-local-test' \
  http://localhost:8899/v1/tenant/brand
```

Tenant via slug path:

```bash
curl -sS http://localhost:8899/s/lets-paint-local-test/v1/tenant/brand
```

Tenant via subdomain-style Host header:

```bash
curl -sS \
  -H 'Host: lets-paint-local-test.localhost:8899' \
  http://localhost:8899/v1/tenant/brand
```

Students:

```bash
curl -sS \
  -H 'X-Tenant-Slug: lets-paint-local-test' \
  http://localhost:8899/v1/students
```

Parent balance query:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{"name":"Amy Wang","phone":"0412 345 678"}' \
  http://localhost:8899/v1/public/lets-paint-local-test/balance-query
```

## 7. Troubleshooting

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
