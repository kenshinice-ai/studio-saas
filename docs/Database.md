# StudioSaaS Database

Version: v3.3
Date: 2026-07-27
Purpose: Schema definition, table descriptions, canonical enums, migration strategy, and operational notes.

---

## 1. Database Overview

- **Engine:** PostgreSQL 16+ (local), RDS PostgreSQL (AWS production target)
- **Local database name:** `studiosaas_local_test`
- **Bootstrap reference:** `backend/db/schema_v1.sql`
- **Canonical schema evolution:** ordered migrations through `0021_plan_quota_revision.sql`
- **Isolation model:** All business data includes `tenant_id`. All queries bind tenant context.

### 1.1 Design Principles

- Soft delete or deactivate by default — no un-audited hard deletes.
- Every business table has `tenant_id` as a foreign key to `tenants.id`.
- Fresh and existing databases converge through `backend/scripts/run_migrations.py`; `schema_v1.sql` is kept in sync with the migration chain (verified zero drift in v7.4.1) — migrations remain canonical.
- `tenant_id` is the hard isolation boundary — no cross-tenant queries.

> The ER diagram in the v2 architecture poster is a simplified illustration (it shows `users.role`, which does not exist). **This document and `schema_v1.sql` are canonical.**

---

## 2. Table Reference

### 2.1 Platform Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `tenants` | `id`, `slug`, `name`, `status`, `plan_code`, `primary_color`, `secondary_color`, `contact_*`, `settings` (JSONB) | Studio tenant, slug, status, brand config, industry settings |
| `plans` | `code`, `name`, `monthly_price_aud`, `student_limit`, `user_limit`, `storage_limit_mb` | Plan definitions (starter, studio, growth) |
| `subscriptions` | `id`, `tenant_id`, `plan_code`, `status`, `billing_period`, `start_date`, `end_date` | Tenant subscription status |
| `tenant_usage` | `id`, `tenant_id`, `storage_used_mb`, `student_count`, `user_count` | Per-tenant resource usage stats |
| `tenant_brand_drafts` | `tenant_id`, `payload`, `updated_by_user_id`, `updated_at` | Private Studio Admin brand draft; never consumed by public pages |
| `tenant_brand_versions` | `tenant_id`, `version_number`, `payload`, `published_by_user_id`, `published_at` | Immutable public-brand publication history and rollback source |
| `memberships.role` | `super_admin`, `owner`, `manager`, `teacher`, `front_desk`, `staff`, `parent` | Explicit platform, brand-owner, operational and family access bundles |
| `audit_logs` | `id`, `tenant_id`, `user_id`, `action`, `details` (JSONB), `created_at` | Key operation audit trail |

### 2.2 User Management Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `users` | `id`, `email`, `password_hash`, `full_name`, `status` | Platform-wide user accounts. **No `role` and no `tenant_id` column.** |
| `memberships` | `id`, `tenant_id` (nullable), `user_id`, `role`, `permissions` (JSONB), `status`, `public_display_name`, `show_on_public_timetable` | User × tenant × role. **All role assignment lives here.** `UNIQUE (tenant_id, user_id)`. The two publicity columns (0025) are **per person and default off** — being rostered onto a class is not consent to be named on the open internet |

**Current super-admin representation:** `seed_super_admin.py` maintains one
active `super_admin` membership with `tenant_id IS NULL`. That platform row
grants access to current and future tenants without manufacturing per-tenant
memberships.

### 2.3 Business Data Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `students` | `id`, `tenant_id`, identity/contact fields, `birthday`, `enrolled_on`, `status`, `access_code_hash`, access-code timestamps | Student profiles (soft delete via status), real editable join date, and hashed private-portal access. Legacy `enrolled_on` values may remain null. |
| `courses` | `id`, `tenant_id`, `name`, `slug`, `credits`, `price_aud_cents` | Course definitions |
| `class_schedules` | `id`, `tenant_id`, `course_id`, `label`, weekday/time fields, `capacity`, `is_active`, `teacher_user_id`, `is_public`, `room` | Recurring weekly schedule templates (0008; teacher/publication/room added in 0025). `is_public` defaults **false** — "scheduled" and "advertised" are different sets |
| `class_schedule_exceptions` | `schedule_id`, `tenant_id`, `on_date`, `cancelled`, `note` | One-off cancellations of a recurring class (0025). Without it a public timetable is a promise the studio cannot withdraw |
| `packages` | `id`, `tenant_id`, `name`, `description`, `price_aud_cents` | Course package definitions |
| `credit_accounts` | `id`, `tenant_id`, `student_id`, `course_id`, `balance` | Student balance accounts. Unique key: `(tenant_id, student_id, course_id)` |
| `credit_transactions` | `id`, `tenant_id`, `student_id`, `credit_account_id`, `transaction_type`, `amount`, `description` | Ledger-style transaction log |
| `attendance_sessions` | `id`, `tenant_id`, `student_id`, `course_id`, `credit_transaction_id`, `reversal_credit_transaction_id`, `attended_at`, `reversed_at` | Class/check-in records linked to credit ledger consume/refund rows |
| `registrations` | `id`, `tenant_id`, identity/contact fields, `status`, `source`, `source_language`, `campaign`, follow-up fields, `student_id`, review fields, timestamps | Portal/Quick Registration leads and the CMS conversion funnel |
| `daily_roster_entries` | `tenant_id`, `roster_date`, `student_id`, `source`, reversible `status` fields | Canonical date-level roster additions/cancellations; recurring schedules remain templates |

### 2.4 Content Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `media_assets` | `id`, `tenant_id`, `owner_student_id`, `asset_type`, `storage_provider`, `storage_key`, `mime_type`, `byte_size`, `checksum_sha256`, `visibility` | Uploaded file metadata. `UNIQUE (tenant_id, storage_key)` |
| `media_variants` | `tenant_id`, `media_asset_id`, `variant`, dimensions, checksum, `metadata_sanitized` | Upload-time/backfilled display and thumbnail derivatives; public routes never fall back to originals |
| `portfolio_items` | `id`, `tenant_id`, `student_id`, `media_asset_id`, `title`, `visibility`, `public_consent_at`, `public_consent_by_user_id`, `created_at` | Student portfolio entries; public gallery requires recorded consent |
| `student_publication_consent_events` | `tenant_id`, `student_id`, append-only status and evidence | Latest event controls public publication; withdrawal takes effect immediately |
| `share_tokens` | `id`, `tenant_id`, `portfolio_item_id`, `token`, `expires_at` | Parent portal security tokens |

### 2.5 System Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `email_templates` | `id`, `tenant_id`, `key`, `subject`, `body` | Per-tenant email templates |
| `notification_logs` | `id`, `tenant_id`, `user_id`, `template_id`, `status`, `sent_at` | Email/notification send records |
| `student_access_sessions` / `student_access_attempts` | tenant-bound token hash, expiry/revocation, lookup hash and lock window | One-hour private student sessions and non-enumerating brute-force protection |
| `public_analytics_events` | `tenant_id`, allowlisted event, anonymous session hash, campaign, timestamp | Privacy-preserving aggregate portal analytics without student/contact/browser identifiers |
| `tenant_archives` | `id`, `tenant_id`, archive path, snapshot metadata | Pre-deletion archive snapshots of all tenant-owned tables (migration 0005) |

---

## 3. Canonical Enums (actual CHECK constraints)

These are the values enforced by the database today. Code, seeds, UI, and docs must match. Extensions go through migration files only.

| Concept | Column | Values |
|---|---|---|
| Tenant status | `tenants.status` | `lead`, `trial`, `onboarding`, `active`, `past_due`, `paused`, `cancelled`, `archived`, `deleted` |
| Subscription status | `subscriptions.status` | `trialing`, `active`, `past_due`, `paused`, `cancelled`, `archived` |
| User status | `users.status` | `active`, `disabled` |
| Membership role | `memberships.role` | `super_admin`, `owner`, `manager`, `teacher`, `front_desk`, `staff`, `parent` |
| Membership status | `memberships.status` | `active`, `invited`, `disabled` |
| Student status | `students.status` | `active`, `inactive`, `trial`, `archived` |
| Credit transaction | `credit_transactions.transaction_type` | `purchase`, `consume`, `adjustment`, `refund`, `expire`, `migration` |
| Registration status | `registrations.status` | `pending`, `contacted`, `trial_booked`, `waiting`, `approved`, `converted`, `rejected`, `duplicate`, `lost`, `archived` |
| Media asset type | `media_assets.asset_type` | `student_photo`, `registration_photo`, `portfolio`, `homework`, `sheet_music`, `logo`, `website_image` |
| Media storage | `media_assets.storage_provider` | `local`, `s3` |
| Media visibility | `media_assets.visibility` | `private`, `public_token` |
| Notification status | `notification_logs.status` | `queued`, `sent`, `failed` |

Resolved / accepted decisions (2026-07-03, P0-01 and P0-07):

- Python `Role` enum now matches the CHECK constraint exactly. Platform admins are memberships with `tenant_id IS NULL`, unique per user via the `memberships_platform_user_uniq` partial index (migration 0002). Per-tenant `super_admin` rows remain honoured for backward compatibility.
- Tenant, subscription, and registration changes are validated by the canonical transition maps in `studiosaas/lifecycle.py`; request handlers cannot invent incompatible state pairs.
- Archive, restore, and permanent deletion remain dedicated audited services rather than ordinary status edits. Archive snapshots cover all tenant-owned tables before destructive work begins.
- Tenant `trial` vs subscription `trialing` naming drift remains intentional, but valid combinations are enforced as one commercial lifecycle.
- `media_assets.visibility` stays `private`/`public_token` until the media service (P1-03) introduces richer sharing.

### 3.1 Credit Transaction Input Mapping

API input aliases map to schema values:

- `debit` → `consume`
- `adjustment_in` → `adjustment` with positive amount
- `adjustment_out` → `adjustment` with negative amount

### 3.2 Credit Account Model

Option B in effect — a default "General Class" course is created/fetched so `(tenant_id, student_id, course_id)` is always a valid unique key. Implemented: `ON CONFLICT (tenant_id, student_id, course_id)` in `api_v1.py`.

### 3.3 Soft Delete

`students.status` and `users.status` track active/inactive/archived. No un-audited `DELETE` on business tables.

---

## 4. Schema Operations

### 4.1 Bootstrap (Fresh Database)

```bash
dropdb -h localhost -p 5432 --if-exists studiosaas_local_test
createdb -h localhost -p 5432 studiosaas_local_test
psql -h localhost -p 5432 -d studiosaas_local_test \
  -v ON_ERROR_STOP=1 \
  -f backend/db/schema_v1.sql
```

### 4.2 Import Core Let's Paint Student Data

```bash
# Read-only preflight: existing tenant is required; no history is imported.
cd backend
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/import_lets_paint_json.py \
  /absolute/path/to/LetsPaint.json \
  --tenant-slug lets-paint-studio \
  --expected-sha256 <verified-source-sha256>

# Destructive apply requires a verified backup and all explicit confirmations.
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/import_lets_paint_json.py \
  /absolute/path/to/LetsPaint.json \
  --tenant-slug lets-paint-studio \
  --expected-sha256 <verified-source-sha256> \
  --apply --reset-all-students --confirm-tenant lets-paint-studio
```

The core importer retains the legacy student ID, current contact/profile fields,
notes, and current balance. It intentionally excludes logs, attendance, rosters,
packages, media, access codes, privacy history, and creative-profile fields. The
global demo-student reset and target import run in one transaction.

### 4.3 Optional Demo Data

```bash
# Demo generation is opt-in and must never be run against real tenant data.
STUDIOSAAS_SEED_DEMO=1 ./start_studiosaas_local.sh

```

### 4.4 Verify Plans

```bash
psql -h localhost -p 5432 -d studiosaas_local_test \
  -c "select code, name, student_limit, user_limit, storage_limit_mb from plans order by monthly_price_aud;"
```

Expected plans: `starter`, `studio`, `growth`.

### 4.5 Verify Tenant Workspace Mapping

```bash
psql -h localhost -p 5432 -d studiosaas_local_test \
  -c "select slug, settings->>'workspace_path' from tenants order by slug;"
```

---

## 5. Migration Strategy (P0-03)

Current `schema_v1.sql` serves as both bootstrap and patch history. Target:

```
backend/db/
├── schema_v1.sql          # Full bootstrap (read-only reference)
└── migrations/
    ├── 0001_schema_v1.sql
    ├── 0002_platform_membership_index.sql
    ├── ...
    ├── 0011_portfolio_public_consent.sql
    ├── 0012_product_lifecycle_and_brand_versions.sql
    ├── 0013_tenant_role_bundles.sql
    ├── 0014_registration_privacy_consent.sql
    ├── 0015_student_privacy_and_media_variants.sql
    ├── 0016_daily_roster_entries.sql
    ├── 0017_public_website_media_and_analytics.sql
    ├── 0018_student_enrolment_date.sql
    ├── 0019_stability_indexes.sql
    ├── 0020_drop_redundant_indexes.sql
    └── 0021_plan_quota_revision.sql
```

Migration 0019 (v7.4.1 stability pass) adds tenant-leading indexes for
`portfolio_items` and `notification_logs` and drops the duplicate
`credit_accounts` unique partial index (`credit_accounts_general_uniq`,
identical to `idx_credit_accounts_default_account`).

Migration 0020 (v7.6.0 stability pass, 2026-07-27 audit D3/L4) drops two
secondary indexes that duplicated the index already backing a UNIQUE
constraint: `idx_media_variants_asset` (0015; column-identical to
`UNIQUE (tenant_id, media_asset_id, variant)` on `media_variants`) and
`idx_tenant_brand_versions_tenant_published` (0012; only differed by `DESC`
from `UNIQUE (tenant_id, version_number)` on `tenant_brand_versions` — a
btree scans both directions). `ON CONFLICT` inference is unaffected; both
UNIQUE constraints remain. No new tables, so `SNAPSHOT_TABLES` is unchanged.

Migration 0021 (v8.1.0 commercial plan quota revision, 2026-07-30 owner
decision) tightens the three SaaS plan quotas to the published catalogue:
`starter` to 1 team user / 2048 MB, `studio` to 5 team users / 10240 MB, and
`growth` to 1000 students / 51200 MB. Prices, plan codes, plan names, feature
flags and `growth.user_limit` (20) are unchanged. The baseline seed in
`schema_v1.sql` and `0001_schema_v1.sql` carries the same numbers, so a fresh
bootstrap makes 0021 a no-op; it exists for databases seeded with the old
catalogue. Reductions are admission-control only — `_student_capacity`, the
team create/reactivate paths and `media._assert_storage_quota` all reject new
records with 403 and never remove existing rows. No new tables, so
`SNAPSHOT_TABLES` is unchanged.

Tracking table:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);
```

The runner (`backend/scripts/run_migrations.py`) must:
- Apply pending migrations in order.
- Skip already-applied versions.
- Be safe to re-run; support baselining an existing database and `--check` release gating.

---

## 6. DB Timeout Configuration (v7.4.1, refined v7.6.0)

Connections opened by the application (`backend/studiosaas/db.py`) apply
bounded waits so one slow or hung query cannot wedge a waitress thread. The
values are per-session. Maintenance scripts that reuse the same helper
(`run_migrations.py`, `prune_event_tables.py`) explicitly lift the caps via
`connect(statement_timeout_ms=0, lock_timeout_ms=0)`, so long-running
migrations and pruning are never killed by the app defaults; `pg_dump`
connects on its own and is unaffected either way. Override the app defaults
via environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `STUDIOSAAS_DB_CONNECT_TIMEOUT` | `5` (seconds) | Connection establishment timeout |
| `STUDIOSAAS_DB_STATEMENT_TIMEOUT_MS` | `30000` | Per-statement execution ceiling |
| `STUDIOSAAS_DB_LOCK_TIMEOUT_MS` | `10000` | Maximum wait for a row/table lock |

---

## 7. Data Privacy Notes

- Children's photos and personal information require special handling.
- Public artwork requires both item-level publication intent and the student's latest append-only consent event to be confirmed; withdrawal keeps the private item and removes it from public results immediately.
- Public/student-facing images use metadata-free derivatives. Missing derivatives fail closed instead of exposing originals.
- Data deletion and export mechanisms must support privacy compliance.
- Support mode (platform staff viewing tenant data) must always log to `audit_logs`.
- No real children's private data should appear in demo or test databases.
