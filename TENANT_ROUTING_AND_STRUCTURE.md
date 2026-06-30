# StudioSaaS Tenant Routing and File Structure

This document describes the local URL model, tenant workspace files, and the
relationship between platform data and tenant CMS pages.

## URL Model

Platform routes:

- `/` - Super Admin dashboard.
- `/super-admin` - Super Admin dashboard alias.
- `/register` - not a public page; registration must use a tenant URL.
- `/v1/*` - platform and tenant API v1.

Tenant routes:

- `/<tenant_slug>` - tenant CMS address.
- `/<tenant_slug>/cms` - internal legacy CMS shell used by the tenant wrapper.
- `/<tenant_slug>/studio-admin` - tenant-specific Studio Admin launcher.
- `/<tenant_slug>/register` - tenant-specific registration launcher.
- `/s/<tenant_slug>/v1/*` - tenant-scoped API route prefix.

Examples:

- `/lets-paint-studio`
- `/lets-paint-studio/studio-admin`
- `/lets-paint-studio/register`
- `/lets-play-piano`

Reserved slugs such as `api`, `v1`, `register`, `super-admin`, `studio-admin`,
`parent-portal`, `vendor`, and asset filenames cannot be used as tenant slugs.

## File Structure

The product root is:

```text
/Users/llmacbookpro/Documents/studiosaas/
```

Platform files live at the project root:

```text
/Users/llmacbookpro/Documents/studiosaas/
  super-admin.html
```

Archived single-tenant shells live here:

```text
/Users/llmacbookpro/Documents/studiosaas/legacy-root/
  index.html
  register.html
  super-admin-old.html
```

`legacy-root/index.html` and `legacy-root/register.html` are still used by
tenant wrappers while the PostgreSQL-backed SaaS pages are being built. They
are not exposed as root-level pages.

Tenant templates live here:

```text
/Users/llmacbookpro/Documents/studiosaas/tenant-template/
  index.html
  studio-admin.html
  register.html
```

Generated tenant workspaces live here:

```text
/Users/llmacbookpro/Documents/studiosaas/tenants/<tenant_slug>/
  index.html
  studio-admin.html
  register.html
  tenant.json
```

Backend/runtime files remain in:

```text
/Users/llmacbookpro/Documents/studiosaas/letspaint-cms-release/
  server.py
  studiosaas/
  db/
  scripts/
  frontend/studio-admin.html
```

When a tenant is created through the Super Admin API or imported through the
legacy importer, StudioSaaS copies the template files into a tenant folder and
renders `{{TENANT_SLUG}}` and `{{TENANT_NAME}}`.

## Database Relationship

The platform database is PostgreSQL. It remains the source of truth for:

- `tenants`
- `plans`
- `subscriptions`
- `tenant_usage`
- `audit_logs`

Tenant-owned business data also stays in PostgreSQL and is isolated by
`tenant_id`:

- `students`
- `courses`
- `packages`
- `credit_accounts`
- `credit_transactions`
- `registrations`
- `media_assets`
- `portfolio_items`

The tenant filesystem workspace is linked from the tenant record:

```sql
select slug, settings->>'workspace_path'
from tenants;
```

Example:

```text
lets-paint-studio -> tenants/lets-paint-studio
lets-play-piano   -> tenants/lets-play-piano
```

This keeps the database normalized while still giving every customer an
individual URL and folder.

## Route to File Mapping

| URL | File served | Tenant source |
| --- | --- | --- |
| `/` | `super-admin.html` | platform-wide |
| `/super-admin` | `super-admin.html` | platform-wide |
| `/register` | 404 JSON hint | none |
| `/<tenant_slug>` | `tenants/<tenant_slug>/index.html` | `tenants.slug` |
| `/<tenant_slug>/cms` | `legacy-root/index.html` | `tenants/<tenant_slug>/tenant.json` and `tenants.slug` |
| `/<tenant_slug>/studio-admin` | `tenants/<tenant_slug>/studio-admin.html` | `tenants.slug` |
| `/<tenant_slug>/register` | `tenants/<tenant_slug>/register.html` | `tenants.slug` |
| `/_legacy/register` | `legacy-root/register.html` | tenant query parameter from wrapper |
| `/v1/*` | API blueprint | header, host, or path tenant context |
| `/s/<tenant_slug>/v1/*` | API blueprint | path tenant context |

## Tenant Creation Flow

1. Super Admin creates tenant with name, slug, plan, status, and subscription dates.
2. API validates the slug and reserved words.
3. API inserts `tenants`, `subscriptions`, and `tenant_usage` rows.
4. API creates `tenants/<slug>/` from `tenant-template/`.
5. API stores `settings.workspace_path` on the tenant row.
6. Audit log records `tenant.created`.

The same workspace generation is used by `scripts/import_lets_paint_json.py`.

## Notes

- `/parent-portal` is temporarily removed from active routing.
- The old Let’s Paint CMS is still available inside each tenant CMS wrapper.
- The long-term direction is to move all tenant CMS behavior to PostgreSQL-backed
  `/v1` APIs and eventually retire the single JSON CMS database.
