# StudioSaaS Architecture

Version: v3.0
Date: 2026-07-03
Purpose: Current system architecture, routing model, file layout, data flow — plus the target architecture (v2 vision) and its adoption policy.

---

## 1. Current System Architecture

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
├── super-admin.html              # Platform dashboard (~1685 lines)
├── start_studiosaas_local.sh     # Local startup script
├── START_STUDIOSAAS_LOCAL.command # macOS double-click launcher
│
├── backend/                      # Canonical runtime
│   ├── server.py                 # Flask application (~1560 lines)
│   ├── studiosaas/
│   │   ├── api_v1.py             # All API routes (~4040 lines — split planned, P2-01)
│   │   ├── auth.py               # Auth helpers, decorators (super_admin_required etc.)
│   │   ├── models.py             # Role/TenantStatus enums, Tenant/Actor contexts
│   │   ├── audit.py              # Audit log writer
│   │   ├── config.py             # Environment configuration
│   │   ├── db.py                 # Database connection
│   │   ├── migration.py          # Legacy data migration helpers
│   │   ├── tenant_context.py     # Tenant resolution
│   │   └── workspaces.py         # Tenant folder generation
│   ├── db/
│   │   └── schema_v1.sql         # Full schema definition (18 tables)
│   ├── scripts/
│   │   ├── seed_super_admin.py
│   │   ├── seed_local_test_tenants.py
│   │   ├── seed_random_demo_data.py
│   │   ├── import_lets_paint_json.py
│   │   ├── migrate_legacy_media.py
│   │   └── verify_local.sh
│   ├── frontend/
│   │   └── studio-admin.html     # Shared Studio Admin page (~2426 lines)
│   ├── vendor/                   # react/babel/tailwind runtime bundles (P2-03: prebuild)
│   ├── test_cms.py               # Legacy smoke test (73 checks, script-style)
│   ├── test_tenant_isolation.py  # Isolation test (script-style)
│   ├── pytest.ini
│   └── requirements.txt
│
├── legacy-root/                  # Bridge layer (transitional)
│   ├── index.html                # CMS shell with request bridge (~3668 lines)
│   └── register.html             # Register shell with request bridge (~797 lines)
│
├── tenant-template/              # Template for new tenants
│   ├── index.html
│   ├── studio-admin.html
│   └── register.html
│
├── tenants/                      # Generated tenant workspaces
│   ├── lets-paint-studio/
│   ├── lets-play-piano/
│   └── lets-play-game/
```

### 3.1 Directory Strategy

- `backend/` is the canonical runtime. The previous `letspaint-cms-release/` tree has been removed (2026-07-03, intentional).
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
| S3 | Media and portfolio storage — future (`media_assets.storage_provider` reserved) |
| CloudFront | CDN for public assets and portfolio — future |
| SES | Email delivery — future |
| Secrets Manager / SSM | Environment variables and secrets — future |

---

## 6. Known Risks and Weak Points (verified 2026-07-03)

| Area | Issue | Priority |
|---|---|---|
| Roles | Schema CHECK, Python Role enum, auth queries, and seeds disagree; `platform_super_admin`/`admin` cannot exist in DB; seed touches nonexistent `memberships.updated_at` | P0-01 |
| Testing | `pytest -q` broken: pytest not installed, duplicate key in pytest.ini, `backend/tests/` missing | P0-02 |
| Migrations | No migration runner; `schema_v1.sql` is both bootstrap and patch history | P0-03 |
| Auth | Login has no rate limiting; failed logins not audited | P0-05 |
| Route protection | ~114 routes, only 8 protection decorators; coverage unaudited | P0-06 |
| Enums | Tenant status lacks `archived`; `trial` vs `trialing`; media visibility only 2 values | P0-07 |
| Attendance | `attendance_sessions` table has zero references in `api_v1.py` — credits/attendance loop unimplemented | P1-05 |
| Legacy residue | `sw.js` still branded "Let's Paint CMS" with platform-level icon cache | P2-02 |
| Code size | `api_v1.py` is ~4040 lines — split along target module boundaries | P2-01 |
| Vendor JS | Runtime Babel/Tailwind compilation in browser | P2-03 |

Resolved since last revision: public endpoint rate limiting (in-memory), dict_row indexing bugs, portfolio DELETE mapping, credit account ON CONFLICT key, `.gitignore` baseline, HTML branding residue.

---

## 7. Target Architecture (v2 Vision)

Source: StudioSaaS v2 架构总览 (2026-07). This is the **north star**, not the current state. The diagrams below are the canonical Mermaid rendition.

### 7.1 System Overview (target)

```mermaid
flowchart TD
    subgraph Users
        V[Visitor] --- P[Parent] --- St[Student] --- T[Teacher] --- O[Studio Owner] --- SA[Super Admin]
    end
    subgraph Frontend [Frontend Web / Mobile]
        CMS[Studio CMS] --- REG[Register Portal] --- PP[Parent Portal] --- TP[Teacher Portal] --- SAD[Studio Admin] --- SUP[Super Admin UI]
    end
    GW[API Gateway / Nginx]
    subgraph Services [Backend Services]
        AUTH[Auth] --- TEN[Tenant] --- USR[User] --- STU[Student] --- CRS[Course]
        PKG[Package] --- ATT[Attendance] --- PAY[Payment] --- CRD[Credit] --- PF[Portfolio]
        CRM[CRM] --- NOT[Notification] --- RPT[Report] --- AI[AI] --- FILE[File]
    end
    subgraph Shared [Shared Services]
        REDIS[(Redis)] --- S3[(MinIO / S3)] --- MQ[Message Queue] --- SCH[Scheduler] --- AUD[Audit Log]
    end
    subgraph Data [Data Layer]
        PG[(PostgreSQL)] --- RR[(Read Replicas)] --- ES[(Elasticsearch)] --- CH[(ClickHouse)]
    end
    Users --> Frontend --> GW --> Services --> Data
    Services -.-> Shared
```

### 7.2 Module Dependencies (target)

```mermaid
flowchart TD
    AUTH[Auth Service] --> TEN[Tenant Service]
    AUTH --> USR[User Service]
    TEN --> STU[Student Service]
    TEN --> CRS[Course Service]
    USR --> STU
    USR --> PKG[Package Service]
    CRS --> ATT[Attendance Service]
    CRS --> CRD[Credit Service]
    PKG --> PAY[Payment Service]
    PKG --> PF[Portfolio Service]
    STU --> ATT
    STU --> CRM[CRM Service]
    PAY --> NOT[Notification Service]
    CRD --> RPT[Report Service]
    PF --> FILE[File Service]
    CRM --> AI[AI Service]
```

### 7.3 Key Business Flows (target — partially implemented)

```mermaid
flowchart LR
    A[Public Register] --> B[Registration Created] --> C[Studio Review] --> D{Approve?}
    D -- Yes --> E[Create Student]
    D -- No --> F[Archive]
```

```mermaid
flowchart LR
    G[Student Buys Package] --> H[Payment Success] --> I[Add Credits] --> J[Use Credits] --> K[Attend Class]
```

Flow 1 is partially implemented (registrations table + statuses exist; conversion UX is P1-04). Flow 2 is largely unimplemented past "Add Credits" — `attendance_sessions` is unused (P1-05); Payment is deferred (P3-05).

### 7.4 Adoption Policy (what to take now vs later)

| Target element | Adoption | When |
|---|---|---|
| Module boundaries (Auth/Tenant/Student/…​) | **Adopt now** as internal package structure of the Flask monolith | P2-01 split |
| File Service (central media handling) | **Adopt now** as a media service module | P1-03 |
| Attendance + Credit closed loop | **Adopt now** at business-logic level | P1-05 |
| Nginx reverse proxy, Docker, CI | Adopt at staging prep | P3-02 |
| S3/MinIO object storage | Adopt via `storage_provider` branch | P3-03 |
| Redis, read replicas, Elasticsearch, ClickHouse, MQ, Scheduler | **Do not introduce during pilot** | P3-04 / Phase 5 |
| Payment, CRM, Notification, Report, AI services | Deferred, pilot-feedback driven | P3-05 / Phase 3+ |
| FastAPI + SQLAlchemy (poster tech stack) | **Not adopted** — staying on Flask + psycopg through pilot; revisit at Phase 3 | Decision log 2026-07-03 |
| Poster ER diagram (e.g. `users.role`) | **Not canonical** — actual schema keeps roles on `memberships`; `backend/db/schema_v1.sql` wins | — |

---

## 8. Future Architecture Goals

- Split `api_v1.py` into modular route files (`routes/`, `services/`) along §7.2 boundaries.
- Add migration runner (`backend/db/migrations/`, P0-03).
- Add v1 media upload endpoint for portfolio assets (P1-03).
- Add browser automation smoke tests (Playwright, P1-06).
- Replace legacy bridge with modern frontend build.
- Migrate from local PostgreSQL to RDS, local files to S3.
- Add support mode with audit trail for platform staff accessing tenant data.
