# StudioSaaS Database

Version: v3.0
Date: 2026-07-03
Purpose: Schema definition, table descriptions, canonical enums, migration strategy, and operational notes.

---

## 1. Database Overview

- **Engine:** PostgreSQL 16+ (local), RDS PostgreSQL (AWS production target)
- **Local database name:** `studiosaas_local_test`
- **Schema file:** `backend/db/schema_v1.sql` (18 tables)
- **Isolation model:** All business data includes `tenant_id`. All queries bind tenant context.

### 1.1 Design Principles

- Soft delete or deactivate by default — no un-audited hard deletes.
- Every business table has `tenant_id` as a foreign key to `tenants.id`.
- Schema is both bootstrap and migration target; a migration runner is planned (P0-03).
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
| `audit_logs` | `id`, `tenant_id`, `user_id`, `action`, `details` (JSONB), `created_at` | Key operation audit trail |

### 2.2 User Management Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `users` | `id`, `email`, `password_hash`, `full_name`, `status` | Platform-wide user accounts. **No `role` and no `tenant_id` column.** |
| `memberships` | `id`, `tenant_id` (nullable), `user_id`, `role`, `permissions` (JSONB), `status` | User × tenant × role. **All role assignment lives here.** `UNIQUE (tenant_id, user_id)` |

**Current super-admin representation:** `seed_super_admin.py` inserts a `super_admin` membership *per existing tenant*. Consequences (tracked as P0-01):

- A platform admin gains no access to tenants created after seeding unless a membership is added.
- The seed's `ON CONFLICT ... SET updated_at = now()` references a column that does not exist on `memberships`.
- The Python `Role` enum values `platform_super_admin` and `admin` are rejected by the CHECK constraint and can never be stored.

Decision pending (P0-01): either represent platform roles as memberships with `tenant_id IS NULL`, or keep the per-tenant model and auto-grant membership on tenant creation.

### 2.3 Business Data Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `students` | `id`, `tenant_id`, `first_name`, `last_name`, `display_name`, `status`, `parent_name`, `mobile`, `email`, `tags` | Student profiles (soft delete via status) |
| `courses` | `id`, `tenant_id`, `name`, `slug`, `credits`, `price_aud_cents` | Course definitions |
| `packages` | `id`, `tenant_id`, `name`, `description`, `price_aud_cents` | Course package definitions |
| `credit_accounts` | `id`, `tenant_id`, `student_id`, `course_id`, `balance` | Student balance accounts. Unique key: `(tenant_id, student_id, course_id)` |
| `credit_transactions` | `id`, `tenant_id`, `student_id`, `credit_account_id`, `transaction_type`, `amount`, `description` | Ledger-style transaction log |
| `attendance_sessions` | `id`, `tenant_id`, `student_id`, `course_id`, `credit_transaction_id`, `reversal_credit_transaction_id`, `attended_at`, `reversed_at` | Class/check-in records linked to credit ledger consume/refund rows |
| `registrations` | `id`, `tenant_id`, `first_name`, `last_name`, `mobile`, `status`, `student_id`, `duplicate_of_registration_id`, `review_note`, `submitted_at` | Public registration applications and Studio Admin review decisions |

### 2.4 Content Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `media_assets` | `id`, `tenant_id`, `owner_student_id`, `asset_type`, `storage_provider`, `storage_key`, `mime_type`, `byte_size`, `checksum_sha256`, `visibility` | Uploaded file metadata. `UNIQUE (tenant_id, storage_key)` |
| `portfolio_items` | `id`, `tenant_id`, `student_id`, `media_asset_id`, `title`, `visibility`, `public_consent_at`, `public_consent_by_user_id`, `created_at` | Student portfolio entries; public gallery requires recorded consent |
| `share_tokens` | `id`, `tenant_id`, `portfolio_item_id`, `token`, `expires_at` | Parent portal security tokens |

### 2.5 System Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `email_templates` | `id`, `tenant_id`, `key`, `subject`, `body` | Per-tenant email templates |
| `notification_logs` | `id`, `tenant_id`, `user_id`, `template_id`, `status`, `sent_at` | Email/notification send records |

---

## 3. Canonical Enums (actual CHECK constraints)

These are the values enforced by the database today. Code, seeds, UI, and docs must match. Extensions go through migration files only (P0-03, P0-07).

| Concept | Column | Values |
|---|---|---|
| Tenant status | `tenants.status` | `trial`, `active`, `past_due`, `paused`, `cancelled` |
| Subscription status | `subscriptions.status` | `trialing`, `active`, `past_due`, `paused`, `cancelled` |
| User status | `users.status` | `active`, `disabled` |
| Membership role | `memberships.role` | `super_admin`, `owner`, `staff`, `parent` |
| Membership status | `memberships.status` | `active`, `invited`, `disabled` |
| Student status | `students.status` | `active`, `inactive`, `trial`, `archived` |
| Credit transaction | `credit_transactions.transaction_type` | `purchase`, `consume`, `adjustment`, `refund`, `expire`, `migration` |
| Registration status | `registrations.status` | `pending`, `approved`, `rejected`, `duplicate`, `contacted`, `archived` |
| Media asset type | `media_assets.asset_type` | `student_photo`, `registration_photo`, `portfolio`, `homework`, `sheet_music`, `logo` |
| Media storage | `media_assets.storage_provider` | `local`, `s3` |
| Media visibility | `media_assets.visibility` | `private`, `public_token` |
| Notification status | `notification_logs.status` | `queued`, `sent`, `failed` |

Resolved / accepted decisions (2026-07-03, P0-01 and P0-07):

- Python `Role` enum now matches the CHECK constraint exactly. Platform admins are memberships with `tenant_id IS NULL`, unique per user via the `memberships_platform_user_uniq` partial index (migration 0002). Per-tenant `super_admin` rows remain honoured for backward compatibility.
- `tenants.status` deliberately has **no** `archived` value — pause/cancel cover current lifecycle needs. Extend via a migration file when the product actually needs archival.
- Tenant `trial` vs subscription `trialing` naming drift is **accepted**: they are independent enums, both validated in `api_v1.py` (`TENANT_STATUSES`, `SUBSCRIPTION_STATUSES`) and used correctly by the Super Admin UI.
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

### 4.2 Seed Demo Data

```bash
# Import legacy Let's Paint sample
cd backend
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/import_lets_paint_json.py \
  testdata/legacy_database_sample.json lets-paint-studio "Let's Paint Studio"

# Seed local demo tenants
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_local_test_tenants.py

# Seed randomized relational demo data
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_random_demo_data.py --students-per-tenant 24
```

### 4.3 Verify Plans

```bash
psql -h localhost -p 5432 -d studiosaas_local_test \
  -c "select code, name, student_limit, user_limit, storage_limit_mb from plans order by monthly_price_aud;"
```

Expected plans: `starter`, `studio`, `growth`.

### 4.4 Verify Tenant Workspace Mapping

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
    ├── 0002_role_model_unification.sql        # P0-01 follow-up
    └── 0003_status_enum_alignment.sql         # P0-07 follow-up
```

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
- Be safe to re-run; support baselining an existing database.

---

## 6. Data Privacy Notes

- Children's photos and personal information require special handling.
- Public artwork requires an auditable consent confirmation (`public_consent_at` + actor); withdrawing publication keeps the private portfolio item.
- Data deletion and export mechanisms must support privacy compliance.
- Support mode (platform staff viewing tenant data) must always log to `audit_logs`.
- No real children's private data should appear in demo or test databases.
