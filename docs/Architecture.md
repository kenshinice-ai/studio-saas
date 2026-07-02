# StudioSaaS Architecture

Version: v2.0
Date: 2026-07-02
Purpose: System architecture, routing model, file layout, data flow, and integration points.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (Desktop / iPad / Mobile)                          │
└──────┬──────────────────────┬───────────────────┬──────────┘
       │                      │                   │
       ▼                      ▼                   ▼
┌─────────────┐   ┌──────────────────┐  ┌─────────────────┐
│ Super Admin │   │  Studio Admin    │  │  Parent Portal  │
│  Dashboard  │   │   (per tenant)   │  │   (public)      │
└──────┬──────┘   └────────┬─────────┘  └────────┬────────┘
       │                   │                      │
       └───────────────────┼──────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Flask API  │
                    │  server.py  │
                    │  /v1/*      │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌───────────┐
       │Tenants   │ │Students  │ │ Portfolios│
       │Plans     │ │Courses   │ │Media      │
       │Subscriptions│Packages │ │Registrations│
       │AuditLogs  │ │Credits   │ │ShareTokens │
       └──────────┘ └──────────┘ └───────────┘
              ▲
              │
       ┌──────▼──────┐
       │ PostgreSQL  │
       │ (RDS later) │
       └─────────────┘
```

### 1.1 Architecture Principles

- `backend/` is the canonical runtime directory.
- `tenant_id` is the isolation boundary for all business data.
- Tenant context is resolved from URL path, header, or subdomain — never from request body.
- Every mutation route must be authenticated unless explicitly public.
- Legacy CMS bridge (`legacy-root/`) is a transitional layer, not a permanent feature.

---

## 2. URL Model

### 2.1 Platform Routes

| Route | Surface |
|---|---|
| `/` | Super Admin dashboard |
| `/super-admin` | Super Admin dashboard (alias) |
| `/register` | Closed (404) — registration belongs to tenants |
| `/v1/*` | Platform and tenant API v1 |

### 2.2 Tenant Routes

| Route | Surface |
|---|---|
| `/<tenant_slug>` | Tenant CMS (serves `legacy-root/index.html`) |
| `/<tenant_slug>/cms` | Tenant CMS (explicit, same shell) |
| `/<tenant_slug>/studio-admin` | Tenant Studio Admin |
| `/<tenant_slug>/register` | Tenant registration |
| `/s/<tenant_slug>/v1/*` | Tenant-scoped API prefix |

### 2.3 Reserved Slugs

`api`, `v1`, `register`, `super-admin`, `studio-admin`, `vendor`, and asset filenames cannot be used as tenant slugs.

### 2.4 Tenant Resolution Order

1. `/s/{tenant_slug}/...` (path-based)
2. `X-Tenant-Slug` header
3. Subdomain (e.g., `lets-paint.studiosa.as`) — future

---

## 3. File Structure

```
studiosaas/
├── super-admin.html              # Platform dashboard (root)
├── start_studiosaas_local.sh     # Local startup script
├── START_STUDIOSAAS_LOCAL.command # macOS double-click launcher
│
├── backend/                      # Canonical runtime
│   ├── server.py                 # Flask application
│   ├── studiosaas/
│   │   ├── api_v1.py             # All API routes (~2200 lines)
│   │   ├── auth.py               # Auth helpers (placeholder)
│   │   ├── db.py                 # Database connection
│   │   ├── tenant_context.py     # Tenant resolution
│   │   └── workspaces.py         # Tenant folder generation
│   ├── db/
│   │   └── schema_v1.sql         # Full schema definition
│   ├── scripts/
│   │   ├── seed_super_admin.py   # Super Admin seed script
│   │   ├── seed_local_test_tenants.py
│   │   ├── seed_random_demo_data.py
│   │   ├── import_lets_paint_json.py
│   │   └── verify_local.sh       # Verification script
│   ├── frontend/
│   │   └── studio-admin.html     # Shared Studio Admin page
│   ├── test_cms.py               # Legacy smoke test (73 checks)
│   └── requirements.txt
│
├── legacy-root/                  # Bridge layer (transitional)
│   ├── index.html                # CMS shell with request bridge
│   └── register.html             # Register shell with request bridge
│
├── tenant-template/              # Template for new tenants
│   ├── index.html
│   ├── studio-admin.html
│   └── register.html
│
├── tenants/                      # Generated tenant workspaces
│   ├── lets-paint-studio/
│   │   ├── index.html
│   │   ├── studio-admin.html
│   │   ├── register.html
│   │   └── tenant.json
│   ├── lets-play-piano/
│   └── lets-play-game/
```

### 3.1 Directory Strategy

- `backend/` is the canonical runtime. The previous `letspaint-cms-release/` tree has been superseded.
- `legacy-root/` is a runtime bridge, not an archive. Tenant wrappers use it to host the old CMS/Register UI while request interception routes data into tenant-scoped PostgreSQL APIs.
- `tenant-template/` is the template source. When a tenant is created, StudioSaaS copies these files into `tenants/<slug>/` and renders `{{TENANT_SLUG}}` and `{{TENANT_NAME}}`.
- `tenants/<slug>/` are generated workspaces, one per tenant.

---

## 4. Data Flow

### 4.1 Tenant Creation Flow

1. Super Admin creates tenant with name, slug, plan, status, and subscription dates.
2. API validates the slug against reserved words.
3. API inserts `tenants`, `subscriptions`, and `tenant_usage` rows.
4. API creates `tenants/<slug>/` from `tenant-template/`.
5. API stores `settings.workspace_path` on the tenant row.
6. Audit log records `tenant.created`.

### 4.2 Studio Admin to CMS Sync

```
Studio Admin → /s/<tenant_slug>/v1/* → PostgreSQL tenant_id rows → CMS/Register
```

| Studio Admin area | API/database source | CMS/Register consumer |
|---|---|---|
| Studio name | `PATCH /s/<slug>/v1/tenant` → `tenants.name` | `/v1/public/<slug>/brand`, CMS/Register wrapper |
| Logo | upload `/v1/tenant/logo` → `tenants.settings.logo_url` | CMS/Register logo replacement |
| Primary/secondary colors | `tenants.primary_color`, `tenants.secondary_color` | CMS/Register CSS variables |
| Welcome message | `tenants.welcome_message` | Public brand payload, CMS/Register |
| CMS layout | `tenants.settings.cms_layout` | CMS/Register wrapper (`bar`, `hero`, `compact`) |
| Show welcome | `tenants.settings.show_welcome` | Controls welcome visibility |
| Industry category | `tenants.settings.category` | Super Admin preset; Studio Admin industry mode |
| Public slogan | `tenants.settings.slogan` | CMS login surfaces, Register header |
| Registration profile | `tenants.settings.registration_profile` | Register form labels/placeholders |
| Copy pack | `tenants.settings.copy_pack` | Public portal labels, Register intro |
| Contact phone/email/address | `tenants.contact_*` | Tenant wrapper contact strip |
| Courses | `/s/<slug>/v1/courses` → `courses` | Studio Admin course management |
| Packages | `/s/<slug>/v1/packages` → `packages` | Legacy CMS bridge exposes packages |
| Students | Legacy CMS bridge → `students` | Legacy CMS returns tenant-scoped students |
| Student balances | Legacy CMS bridge → `credit_accounts` | Register balance query |
| Registrations | Register bridge → `/v1/public/<slug>/registrations` | Studio Admin pending queue |

### 4.3 Legacy Bridge Integration

The legacy CMS shell (`legacy-root/index.html`) intercepts old calls to `/api/data` and `/api/save` and rewrites them to `/s/<tenant_slug>/v1/legacy-cms/data` and `/s/<tenant_slug>/v1/legacy-cms/save`. This keeps the old UI usable while preventing tenant business data from returning to the single-studio JSON path.

The legacy Register shell (`legacy-root/register.html`) intercepts `/api/register` and `/api/balance` and rewrites them to `/v1/public/<tenant_slug>/registrations` and `/v1/public/<tenant_slug>/balance-query`.

---

## 5. Integration Points

| Component | Integration |
|---|---|
| PostgreSQL (local) | Homebrew PostgreSQL 16+/18, database `studiosaas_local_test` |
| PostgreSQL (AWS) | RDS PostgreSQL — future production |
| S3 | Media and portfolio storage — future production |
| CloudFront | CDN for public assets and portfolio — future |
| SES | Email delivery — future |
| Secrets Manager / SSM | Environment variables and secrets — future |

---

## 6. Known Risks and Weak Points

| Area | Issue | Priority |
|---|---|---|
| Auth | `auth.py` is mostly a placeholder; v1 route protection not fully wired | P0 |
| Admin API | Super Admin and Studio Admin mutations lack role checks on some routes | P0 |
| DB integrity | Some app-level assumptions are not enforced by schema constraints | P1 |
| Runtime bugs | Several v1 POST endpoints use tuple indexing on dict rows | P0 |
| Credit logic | API transaction names do not match schema CHECK values | P0 |
| Privacy | Parent balance query is public, not rate-limited in v1 | P0 |
| Legacy residue | `legacy-root/` still has visible "Let's Paint" strings | P1 |
| Repository hygiene | `.api_secret`, `.cms_password` must be in `.gitignore` | P0 |
| Code size | `api_v1.py` is 2200+ lines — should be split before unmaintainable | P2 |

Full risk assessment: see `docs/archive/StudioSaaS_Code_Review_Bug_Risk_Scan_v1.md`.

---

## 7. Future Architecture Goals

- Split `api_v1.py` into modular route files (`routes/`, `services/`).
- Add migration runner (`backend/db/migrations/`).
- Add v1 media upload endpoint for portfolio assets.
- Add browser automation smoke tests (Playwright/Selenium).
- Replace legacy bridge with modern frontend build.
- Migrate from local PostgreSQL to RDS, local files to S3.
- Add support mode with audit trail for platform staff accessing tenant data.
