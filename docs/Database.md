# StudioSaaS Database

Version: v2.0
Date: 2026-07-02
Purpose: Schema definition, table descriptions, constraints, migration strategy, and operational notes.

---

## 1. Database Overview

- **Engine:** PostgreSQL 16+ (local), RDS PostgreSQL (AWS production target)
- **Local database name:** `studiosaas_local_test`
- **Schema file:** `backend/db/schema_v1.sql`
- **Isolation model:** All business data includes `tenant_id`. All queries bind tenant context.

### 1.1 Design Principles

- Soft delete or deactivate by default — no un-audited hard deletes.
- Every business table has `tenant_id` as a foreign key to `tenants.id`.
- Schema is both bootstrap and migration target; a migration runner should be added (see Risks).
- `tenant_id` is the hard isolation boundary — no cross-tenant queries.

---

## 2. Table Reference

### 2.1 Platform Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `tenants` | `id`, `slug`, `name`, `status`, `plan_code`, `primary_color`, `secondary_color`, `settings` (JSONB) | Studio tenant, slug, status, brand config, industry settings |
| `plans` | `code`, `name`, `monthly_price_aud`, `student_limit`, `user_limit`, `storage_limit_mb` | Plan definitions (starter, studio, growth) |
| `subscriptions` | `id`, `tenant_id`, `plan_code`, `status`, `billing_period`, `start_date`, `end_date` | Tenant subscription status |
| `tenant_usage` | `id`, `tenant_id`, `storage_used_mb`, `student_count`, `user_count` | Per-tenant resource usage stats |
| `audit_logs` | `id`, `tenant_id`, `user_id`, `action`, `details` (JSONB), `created_at` | Key operation audit trail |

### 2.2 User Management Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `users` | `id`, `tenant_id` (nullable), `email`, `full_name`, `status`, `password_hash`, `role` | Platform users (tenant_id null for super_admin) |
| `memberships` | `id`, `user_id`, `tenant_id`, `role` | User-tenant-role relationships |

### 2.3 Business Data Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `students` | `id`, `tenant_id`, `name`, `phone`, `email`, `status`, `tags` (JSONB) | Student profiles (soft delete) |
| `courses` | `id`, `tenant_id`, `name`, `slug`, `credits`, `price_aud_cents` | Course definitions |
| `packages` | `id`, `tenant_id`, `name`, `description`, `price_aud_cents` | Course package definitions |
| `credit_accounts` | `id`, `tenant_id`, `student_id`, `course_id`, `balance` | Student balance accounts |
| `credit_transactions` | `id`, `tenant_id`, `student_id`, `credit_account_id`, `type`, `amount`, `description` | Purchase, consume, adjust, refund logs |
| `attendance_sessions` | `id`, `tenant_id`, `student_id`, `course_id`, `date`, `status` | Class/check-in records |
| `registrations` | `id`, `tenant_id`, `parent_name`, `parent_phone`, `child_name`, `status`, `submitted_at` | Public registration applications |

### 2.4 Content Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `media_assets` | `id`, `tenant_id`, `student_id`, `filename`, `mime_type`, `size_bytes`, `url`, `is_public` | Uploaded file metadata |
| `portfolio_items` | `id`, `tenant_id`, `student_id`, `media_asset_id`, `title`, `is_public`, `created_at` | Student portfolio entries |
| `share_tokens` | `id`, `tenant_id`, `portfolio_item_id`, `token`, `expires_at` | Parent portal security tokens |

### 2.5 System Tables

| Table | Key Columns | Purpose |
|---|---|---|
| `email_templates` | `id`, `tenant_id`, `key`, `subject`, `body` | Per-tenant email templates |
| `notification_logs` | `id`, `tenant_id`, `user_id`, `template_id`, `status`, `sent_at` | Email/notification send records |

---

## 3. Key Constraints

### 3.1 Tenant Isolation

Every query on business tables must include `WHERE tenant_id = <resolved_tenant_id>`. The application layer enforces this via `tenant_context.py`. No cross-tenant queries are permitted.

### 3.2 Credit Transaction Types

Schema CHECK constraint on `credit_transactions.type`:

```
purchase, consume, adjustment, refund, expire, migration
```

API input mapping:
- `debit` → `consume`
- `adjustment_in` → `adjustment` with positive amount
- `adjustment_out` → `adjustment` with negative amount

### 3.3 Credit Account Model

Recommended: Option B — always create/fetch a default "General Class" course and use `(tenant_id, student_id, course_id)` as the unique key. This avoids `ON CONFLICT` errors and ensures deterministic balance queries.

### 3.4 Soft Delete

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

## 5. Migration Strategy (Future)

Current `schema_v1.sql` serves as both bootstrap and patch history. This should be replaced with:

```
backend/db/
├── schema_v1.sql          # Full bootstrap (read-only reference)
└── migrations/
    ├── 0001_schema_v1.sql
    ├── 0002_credit_account_constraints.sql
    ├── 0003_auth_seed_and_roles.sql
    └── 0004_tenant_presentation_backfill.sql
```

Add a `schema_migrations` table to track applied versions:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);
```

A migration runner script (`backend/scripts/run_migrations.py`) should:
- Apply pending migrations in order.
- Skip already-applied versions.
- Be safe to re-run.

---

## 6. Data Privacy Notes

- Children's photos and personal information require special handling.
- Parent consent and image privacy rules should be documented.
- Data deletion and export mechanisms must support privacy compliance.
- Support mode (platform staff viewing tenant data) must always log to `audit_logs`.
- No real children's private data should appear in demo or test databases.
