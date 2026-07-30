# PWE Studio v8.1.0 — Release Notes and Acceptance Evidence

Release status: production deployed to `https://pwestudio.online` on
2026-07-30 (AWS Lightsail, Sydney). Monitoring, a contractual SLA,
privileged-account MFA and off-instance backup copies remain deferred and are
disclosed as deferred.

The customer-facing version of this record is
`customer-resources/Release_Notes_v8.1.0.html`. Engineering detail and measured
evidence live in `docs/HANDOFF_LATEST.md`.

## What v8.1.0 changes

### Production hosting (was deferred in v8.0.1)

- `https://pwestudio.online` runs on an AWS Lightsail instance (Ubuntu 24.04,
  2 vCPU / 1.9 GB, `ap-southeast-2`). nginx terminates TLS with a Let's Encrypt
  certificate covering the apex and `www`; `www` 301s to the apex; HTTP 301s to
  HTTPS; HSTS is set for one year. The application listens on loopback only.
- Daily PostgreSQL logical dump plus media-volume archive under cron; the
  restore rehearsal runs and passes.
- **Cloudflare Tunnel is no longer the production path.** It is retained for
  local development only and must not be reintroduced for this hostname.
- Edge hardening: one shared TLS snippet included by both 443 blocks, duplicate
  security headers removed, a branded maintenance page for 502/503/504, and
  **OCSP stapling deliberately left off** — the Let's Encrypt certificate no
  longer carries an OCSP responder URL, so enabling it produces a permanent
  ignored-directive warning on every reload and nothing else.

### Tenant theme publication (the release's main product fix)

- The registration success card paired fixed light text with `--ink`. Under the
  seven dark theme-modes `--ink` *is* the light text colour, so that card
  measured **1.06:1 — a parent who submitted a registration saw an invisible
  confirmation**. It now uses `var(--bg)` against `var(--ink)`, a pair
  `backend/scripts/palette_gen.py:221` already asserts at ≥4.5:1, which covers
  all 15 theme-modes.
- The portal's degraded-content band moved from a fixed warm yellow to the
  theme's own warning colour, so it is no longer a light foreign strip across
  every dark theme.
- The CMS mapped **10 of the 21 theme tokens** and then applied
  `body { background:#f1f5f9 !important }` over the result, so every studio's
  CMS looked identical. Portal, registration and CMS now map the same complete
  21-token set, with a test asserting the three agree field for field.
- Product homepage focus ring: Family Amber measured **1.70:1** against Warm
  Paper, below the 3:1 WCAG 1.4.11 requires of a non-text indicator. It now uses
  the accessible amber at **4.52:1**; the bright amber is retained on navy
  sections where it measures 9.70:1.
- Dark-section form borders moved from `rgba(255,255,255,.28)` (2.51:1) to
  `.42` (3.90:1).
- `backend/tests/test_portal_theme_contract.py` (12 tests, new) holds all of the
  above.

### Commercial plan quotas (owner decision, 2026-07-30)

Prices, plan codes, plan names and feature flags are unchanged.

| Plan | AUD/month | Students | Team users | Storage |
|---|---:|---:|---:|---:|
| Starter | 49 (unchanged) | 100 (unchanged) | 2 → **1** | 5 GB → **2 GB** |
| Studio | 99 (unchanged) | 500 (unchanged) | 8 → **5** | 30 GB → **10 GB** |
| Growth | 199 (unchanged) | 1500 → **1000** | 20 (unchanged) | 100 GB → **50 GB** |

Applied by migration `0021_plan_quota_revision.sql`. Over-quota behaviour is
admission control on new records only: a tenant found above a lowered ceiling
keeps all of its data and simply cannot add more until the plan is upgraded.

### Compliance and brand

- `customer-resources/Privacy_Policy.html` and `Terms_of_Service.html` are new
  and published (PWE GROUP PTY LTD, ABN 55 606 664 546). Both carry a draft
  qualifier pending Australian legal review.
- The FAQ and these release notes no longer claim "AWS not yet deployed"; they
  state the live position and the gaps that remain on a live service.
- Both pages were migrated off the retired forest/sage palette onto the brand
  tokens through a shared stylesheet.

## Explicitly not delivered

- Uptime monitoring, backup-failure alerting, on-call ownership, a contractual
  SLA;
- multi-factor authentication for privileged accounts — now an open gap on a
  live service, and the highest-priority security item;
- off-instance backup copies (backups exist and restore, but live on the same
  instance);
- managed AWS services (RDS, S3, SES);
- automated messaging provider, online payments, accounting sync;
- per-studio custom domains;
- organisation-level multi-campus aggregation — one campus remains one tenant;
- inside the CMS only: the second, older dark-appearance mechanism is not yet
  merged into the theme one, and the `text-gray-400`-class secondary labels do
  not yet meet AA. Both are recorded as items 29, 7 and 8 in
  `docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`. Neither affects a
  parent-facing or student-facing surface.

## Acceptance matrix

| Gate | Required evidence | Status |
|---|---|---|
| Unit/backend | full local PostgreSQL verification gate | Complete |
| Theme publication | portal/registration/CMS map the identical complete token set | Complete: `test_portal_theme_contract.py` |
| Public-surface contrast | text and focus indicators meet the standard across all 15 theme-modes | Complete; the CMS items above remain open |
| Calendar privacy | ICS structure/timezone and no student data | Complete |
| Demo reset | guard refusal plus successful isolated reset | Complete |
| Frontend build | CMS source compiled to deployed bundle | Complete |
| Responsive UI | 375, 768, 1024 and 1440 px browser checks | Complete |
| Templates | CSV + 5-sheet XLSX, all sheets rendered and inspected | Complete |
| Packages | SaaS + Edition bundle build and content inspection | Complete |
| Deployment | public HTTPS, DNS, certificate, redirect, deep health, data counts | Passed 2026-07-30 |
| Recovery | database and media restore rehearsal from a real backup artefact | Passed on-instance; off-instance copy open |
| Privileged MFA | second factor enforced for every privileged account | Open |
| Monitoring and SLA | uptime and backup-failure alerting, on-call roster, signed target | Open |

The instance keeps serving the build installed on 2026-07-30 until the next
deployment; the v8.1.0 build and migration 0021 reach production with that
deployment. See `docs/HANDOFF_LATEST.md` §9.2.

## Customer acceptance

Customer representative: `[ ]`
Demonstrated version/hash: `[ ]`
Demonstration date: `[ ]`
Accepted scope: `[ ]`
Open exceptions: `[ ]`
Signature: `[ ]`
