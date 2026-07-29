# StudioSaaS Current Sprint

> ⚠️ **已由 `docs/HANDOFF_LATEST.md` 取代（2026-07-26）。本文件停在 v7.0 sprint（2026-07-10），仅作历史参考。**
>
> **v7.1–v7.5 后续实际走向**（帮助读者接上）：
> - v7.2.x — 注册提交先落库再发通知邮件、真实入学日期、注册成功页与 `brand-system.css` 语义 token 共享。
> - v7.3.0/7.3.1 — 行业预设联动的七套 curated brand styles + 品牌搭建器三步化。
> - v7.3.2 — UX 审查 30 条全量执行（存储型 XSS 关闭、占位文案下线、CMS 双语层、术语表 CI）。
> - v7.3.3/7.3.4 — 主题系统重构（8 主题 × 明暗、`palette_gen.py` 390 断言）+ 双语链路补全（`localized_copy`、`?lang=` URL、hreflang）。
> - v7.4.0 — 全量 RBAC 角色边界审计修复、四界面可访问性、AWS 单实例部署套件（`deploy/aws/`）。
> - v7.4.1 — 数据库审计 + change-review 稳定性修复。
> - v7.5.0 — 文档全量刷新纠错、UI/UX 修复批次、`docs/guides/` 六份角色手册、skill 同步。

Version: v4.1
Date: 2026-07-10
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
| D2 | Cloudflare Tunnel → `https://studiosaas.cc.cd` → localhost:8901; current connector files are project-local under `.runtime/` | ✅ updated 2026-07-29 |
| P0-1 | Historical unique-password rotation was superseded by the user-directed shared local/Pilot demo password; startup still preserves hashes | ✅ updated 2026-07-29 |
| P0-2 | Tunnel-origin session cookies carry Secure (custom SessionInterface); local http unaffected | ✅ 2026-07-09 |
| P0-3 | One-click backup (`BACKUP_STUDIOSAAS_NOW.command`, keep 14) + restore drill passed (restore-dry-run, 10 migrations verified) | ✅ 2026-07-09 |
| P0-4 | On-demand ONLINE/STOP `.command` scripts (user chose no persistent daemons); LaunchAgent templates in `deploy/launchd/` if ever needed | ✅ 2026-07-09 |
| P0-5 | Cloudflare Access email-OTP policy on `/super-admin*` | ⚠️ manual dashboard step (Zero Trust → Access → Applications; self-hosted app for `studiosaas.cc.cd/super-admin*` + `/` root alias) |

### Product rename + tenant portal (2026-07-09, user-directed)

| Item | Status |
|---|---|
| Display rename → **PWE Studio** (titles, Super Admin, manifests and README; SaaS/Edition remain delivery descriptors, while internal identifiers and API service contracts stay unchanged) | ✅ |
| Default credential hints removed from login UI; the current shared local/Pilot password remains only in protected `.runtime/` files | ✅ updated 2026-07-29 |
| Super-admin quick links: Portal `/slug` + CMS `/slug/cms` + Admin + Register (was: "CMS" mislinked to `/slug`) | ✅ |
| Tenant portal v2: bilingual SPA (home/join/my/privacy), brand/programs from v1 public APIs, in-page enrolment, and a private student area protected by name + mobile + studio-issued 6-digit access code | ✅ |
| Student privacy hardening: append-only publication consent, one-hour HttpOnly student sessions, brute-force lockout, metadata-free display/thumb variants and fail-closed public media | ✅ 2026-07-18 |
| Canonical daily roster entries with reversible cancellation; recurring schedules remain preview templates | ✅ 2026-07-18 |
| Privacy-preserving portal funnel analytics + tenant-owned website media + tenant-scoped portal PWA manifest | ✅ 2026-07-18 |
| lets-paint-studio keeps the full-content portal (artist/FAQ/contact), rewired to v1 endpoints | ✅ |
| `/slug/cms/studio-admin` → 302 alias to `/slug/studio-admin` | ✅ |
| CSRF guard: `/v1/public/*` exempt (session-holding staff were 403-blocked on public portal forms) | ✅ |
| Principal (主理人) placeholder section in template + all tenants; lets-paint de-personalised (Junjun/LV refs removed) | ✅ |
| `.keep-local` guard: workspace files listed there survive template regeneration (protects bespoke portals) | ✅ |
| Folder tidy: portal reference → `docs/reference/`, 2026-07-03 zip snapshot → `checkpoints/`, .DS_Store purged | ✅ |

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
| P2-04 | Super Admin commercial cockpit: lifecycle, MRR, trial/risk/onboarding and acquisition funnel | ✅ 2026-07-12 |
| P2-05 | Studio Admin workflow reorganisation — Studio Admin refocused on website/brand/lead-capture settings; CMS remains daily operations | ✅ 2026-07-09 |
| P2-06 | Product-surface SSOT, brand draft/publish/version flow, commercial lifecycle metrics, registration source/follow-up funnel, plan limits and explicit operational roles | ✅ code complete 2026-07-12; DB/browser acceptance pending |
| P2-07 | Shared design tokens from `docs/Design_System.md` | ❌ |
| P2-08 | Review hardening: canonical lifecycle rules, complete archive snapshots, shared industry presets, bilingual Quick Registration, safer brand publishing, and dead Studio Admin operations removal | ✅ 2026-07-14 |
| P2-09 | Chinese-first Studio Admin and Super Admin with persistent 中文 / English switch, including dynamic controls and prompts | ✅ 2026-07-18 |

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
curl -sS http://localhost:8901/v1/health
```

### Auth test (local)

```bash
# Login
curl -i -c /tmp/studiosaas.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8901/v1/auth/login \
  -d "{\"email\":\"admin@studiosaas.local\",\"password\":\"$SUPER_ADMIN_PASSWORD\"}"

# Check session
curl -i -b /tmp/studiosaas.cookies http://localhost:8901/v1/auth/me

# Logout (cookie-authenticated mutations need the CSRF header)
curl -i -b /tmp/studiosaas.cookies -H 'X-Requested-With: StudioSaaS' \
  -X POST http://localhost:8901/v1/auth/logout
```

> **CSRF note (A4):** any mutation sent **with a session cookie** must include
> `-H 'X-Requested-With: StudioSaaS'` or it returns 403. Unauthenticated and
> public calls are unaffected.

### Tenant mutation without auth (must fail)

```bash
curl -i -X POST http://localhost:8901/v1/admin/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Bad Tenant","slug":"bad-tenant","planCode":"starter"}'
# Expected: 401

curl -i -X PATCH http://localhost:8901/s/lets-paint-studio/v1/tenant \
  -H 'Content-Type: application/json' \
  -d '{"name":"Hacked"}'
# Expected: 401 or 403
```

### Page open tests

```bash
# All should return 200
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8901/
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8901/studio-admin
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8901/lets-paint-studio
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8901/lets-paint-studio/cms
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8901/lets-paint-studio/studio-admin
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8901/lets-paint-studio/register
# /register should return 404
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8901/register
```

---

## 5. Protected Pilot Credentials

Passwords are absent from the repository and login UI. The current controlled
local/Pilot demonstration uses one user-directed shared application password,
stored only in `.runtime/online.env` and owner-only credential files. Normal
startup never changes password hashes.

The explicit local migration command is:

```bash
set -a
source .runtime/online.env
set +a
STUDIOSAAS_ENV=pilot STUDIOSAAS_MODE=saas \
  .venv/bin/python backend/scripts/set_local_demo_passwords.py \
  --confirm SET-ALL-LOCAL-APPLICATION-PASSWORDS \
  --cms-password-file .runtime/cms-data/.cms_password \
  --credentials-file .runtime/credentials/pilot-credentials.txt
```

This command also sets the separate legacy CMS password and writes the
credential handoff with mode `0600`. It refuses production and customer
Edition environments. AWS production must return to unique privileged
credentials, MFA and managed secrets. Password storage remains
PBKDF2-HMAC-SHA256.

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
| External pilot (tunnel) | **GO when launcher is running** | Full verification green + shared-password risk disclosed + Secure cookies + current backup. The tunnel is intentionally on demand. |
| AWS staging | **NO-GO** | Needs P3-01 config layering + P3-03 S3 media (plan: `docs/Deployment.md` §3) |

---

## 8. Historical Records

Earlier sprint documents (`docs/archive/`, Codex prompt files) were intentionally deleted in the 2026-07-03 documentation refactor. Git history before commit `1ff243d` retains them if ever needed.
