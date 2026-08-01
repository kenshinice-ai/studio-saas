# StudioSaaS Release And Recovery Runbook

This runbook is deployment-neutral. It applies to a local pilot, a virtual
machine, a container, or a managed platform. Provider-specific deployment is
deliberately outside this document.

## Non-negotiable boundaries

- PostgreSQL is the canonical source for tenant, user, student, registration,
  roster, credit, consent, analytics, and media metadata.
- Every operational query and mutation remains tenant-scoped. A request body,
  header, browser storage value, or uploaded filename cannot choose another
  tenant.
- Super Admin owns platform lifecycle and plans. Studio Admin owns website,
  brand, public media, registration questions, and anonymous portal analytics.
  CMS owns daily operations. Public visitors never receive CMS or Studio Admin
  authority.
- `/<tenant-slug>/register` remains the only standalone registration route;
  root `/register` must return 404.
- Student records are private by default. Public work requires the latest
  append-only consent event to be active. Withdrawing consent removes public
  works immediately.
- Public images use generated display derivatives. Never make original uploads
  the fallback for a missing derivative.

## Required runtime configuration

Set these through the deployment's secret/configuration mechanism, not a file
committed to Git:

```bash
export STUDIOSAAS_DATABASE_URL='postgresql://...'
export STUDIOSAAS_ENV='production'
export PORT='8000'
export STUDIOSAAS_API_KEY='<at least 32 random characters>'
export STUDIOSAAS_SESSION_SECRET='<different, at least 32 random characters>'
export STUDIOSAAS_MEDIA_DIR='/persistent/studiosaas/media'
export CMS_DATA_DIR='/persistent/studiosaas/legacy-data'
export COOKIE_SECURE='1'
```

`STUDIOSAAS_API_KEY` and `STUDIOSAAS_SESSION_SECRET` must be independent.
Production startup fails closed if either is missing, too short, or equal.

Optional tuning: database waits are bounded by default and can be adjusted
with `STUDIOSAAS_DB_CONNECT_TIMEOUT` (seconds, default 5),
`STUDIOSAAS_DB_STATEMENT_TIMEOUT_MS` (default 30000), and
`STUDIOSAAS_DB_LOCK_TIMEOUT_MS` (default 10000).

## Pre-release gate

From the candidate revision:

```bash
bash backend/scripts/build_cms.sh
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh
```

The gate must report all of the following as green:

- Python, inline scripts, CMS bundle, escaping, unit tests, and smoke tests;
- no pending SQL migration;
- no local image missing its sanitized display and thumbnail variants;
- the complete tenant-isolation and privacy integration suite.

Do not waive a red result by skipping PostgreSQL. Diagnose it or stop the
release.

## Backup before change

```bash
STUDIOSAAS_DATABASE_URL="$STUDIOSAAS_DATABASE_URL" \
  .venv/bin/python backend/scripts/backup_postgres.py backup --keep 14
```

Keep both the `.dump` and its `.manifest.json`. New manifests contain the exact
migration inventory and critical table counts. A dump without its matching
manifest is not a release backup.

## Database migration and media backfill

Preview, apply, and verify ordered migrations:

```bash
cd backend
../.venv/bin/python scripts/run_migrations.py --dry-run
../.venv/bin/python scripts/run_migrations.py
../.venv/bin/python scripts/run_migrations.py --check
```

Generate missing privacy-safe image derivatives after migrations:

```bash
cd backend
../.venv/bin/python scripts/backfill_media_variants.py --dry-run
../.venv/bin/python scripts/backfill_media_variants.py
../.venv/bin/python scripts/backfill_media_variants.py --check
```

The backfill preserves originals, writes tenant-scoped derivatives, refreshes
storage usage, and exits non-zero on any undecodable or unsafe asset. Resolve
every reported asset before opening public traffic.

## Rollout order

1. Put the public entry behind the platform's normal maintenance or traffic
   control if the schema change is not backwards-compatible.
2. Create the verified PostgreSQL backup.
3. Deploy the code candidate without changing tenant data by hand.
4. Run ordered migrations.
5. Run the media backfill and its `--check` mode.
6. Start or restart the application with the required configuration.
7. Run the full release gate against the deployed database.
8. Verify `/v1/health`, `/platform-admin`, the optional Access-protected
   `/super-admin` alias, one tenant portal, CMS, Studio Admin,
   and `/<slug>/register`; confirm `/register` is still 404.
9. Reopen traffic and watch errors, storage usage, registration conversion,
   and audit logs.

## Recovery and rollback

Prefer a forward fix when the migrated database is healthy. Reverting code
while retaining compatible additive migrations is safer than restoring an old
database and losing new transactions.

For the current Lightsail release controller, code rollback is automatic when
either internal deep health or public HTTPS deep health fails. Before changing
the `current` symlink or production environment, the controller must capture a
safe previous version. Rollback is successful only when all four checks pass:

1. `current` points back to the prior release directory;
2. `STUDIOSAAS_VERSION` is restored to the prior value;
3. the prior application passes internal deep health; and
4. the public HTTPS endpoint passes deep health with that prior version.

An application restart failure or either failed health check is an explicit
failed rollback, never a warning to ignore. The controller must leave the
maintenance response in place and return non-zero for operator intervention.

Use database restore only for confirmed corruption or an incompatible failed
migration:

```bash
STUDIOSAAS_DATABASE_URL="$STUDIOSAAS_DATABASE_URL" \
  .venv/bin/python backend/scripts/backup_postgres.py restore-dry-run \
  backups/postgres/<backup>.dump
```

The drill creates a temporary sibling database, restores the dump, compares
migrations and critical table counts with the manifest, then removes the
temporary database. Only after this succeeds may an operator run the guarded
real restore:

```bash
STUDIOSAAS_DATABASE_URL='<target-url>' \
  .venv/bin/python backend/scripts/backup_postgres.py restore \
  backups/postgres/<backup>.dump --confirm '<exact_database_name>'
```

Before a real restore, stop writes and record the incident window. Afterward,
rerun the release gate and reconcile any registrations, credit transactions,
consent events, roster changes, or uploads created after the backup timestamp.

## Post-release evidence

Record the Git revision, migration list, backup dump and manifest names, test
counts, release time, operator, and any accepted limitations. Do not record
passwords, access codes, raw session values, student identifiers, or contact
details in release notes. When releasing the containerized form, the
reproducible bundle (with checksum and build info) is produced by
`deploy/aws/build_aws_bundle.sh`.

For Lightsail, also record the release directory, previous version, image tag,
internal and public health payloads, rollback-controller result and the host's
daily backup-cron entry. Off-instance copying remains a separately tracked
operation until implemented; same-instance cron output must not be described
as disaster recovery.
