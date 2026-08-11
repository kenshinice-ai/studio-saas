# PWE Studio — Release Notes and Acceptance Evidence

## v9.8.6 — online manual: timetable and booking

The bilingual online manual now has a dedicated chapter for the public
timetable at `/<slug>/timetable` and its optional booking request flow. It
explains the two independent publication switches, the 1–4 week display and
booking window, field visibility, teacher-name consent, and the rule that a
booking request does not reserve a seat before approval.

The manual also adds four paired desktop/mobile screenshots from the synthetic
`lets-paint-showcase` capture tenant: Studio Admin timetable settings and the
mobile booking request dialog. This is a documentation-focused release; it
does not add a data migration or change stored customer records.

## v9.6.1 — Studio Admin workspace polish

This small release keeps the v9.6.0 information architecture and gives the
Studio Admin workbench a more useful canvas. On wide screens the shell uses the
available width like the CMS, while the navigation rail stays compact and the
editor/preview pair keeps its approximately `1.618:1` working ratio. Tablet
layouts stack the preview before the working area becomes cramped; mobile stays
single-column without horizontal overflow.

The preview now starts in the active admin shell language, so the surrounding
controls, draft notice and save status do not unexpectedly disagree with the
preview. The preview language buttons remain available for an explicit,
independent bilingual comparison.

This is a presentation and language-alignment release only. It does not change
the data model, permissions, publishing contract, payments, bank-transfer
display, persistent CMS notifications or external messaging providers.

Production acceptance: v9.6.1 is deployed at `https://pwestudio.online` from
candidate commit `e46a3e3f4a407e8b2ac34ce8e230165c37150ea1`. The SaaS archive
SHA-256 is `f1465b393fefb83e962bac41402fff150430c3fcd3e9b7252911d985840aabb4`;
the Edition archive SHA-256 is
`3d881f7e3324b5acacc4aa89feadd23a278e5cd2cc412f0474d6c13b8deb7e0e`.
Deep health reports `appVersion=9.6.1`, `db=ok`, six readable tenants and
`themes.unreadable=0`.

## v9.6.0 — Studio Admin navigation and publication clarity

Studio Admin now groups the public-brand workbench into Brand & Website,
Admissions, Publish and Insights. Registration and public timetable controls
are together under Admissions; family message templates remain in Studio Admin
under the same group and remain compatible with the existing CMS copy workflow.

The release also repairs dirty-state coverage for timezone, timetable and family
message fields, makes Registration shortcuts and workbench views deep-linkable,
completes timetable translation, reserves safe space for the sticky save bar and
labels the right-hand panel as a private draft preview. Publication status now
distinguishes unsaved changes, saved private drafts and published content.

Online payments, bank-transfer configuration, Gmail/SMTP, AWS SES, SMS, SSE,
WebSocket and browser push remain deferred.

Production acceptance: v9.6.0 is deployed at `https://pwestudio.online` from
candidate commit `f9007855dcaa10298bd522c82e7397d2afba0638`. The SaaS archive
SHA-256 is `38da495f81146d48878350fd07a8dfce25b6c30ff67782f3f4cc3d990790cdde`;
the Edition archive SHA-256 is
`88416f04de9cf7ab88fa61a409e094e282d4ed9701218757d39b9b44db51d2a2`.
Deep health reports `appVersion=9.6.0`, `db=ok`, six readable tenants and
`themes.unreadable=0`.

## v9.5.0 — CMS information architecture and operational workspaces

The CMS now has one stable working model for operators: a top app bar for
high-frequency controls, grouped navigation, a role-specific workbench and
deep-linkable routes. Daily work is grouped into Today, Teaching & Operations,
Business and Records; System Settings is a full page with anchored sections.

Courses, works, students, pending requests and recharge/refund operations now
have dedicated functional workspaces. The same permissions remain enforced by
role, and the UI does not expose Studio Admin or the public portal as if they
were CMS workspaces. The layout keeps a wide content measure beside a compact
navigation rail, uses the existing PWE Brand tokens, and preserves 44px touch
targets on mobile.

Persistent CMS notifications remain in-app only: new registrations and
class-booking requests are stored with the request, shown in the notification
center, refreshed every 30 seconds and surfaced with a popup prompt. Online
payments, bank-transfer configuration, Gmail/SMTP, AWS SES, SMS, SSE,
WebSocket and browser push remain deferred.

Production acceptance: v9.5.0 is deployed at `https://pwestudio.online` from
commit `9a976215bab9d5b32b9792f36851078a4111ff4b`. The SaaS archive SHA-256 is
`d9cd91c57467213ee81710d290b8a589c6910b4819568d136e2da9e59842802a`; the
Edition archive SHA-256 is
`90409a371521074252ceed90946198a5c4021319fcefb19fc55d665f74dfc97d`. Public
deep health reports `db=ok` and all six stored tenant themes readable.

## v9.2.0 — persistent CMS notifications

The CMS now keeps an in-app notification history for new public registrations
and class-booking requests. Each event is written in the same database
transaction as the request, so the notification cannot claim success for a
request that was not saved, and duplicate submissions do not create duplicate
alerts. Staff with registration visibility see a bell, unread count and
notification list; booking notifications are limited to roles that can review
bookings.

The first delivery uses a simple 30-second refresh, an immediate refresh when
the browser becomes visible again, a popup prompt for new events and per-user
read state. Online payments, bank-transfer configuration, Gmail/SMTP, AWS SES,
SMS, SSE and WebSocket push remain deferred.

## v9.1.1 — Course Schedule terminology and operator polish

The CMS workspace formerly named Daily Roster is now Course Schedule. Its date
and week navigation, attendance summary, time groups, add-student controls and
batch tools form one top-to-bottom planning flow. Wide layouts keep each student
on one compact row, while mobile retains the same task order without horizontal
overflow.

Each student's more-actions menu now opens with their date, time and credit
balance, identifies recurring-schedule entries, and groups status, reminder,
one-to-one, undo and removal actions. Scheduled and make-up states can be saved
directly without removing and re-adding the student.

## v9.1.0 — faster daily scheduling and safer delivery

v9.1.0 reshapes the daily roster around the work performed at the front desk:
date navigation, week occupancy, attendance summary, time groups, batch tools
and student rows now form one compact planner. Each row has one clear check-in
and credit-deduction action, while reminders, one-to-one marking, date-bound
undo and removal live in a deliberate overflow menu. Only an explicit
`oneToOne` flag raises a same-time conflict; ordinary group classes remain
valid. Birthday and recurring-schedule tools stay available but collapsed so
they no longer push today's work below the fold.

The dashboard now turns student-portal and publication readiness into actionable
filters. Thirty-day activity is keyed by immutable student ID; a historical
name-only event is used only when the name identifies exactly one student.
Public timetable bookings notify the studio admin only after a new request is
durably committed, and duplicate submissions never send a second alert.

Image delivery now creates 360px, 960px and 2000px metadata-free derivatives
and publishes responsive candidates. Existing media is covered by an explicit
backfill. Authorized private media uses checksum ETags with `private,
no-cache`, so a repeat request can return 304 only after session, ownership and
consent checks. Shared frontend assets likewise carry both release and content
hashes; a missing or stale manifest fails the build/runtime contract instead of
silently caching mismatched JavaScript.

## v9.0.0 — one Brand contract and a safe CMS migration baseline

v9.0.0 establishes one product-wide contract rather than introducing a
breaking data migration. The source, package and deployed production status are
reported separately; `docs/design/Brand_Identity.md` is the canonical Brand
document; public product surfaces share the same bilingual system type,
touch-target and layout rules; and Front Desk has a narrow backend permission
to review class-booking requests without gaining course, capacity or schedule
authority.

Inside the operational CMS, the release repairs malformed touch, active and
disabled selectors and migrates only `EmptyState` to semantic theme tokens.
The component's props and callbacks are unchanged. A real Chromium acceptance
at 390px verified no horizontal overflow, a 44px action target and a visible
2px keyboard focus ring. This is the reference pattern for later CMS migration,
not authorization for a broad rewrite.

## v8.1.0 — Production deployment and tenant theme publication

Release status: production deployed to `https://pwestudio.online` on
2026-07-30 (AWS Lightsail, Sydney). Monitoring, a contractual SLA,
privileged-account MFA and off-instance backup copies remain deferred and are
disclosed as deferred.

The customer-facing version of this record is
`customer-resources/Release_Notes.html`. Engineering detail and measured
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

Applied by migration `0021_plan_quota_revision.sql`, live in production. Over-quota behaviour is
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

v8.1.0 is deployed: the instance runs `studiosaas:8.1.0` with 21 migrations
applied and the revised plan quotas live
(`starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`). See
`docs/HANDOFF_LATEST.md` §7.5. (§9.2 of that document describes migration 0021
as pending; it was written before the deploy and is superseded by §7.5.)

## Customer acceptance

Customer representative: `[ ]`
Demonstrated version/hash: `[ ]`
Demonstration date: `[ ]`
Accepted scope: `[ ]`
Open exceptions: `[ ]`
Signature: `[ ]`
