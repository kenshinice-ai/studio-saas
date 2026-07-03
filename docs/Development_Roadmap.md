# StudioSaaS Development Roadmap

Version: v3.0
Date: 2026-07-03
Purpose: Phased development plan, milestones, current status, and deployment targets.

---

## 1. Phase Overview

| Phase | Timeline | Status | Goal |
|---|---|---|---|
| Phase 0: Product Definition & Prototype | 1–2 weeks | ✅ Complete | PRD, data model, wireframes, API draft |
| Phase 1: SaaS MVP | 8–12 weeks | 🟡 In progress | Support 1–3 pilot studios |
| Phase 2: Pilot Optimization | 4–8 weeks | ⬜ Pending | Fix real-use issues, optimize UI |
| Phase 3: Commercial Release | 2–4 months | ⬜ Pending | Public website, pricing, subscriptions |
| Phase 4: Mobile App | 2–4 months | ⬜ Pending | Teacher/admin iOS app |
| Phase 5: Mature SaaS | 6–12 months | ⬜ Pending | Self-serve, billing, extensions |

---

## 2. Phase 0 — Product Definition (Complete)

**Deliverables:**
- Complete PRD (merged into `docs/StudioSaaS_Blueprint_v2.md`)
- Data model (schema v1 in `backend/db/schema_v1.sql`)
- Page wireframes (embedded in Blueprint)
- API v1 draft (documented in `docs/API.md`)
- Three-tier pricing plan
- Pilot customer interview list

**Status:** Complete. Product direction, technical direction, and local development direction are all established.

---

## 3. Phase 1 — SaaS MVP (In Progress)

**Goal:** Support 1–3 pilot studios in real use.

**Scope:**
- Multi-tenant base with `tenant_id` isolation
- Studio Admin (students, courses, packages, credits, portfolio)
- Brand customization (logo, colors, welcome, industry presets)
- Public registration page (tenant-specific)
- Parent/Student portal (balance, portfolio, registration)
- Super Admin (tenant lifecycle, plans, usage, audit)
- Tenant CMS (`/<slug>/cms`) — the core daily operating surface for studio owners
- Basic backup and export
- Basic permission controls

**Current Status (verified 2026-07-03):**

| Feature | Status | Notes |
|---|---|---|
| Multi-tenant routing | ✅ | Path, header, subdomain resolution |
| Tenant workspace generation | ✅ | From `tenant-template/` |
| PostgreSQL schema v1 | ✅ | 18 tables defined |
| Super Admin dashboard | ✅ | Create/pause/resume tenants |
| Studio Admin login | ✅ | Per-tenant login management |
| Studio CMS | ✅ | Legacy bridge with tenant routing |
| Tenant registration | ✅ | Tenant-specific registration page |
| Brand sync (Studio Admin → CMS) | ✅ | Logo, colors, welcome, industry |
| Demo data seeding | ✅ | Randomized relational data |
| Legacy smoke test | ✅ | 73 checks passing |
| Public endpoint rate limiting | ✅ | In-memory: registrations 5/min, balance 10/min, uploads 5/min |
| dict_row indexing bugs | ✅ | No tuple indexing remains in `api_v1.py` |
| Credit transaction alignment | ✅ | `(tenant_id, student_id, course_id)` conflict key in use |
| Role model consistency | ✅ | Platform admin = NULL-tenant membership (P0-01, 2026-07-03) |
| pytest infrastructure | ✅ | `pytest -q` green, 20 tests (P0-02, 2026-07-03) |
| Migration runner | ✅ | `run_migrations.py` + `schema_migrations` (P0-03, 2026-07-03) |
| Login rate limiting | ✅ | 5/min per IP+email, 30/min per IP (P0-05, 2026-07-03) |
| Route protection audit | ✅ | 146 routes audited; 12 open GET reads fixed (P0-06, 2026-07-03) |
| Registration review loop | ✅ | Duplicate detection, approve-to-student, review notes, audit (P1-04, 2026-07-03) |
| Attendance / credits closed loop | ✅ | Attendance consume/void linked to credit ledger (P1-05, 2026-07-03) |
| Media upload endpoint (v1) | ✅ | Canonical media service + `/s/<slug>/v1/media/upload` (P1-03, 2026-07-03) |
| Browser smoke tests | ❌ | Playwright — P1-06 |

---

## 4. Phase 2 — Pilot Optimization

**Timeline:** 4–8 weeks after Phase 1 completion.

**Scope:**
- Fix real-use issues from pilot studios
- Optimize UI for desktop, iPad, mobile
- Data import tool improvements
- Refined permissions (support mode + audit)
- Email notification system
- Enhanced reporting

**Key risks to address:**
- Tenant isolation testing (cross-tenant negative tests)
- Upload security (MIME, size, magic bytes, path traversal)
- Vendor JS placeholders for offline deployment
- Browser automation tests for UI regression

---

## 5. Phase 3 — Commercial Release

**Timeline:** 2–4 months after Phase 2.

**Scope:**
- Public website and pricing page
- Subscription system (Stripe integration)
- Customer self-service onboarding
- Privacy policy and terms of service
- Support backend
- System monitoring and alerting

**AWS Deployment Target:**

| Component | Local (Current) | AWS (Target) |
|---|---|---|
| PostgreSQL | Homebrew PostgreSQL 18 | RDS PostgreSQL |
| Media/Portfolio | Local file system | S3 |
| Application | Waitress/Flask local | Lightsail systemd or ECS |
| Domain/Routing | `localhost:8899` | Route 53 + CloudFront |
| Secrets | Local env vars | SSM Parameter Store / Secrets Manager |
| Email | Local SMTP (transitional) | Amazon SES |

---

## 6. Phase 4 — Mobile App

**Timeline:** 2–4 months after Phase 3.

**Priority:** Teacher/admin side first.

**Features:**
- Photo upload from camera
- Quick clock-hour deduction
- Student search
- Daily class list
- Portfolio management

**Decision:** Do not build iOS App as the first step. Web SaaS must stabilize first.

---

## 7. Phase 5 — Mature SaaS

**Timeline:** 6–12 months total.

**Features:**
- Self-service onboarding (no setup fee required)
- Automated billing and subscription management
- Multi-language support
- API rate limiting and usage analytics
- Plugin/extension system
- Advanced reporting and analytics

---

## 8. Current Sprint Priorities

See `codingprompt.md` (task definitions) and `docs/Current_Sprint.md` (status tracking) for active tasks, P0 priorities, and verification commands.

## 8.1 Target Architecture Adoption Mapping

The v2 architecture poster (see `docs/Architecture.md` §7) maps onto phases as follows:

| Target element | Phase |
|---|---|
| Module boundaries as internal package structure (modular monolith) | Phase 1–2 (P2-01) |
| Central media/File service | Phase 1 (P1-03) |
| Attendance + credit closed loop | Phase 1 (P1-05) |
| Docker, Nginx, GitHub Actions CI | Phase 3 (P3-02) |
| S3/MinIO object storage | Phase 3 (P3-03) |
| Payment (Stripe), Notification (SES), CRM, Report services | Phase 3–5 (P3-05) |
| Redis, read replicas, Elasticsearch, ClickHouse, MQ, Scheduler | Phase 5 (P3-04) — not during pilot |
| FastAPI + SQLAlchemy rewrite | Not planned — staying on Flask + psycopg through pilot |

## 9. Do-Not-Prioritize (Current Phase)

- Native iOS App (Phase 4)
- Complex scheduling system
- Full accounting system
- Stripe automatic subscription billing
- AI portfolio review
- Custom code per customer
- Complex multi-campus enterprise permissions

## 10. Key Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-06-29 | Keep `backend/` as canonical runtime | Clean separation of concerns |
| 2026-06-29 | Retain `legacy-root/` as bridge | Pragmatic transition, not deletion |
| 2026-07-01 | Close root `/register` | Each tenant has its own registration |
| 2026-07-01 | Add industry presets | Per-tenant branding customization |
| 2026-07-02 | Studio Admin and CMS share login | Unified tenant owner account |
| 2026-07-02 | Semi-service SaaS model | Easier early sales + customer onboarding |
| 2026-07-03 | Delete `docs/archive/` and `letspaint-cms-release/` | Single source of truth refactor; git history retains them |
| 2026-07-03 | Adopt v2 architecture poster as north star, modular-monolith first | Module boundaries now, heavy infra deferred |
| 2026-07-03 | Stay on Flask + psycopg through pilot (no FastAPI rewrite) | Stability over rewrite; revisit at Phase 3 |
