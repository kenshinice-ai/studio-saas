# StudioSaaS Tenant Routing and File Structure

This document describes the local URL model, tenant workspace files, and the
relationship between platform data and tenant CMS pages.

## URL Model

## Product Roles

- Super Admin is for the StudioSaaS owner/operator. It manages tenant accounts,
  subscription status, plan assignment, plan limits, billing periods, ownership
  contacts, ABN, and audit activity.
- Studio Admin is for each studio owner or manager. It manages that studio's
  CMS/Register presentation, including logo upload, public contact details,
  theme colors, welcome copy, courses, and packages.
- CMS and Register pages are the end-user surfaces for teachers, staff,
  parents, and students. They consume tenant branding and public settings
  configured in Studio Admin.

Platform routes:

- `/` - Super Admin dashboard.
- `/super-admin` - Super Admin dashboard alias.
- `/register` - not a public page; registration must use a tenant URL.
- `/v1/*` - platform and tenant API v1.

Tenant routes:

- `/<tenant_slug>` - tenant CMS address; serves the same CMS shell as `/<tenant_slug>/cms`.
- `/<tenant_slug>/cms` - tenant CMS address; canonical explicit CMS route.
- `/<tenant_slug>/studio-admin` - tenant-specific Studio Admin launcher.
- `/<tenant_slug>/register` - tenant-specific registration launcher.
- `/s/<tenant_slug>/v1/*` - tenant-scoped API route prefix.

Examples:

- `/lets-paint-studio`
- `/lets-paint-studio/studio-admin`
- `/lets-paint-studio/register`
- `/lets-play-piano`

Reserved slugs such as `api`, `v1`, `register`, `super-admin`, `studio-admin`,
`vendor`, and asset filenames cannot be used as tenant slugs.

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

Runtime legacy bridge shells live here:

```text
/Users/llmacbookpro/Documents/studiosaas/legacy-root/
  index.html
  register.html
```

`legacy-root/index.html` and `legacy-root/register.html` are still used while
the PostgreSQL-backed SaaS pages are being built. They are not exposed as
root-level pages. `/<tenant_slug>` and `/<tenant_slug>/cms` both serve
`legacy-root/index.html` so each tenant has one consistent CMS implementation.
Each shell includes a small request bridge:
legacy `/api/data`, `/api/save`, `/api/register`, and `/api/balance` calls are
rewritten to tenant-scoped StudioSaaS endpoints.

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
/Users/llmacbookpro/Documents/studiosaas/backend/
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

## Studio Admin to CMS Sync Map

Studio Admin is the tenant owner's control surface. CMS and Register are the
published tenant surfaces. The intended data path is:

```text
Studio Admin -> /s/<tenant_slug>/v1/* -> PostgreSQL tenant_id rows -> CMS/Register
```

Current field mapping:

| Studio Admin area | API/database source | CMS/Register consumer |
| --- | --- | --- |
| Studio name | `PATCH /s/<slug>/v1/tenant` -> `tenants.name` | `/v1/public/<slug>/brand`, tenant CMS wrapper, Register wrapper |
| Logo | upload `/v1/tenant/logo`, then `tenants.settings.logo_url` | CMS/Register logo replacement and document title |
| Primary/secondary colors | `tenants.primary_color`, `tenants.secondary_color` | CMS/Register CSS variables and theme color |
| Welcome message | `tenants.welcome_message` | public brand payload, tenant CMS wrapper, Register wrapper |
| CMS layout | `tenants.settings.cms_layout` through `/tenant` | tenant CMS wrapper and Register wrapper (`bar`, `hero`, `compact`) |
| Show welcome | `tenants.settings.show_welcome` through `/tenant` | controls welcome message visibility on CMS/Register wrappers |
| Studio category | `tenants.settings.category` | Super Admin preset selection; Studio Admin tenant-controlled industry mode |
| Public slogan | `tenants.settings.slogan` | CMS login surfaces, Register header, tenant wrappers, growth report output |
| Registration profile | `tenants.settings.registration_profile` | Register preference section labels/placeholders, legacy CMS new/edit/pending preference panels, and submitted `preferences` payload |
| Copy pack | `tenants.settings.copy_pack` | public portal label and Register intro copy |
| Public phone/email/address | `tenants.contact_phone`, `tenants.contact_email`, `tenants.address` | tenant wrapper contact strip and public brand payload |
| Courses | `/s/<slug>/v1/courses` -> `courses` | Studio Admin course management; legacy CMS bridge creates `General Class` for balance accounts |
| Packages | `/s/<slug>/v1/packages` -> `packages` | legacy CMS `/api/data` bridge exposes `packages`; legacy `/api/save` writes package edits back |
| Students | legacy CMS `/api/save` bridge -> `students` | legacy CMS `/api/data` bridge returns tenant-scoped students |
| Student balances | legacy CMS `/api/save` bridge -> `credit_accounts` | legacy CMS `/api/data`; Register balance query via `/v1/public/<slug>/balance-query` |
| Registrations | Register bridge -> `/v1/public/<slug>/registrations` -> `registrations` | Studio Admin `/s/<slug>/v1/registrations` and legacy CMS pending queue |

The legacy CMS shell still contains old calls to `/api/data` and `/api/save`.
Inside tenant routes, `legacy-root/index.html` intercepts those calls and sends
them to `/s/<tenant_slug>/v1/legacy-cms/data` and
`/s/<tenant_slug>/v1/legacy-cms/save`. This keeps the old UI usable while
preventing tenant business data from returning to the single-studio
`database.json` path.

The legacy Register shell still contains old calls to `/api/register` and
`/api/balance`. Inside tenant register routes, `legacy-root/register.html`
intercepts those calls and sends them to `/v1/public/<tenant_slug>/registrations`
and `/v1/public/<tenant_slug>/balance-query`.

`/v1/tenant/settings` remains available only as a compatibility alias. It writes
through the same update path as `/v1/tenant`, so older callers no longer update
JSON-only settings that CMS/Register cannot see.

## Route to File Mapping

| URL | File served | Tenant source |
| --- | --- | --- |
| `/` | `super-admin.html` | platform-wide |
| `/super-admin` | `super-admin.html` | platform-wide |
| `/register` | 404 JSON hint | none |
| `/<tenant_slug>` | `legacy-root/index.html` | `tenants/<tenant_slug>/tenant.json` and `tenants.slug` |
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

- The old Let’s Paint CMS is still available inside each tenant CMS wrapper.
- The long-term direction is to move all tenant CMS behavior to PostgreSQL-backed
  `/v1` APIs and eventually retire the single JSON CMS database.
