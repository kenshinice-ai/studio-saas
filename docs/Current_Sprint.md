# StudioSaaS Current Sprint

Version: v4.0
Date: 2026-07-09
Purpose: Status tracking for the prioritised task list in `codingprompt.md` (same numbering), verification commands, credentials, and go/no-go criteria.

> Task definitions (problem/evidence/fix/verify) live in `codingprompt.md`. This file tracks **status only**. Update it after each completed task.

---

## 1. Sprint Overview

**Current Status:** Phase 2 — Public pilot via Cloudflare Tunnel (v6 harvest complete 2026-07-08; tunnel live 2026-07-09)
**Focus:** Deployment hardening per `codingprompt.md` v7 — public-pilot security baseline, then AWS readiness (`docs/Deployment.md`).

**Key principle:** Do not add features before tenant isolation, upload security, auth roles, backup/restore, and browser smoke testing are solid.

---

## 2. Verified Fixed (2026-07-03 code-level audit)

These items from earlier sprint docs are confirmed done — do not re-fix:

| Legacy ID (v2 doc) | Item | Evidence |
|---|---|---|
| P0-01 (old) | Auth login `password_hash` SELECT bug | Fixed per code; runtime re-test pending under new P0-06 audit |
| P0-04 (old) | dict_row tuple-indexing crashes | No `fetchone()[0]` / `row[0]` remain in `api_v1.py` |
| P0-05 (old) | Credit account ON CONFLICT mismatch | `ON CONFLICT (tenant_id, student_id, course_id)` at `api_v1.py:2482` |
| P0-06 (old) | Portfolio DELETE mapped to update | Separate DELETE route at `api_v1.py:3473` |
| P0-07 (old) | Public endpoint rate limiting | Implemented in-memory: registrations 5/min, balance-query 10/min, uploads 5/min |
| P1-03 (old) | Visible "Let's Paint" branding in HTML | Zero matches in HTML surfaces; only `sw.js` remains (new P2-02) |

---

## 3. Active Task Status (numbering = codingprompt.md v2)

### P0 — Data consistency and security

| ID | Task | Status |
|---|---|---|
| P0-01 | Unify role model — enum matches CHECK; platform admin = `tenant_id IS NULL` membership; seed fixed | ✅ Done 2026-07-03 |
| P0-02 | Fix pytest — requirements-dev, clean pytest.ini, `backend/tests/` (20 tests) | ✅ Done 2026-07-03 |
| P0-03 | Migration runner — `migrations/0001+0002`, `schema_migrations`, `run_migrations.py` (`--baseline`, `--dry-run`) | ✅ Done 2026-07-03 |
| P0-04 | Repo hygiene — deletions committed, `backend/` now tracked (was never in git!), checkpoints ignored | ✅ Done 2026-07-03 |
| P0-05 | Login rate limiting (5/min per IP+email, 30/min per IP) + legacy-login failure audit | ✅ Done 2026-07-03 |
| P0-06 | Route audit (146 routes): mutations were safe; 12 unauthenticated tenant GET reads fixed | ✅ Done 2026-07-03 |
| P0-07 | Enum alignment verified; `archived`/`trialing` decisions recorded in Database.md §3 | ✅ Done 2026-07-03 |

### v6.6.6 Harvest — codingprompt v6 (2026-07-06)

| ID | Task | Status |
|---|---|---|
| S1 | SW no longer intercepts non-GET (iOS upload body loss); scope tightened per tenant page, root registrations unregistered | ✅ |
| S2 | iPhone HEIC/HEIF uploads: server-side JPEG conversion (pillow-heif) in media service | ✅ |
| S3 | Lazy 360px thumbnails (`?thumb=1`) for CMS portfolio grid + shared portfolio page | ✅ |
| S4 | Registration honeypot (silent bot drop) + privacy consent checkbox | ✅ |
| S5 | verify_local.sh: compiled-bundle syntax check + forgot-to-build detection | ✅ |
| A1 | Attendance accounted on class_date (make-up check-ins land on the right day) | ✅ 2026-07-08 |
| A2+A4 | 退款退课 (negative-fee revenue netting, signed ledger) + settle-page mode toggle, recent-3, confirm cards | ✅ 2026-07-08 |
| A3 | 经营真账 dashboard card (attended, avg price, earned vs prepaid liability vs cash) | ✅ 2026-07-08 |
| A5 | Pre-class low-balance warning + one-tap 催费 copy | ✅ 2026-07-08 |
| B1 | Roster workbench: date quick-nav, mini week view, day overview bar | ✅ 2026-07-08 |
| B2 | Schedule conflict + duplicate warnings | ✅ 2026-07-08 |
| B3 | Student profile 上课记录 (by class_date) | ✅ 2026-07-08 |
| B4 | Artwork 标题+老师评语 end to end (CMS + share page) | ✅ 2026-07-08 |
| B5 | EmptyState component, Enter-to-open search, filter count/clear | ✅ 2026-07-08 |
| B6 | Dark mode (system-following CSS layer, harvested v5.0.x) | ✅ 2026-07-08 |
| — | Bonus: /vendor CWD 404 fixed + real pinned react/tailwind bundles | ✅ 2026-07-08 |

### Deployment Sprint — codingprompt v7 (2026-07-09)

| ID | Task | Status |
|---|---|---|
| D1 | v1 API rate limiting/audit use real client IP behind cloudflared (`_client_ip()` trusts CF-Connecting-IP only from localhost; audit inet validated) | ✅ 2026-07-09 |
| D2 | Cloudflare Tunnel `studiosaas` → `https://studiosaas.cc.cd` → localhost:8899 (locally-managed, config in `~/.cloudflared/config.yml`) | ✅ 2026-07-09 |
| P0-1 | Rotate default `admin123456` on all 7 privileged accounts → `~/.studiosaas/pilot-credentials.txt`; LOCAL start script preserves rotated password | ✅ 2026-07-09 |
| P0-2 | Tunnel-origin session cookies carry Secure (custom SessionInterface); local http unaffected | ✅ 2026-07-09 |
| P0-3 | One-click backup (`BACKUP_STUDIOSAAS_NOW.command`, keep 14) + restore drill passed (restore-dry-run, 10 migrations verified) | ✅ 2026-07-09 |
| P0-4 | On-demand ONLINE/STOP `.command` scripts (user chose no persistent daemons); LaunchAgent templates in `deploy/launchd/` if ever needed | ✅ 2026-07-09 |
| P0-5 | Cloudflare Access email-OTP policy on `/super-admin*` | ⚠️ manual dashboard step (Zero Trust → Access → Applications; self-hosted app for `studiosaas.cc.cd/super-admin*` + `/` root alias) |

### Product rename + tenant portal (2026-07-09, user-directed)

| Item | Status |
|---|---|
| Display rename → **PWE Studio SaaS** (titles, super-admin h1, health `service`, manifests, README; internal identifiers `STUDIOSAAS_*`/CSRF value/domain unchanged) | ✅ |
| Passwords reverted to `admin123456` (test-only pilot, owner decision) | ✅ |
| Super-admin quick links: Portal `/slug` + CMS `/slug/cms` + Admin + Register (was: "CMS" mislinked to `/slug`) | ✅ |
| Tenant portal v2: `tenant-template/index.html` rebuilt on the LetsPaint v6.6.6 portal design — bilingual SPA (home/join/my/privacy), brand/programs from v1 public APIs, in-page enrolment (honeypot+consent) and student area (balance + portfolio thumbs) | ✅ |
| lets-paint-studio keeps the full-content portal (artist/FAQ/contact), rewired to v1 endpoints | ✅ |
| `/slug/cms/studio-admin` → 302 alias to `/slug/studio-admin` | ✅ |
| CSRF guard: `/v1/public/*` exempt (session-holding staff were 403-blocked on public portal forms) | ✅ |

### CMS Core Sprint — codingprompt v5 (2026-07-04)

| ID | Task | Status |
|---|---|---|
| A1 | Weekly class schedules (排课): class_schedules + CMS 每周课表 view, auto day-roster, template conversion | ✅ |
| A2 | Unified ledger: CMS check-in/top-up/adjust → v1 attendance & credit endpoints; account consolidation (0007); roster persistence | ✅ |
| A3 | CMS precompiled: JSX source at legacy-root/src/cms-app.jsx, esbuild via scripts/build_cms.sh, no in-browser Babel | ✅ |
| A4 | CMS pending tab → v1 registration state machine (approve creates student + parent email; reject with note) | ✅ |
| A5 | Surface links: CMS↔studio-admin, landing→CMS login; docs reposition CMS as core surface | ✅ |
| B1-B4 | 费用提醒 / 生日流失运营 / staff 账号 / 备份对接 | ❌ next |

### A/B Sprint — codingprompt v3 (completed 2026-07-03)

| ID | Task | Status |
|---|---|---|
| A1 | Commit in-flight work; tenants/ tracking policy; dance-dance seeded (`--only-slug`) | ✅ |
| A2 | last_login tracking + one-time password setup links (migration 0006) | ✅ |
| A3 | Server-side pagination for students/registrations + UI pager | ✅ |
| A4 | CSRF guard (X-Requested-With on cookie-authed v1 mutations) | ✅ |
| A5 | Login UX (remember me, 429, pw toggle) + idle session policy 24h/30d | ✅ |
| A6 | Shared /assets/ui-common.js (esc + fetch patch) + escaping check in verify | ✅ |
| B1 | CSV export: students / registrations / credit ledger (audited) | ✅ |
| B2 | Durable portfolio share links + /shared/portfolio public viewer | ✅ |
| B3 | Email notifications v1 (console/SMTP; registration received/approved/rejected) | ✅ |
| B4 | Support mode with mandatory reason + audit tagging + banner | ✅ |
| B5 | Tenant root = public landing page; /v1/public/<slug>/programs; CMS stays at /cms | ✅ |

### P1 — Engineering quality and business loops

| ID | Task | Status |
|---|---|---|
| P1-01 | Documentation sync | ✅ Done 2026-07-03 (this refresh) |
| P1-02 | Tenant isolation negative test matrix | ✅ Done 2026-07-03 (`test_tenant_isolation.py`, 63+ checks) |
| P1-03 | v1 media upload endpoint + central media service | ✅ Done 2026-07-03 |
| P1-04 | Registration review → student conversion loop | ✅ Done 2026-07-03 (duplicate detection, student link, review notes, audit) |
| P1-05 | Credits closed loop + attendance | ✅ Done 2026-07-03 |
| P1-06 | Playwright browser smoke tests | ❌ |
| P1-07 | Backup/restore script + runbook | ✅ Done 2026-07-03 |

### P2 — Structure and UI (after P0 is green)

| ID | Task | Status |
|---|---|---|
| P2-01 | Split `api_v1.py` (4040 lines) along target-architecture module boundaries | ❌ |
| P2-02 | Multi-tenant PWA/sw.js (last "Let's Paint" residue) | ❌ |
| P2-03 | Replace runtime Babel/Tailwind vendor JS with prebuilt assets | ❌ |
| P2-04 | Super Admin platform cockpit | ❌ |
| P2-05 | Studio Admin workflow reorganisation | ❌ |
| P2-06 | Shared design tokens from `docs/Design_System.md` | ❌ |

### P3 — Platform and deployment

| ID | Task | Status |
|---|---|---|
| P3-01 | Config layering + secure cookies + structured logging | ❌ |
| P3-02 | Docker + Nginx + GitHub Actions CI | ❌ |
| P3-03 | S3/MinIO media storage branch | ❌ |
| P3-04 | Long-term data infra (Redis/replicas/ES/ClickHouse/MQ) — explicitly deferred | ⏸ Deferred |
| P3-05 | Extension services (Payment/CRM/Notification/Report/AI) — pilot-feedback driven | ⏸ Deferred |

---

## 4. Verification Commands

### Full verification

```bash
bash backend/scripts/verify_local.sh
```

### Syntax check

```bash
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py backend/test_cms.py
```

### Script-style smoke tests

```bash
cd backend && ../.venv/bin/python test_cms.py
# Expected: 72 checks passing, 0 failing
cd backend && ../.venv/bin/python test_tenant_isolation.py
```

### Pytest (after P0-02 lands)

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

### API health check

```bash
curl -sS http://localhost:8899/v1/health
```

### Auth test (local)

```bash
# Login
curl -i -c /tmp/studiosaas.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/v1/auth/login \
  -d '{"email":"admin@studiosaas.local","password":"admin123456"}'

# Check session
curl -i -b /tmp/studiosaas.cookies http://localhost:8899/v1/auth/me

# Logout (cookie-authenticated mutations need the CSRF header)
curl -i -b /tmp/studiosaas.cookies -H 'X-Requested-With: StudioSaaS' \
  -X POST http://localhost:8899/v1/auth/logout
```

> **CSRF note (A4):** any mutation sent **with a session cookie** must include
> `-H 'X-Requested-With: StudioSaaS'` or it returns 403. Unauthenticated and
> public calls are unaffected.

### Tenant mutation without auth (must fail)

```bash
curl -i -X POST http://localhost:8899/v1/admin/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Bad Tenant","slug":"bad-tenant","planCode":"starter"}'
# Expected: 401

curl -i -X PATCH http://localhost:8899/s/lets-paint-studio/v1/tenant \
  -H 'Content-Type: application/json' \
  -d '{"name":"Hacked"}'
# Expected: 401 or 403
```

### Page open tests

```bash
# All should return 200
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/studio-admin
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/cms
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/studio-admin
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/register
# /register should return 404
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/register
```

---

## 5. Default Credentials (Local)

> **P0-1 rotation reverted 2026-07-09 (owner decision):** the pilot is test-only, so all seven privileged accounts are back on `admin123456`. Re-rotate before inviting real users (P0-5 Cloudflare Access on /super-admin is the compensating control until then).

### Super Admin

| Field | Value |
|---|---|
| Email | `admin@studiosaas.local` |
| Password | `admin123456` |

Reset command:

```bash
cd backend
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_super_admin.py --reset-password \
  --email admin@studiosaas.local --password admin123456
```

Password storage: seed/reset scripts write PBKDF2-HMAC-SHA256 hashes. Legacy unsalted SHA-256 user hashes are verified only to complete a successful login, then upgraded in place.

### Studio Admin (Demo Tenants)

| Tenant | Email | Password |
|---|---|---|
| `lets-paint-studio` | `owner@lets-paint-studio.test` | `admin123456` |
| `lets-play-piano` | `owner@lets-play-piano.test` | `admin123456` |
| `lets-play-game` | `owner@lets-play-game.test` | `admin123456` |

---

## 6. Core Files To Recheck After Future Changes

- `backend/studiosaas/api_v1.py`
- `backend/studiosaas/auth.py`
- `backend/studiosaas/models.py`
- `backend/db/schema_v1.sql`
- `backend/frontend/studio-admin.html`
- `super-admin.html`
- `tenant-template/*.html`
- `legacy-root/index.html`, `legacy-root/register.html`

---

## 7. Go/No-Go Criteria

| Milestone | Verdict | Condition |
|---|---|---|
| Local demo | **GO** | Dependency install + smoke tests pass |
| Internal testing | **GO** (2026-07-03) | P0-01…P0-07 all done and verified |
| External pilot (tunnel) | **GO** (2026-07-09) | P0 ✅ + P1-07 backup ✅ + D1 real-IP fix ✅. **Before inviting real users:** rotate `admin123456` passwords + enable `COOKIE_SECURE=1` + schedule daily backup (Deployment.md §2.4) |
| AWS staging | **NO-GO** | Needs P3-01 config layering + P3-03 S3 media (plan: `docs/Deployment.md` §3) |

---

## 8. Historical Records

Earlier sprint documents (`docs/archive/`, Codex prompt files) were intentionally deleted in the 2026-07-03 documentation refactor. Git history before commit `1ff243d` retains them if ever needed.
