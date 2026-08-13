# PWE Studio

## Current release identity

These are three independent facts. A matching version label is not proof that
the current source tree was packaged or deployed; Source, Package and
Production remain separate rows. v9.9.2 completed all three milestones on
12 August 2026; the rows below record the independent evidence.

| Layer | Verified state | Evidence |
|---|---|---|
| Source | **v9.9.2 committed** | `VERSION` = **9.9.2**; release commit `aeda04e98b9faaa062c1938285a1b10cc008bd9b` on `claude/ui-ux-pro-max-audit-073a82`. Full gate green: `verify_local.sh` all checks passed, pytest `1726 passed, 5 skipped`, legacy CMS smoke `73 passed`, tenant isolation `237 passed, 0 failed`. |
| Package | Clean SaaS and Edition v9.9.2 packages verified | SaaS `dist/PWE-StudioSaaS-aws-9.9.2.tar.gz` SHA-256 `f62c355b6e89fde18632314945ac6058d702bd9b5dd2010825f2a8763a6c83db`; Edition `dist/PWE-Studio-Edition-9.9.2.tar.gz` SHA-256 `b7fc586677f9c5686b00384e3ec8fb8cad4b922fc64ba60a4de56917dc9f2f19`. Both `BUILD_INFO` records read v9.9.2 with modes `saas` / `standalone`, and both passed checksum, entrypoint, version and exclusion checks. |
| Production | **v9.9.2 deployed to `pwestudio.online`** | `/opt/pwestudio/current` points to `PWE-StudioSaaS-aws-9.9.2`; image `studiosaas:9.9.2`; deep health reports `appVersion=9.9.2`, `db=ok`, `mode=saas`, `tenants=6`, `themes.unreadable=0`, `workspaces.stale=0`; disk free about `45.93 GB`; HTTP→HTTPS `301`, HTTPS `200`, TLS check `0`, HTTP/2. |

Re-verify the production health endpoint (`/v1/health?deep=1`) before any later
release claim; do not infer Production from `VERSION` or from an archive
filename, which does not identify the deployed commit. The
deployed source commit is recorded in the Source row above and in the latest
handoff, never inferred from the version label.

## v9.9.2 release scope

Two corrections to v9.9.0, both reported from a real console:

**The draft asked the wrong question of its own records.** `collectShowcaseItems()`
maps to the API's camelCase on its way out, and the draft contract filtered that
output on `image_url` and `publication_state` — undefined on every mapped item.
`showcaseHasContent()` therefore answered false for every work, so the switch
read "no published work yet" while the studio's site showed two and the counter
above the dropzone agreed with the site.

**A long label was clipped twice.** `16ch` is about 8em, narrower than the ten
Chinese characters the contract already allows, so the browser cut a label the
server had cut, leaving an ellipsis inside an ellipsis. The contract is the only
limit now; the CSS is a safety net. The call to action gets a tighter limit than
the rest of the bar, because it is a bordered pill next to the language switch —
least room, most padding. The hero button reads that field directly and still
shows all of it.

---

## v9.9.0 release scope

Six batches, all of them things that were already wrong rather than things
that were missing.

**Navigation.** A hash link was rewritten to name the tenant home page on every
page including the home page, where the result differed from the current URL
by more than its fragment whenever the visit carried a query — so every nav
click from an advertisement was a full reload that also dropped `?lang=` and
every `utm_*`. The timetable page never declared its slug, so the rewrite it
depends on did nothing there. The home page's contract-failure branch reached
neither `apply()` nor the local fallback, leaving the header behind the loading
mask for the life of the page.

**A renamed studio's name.** `tenants/<slug>/` is materialised and carried the
studio's name into `<title>`, the social-preview tags and the structured data
at creation; nothing rewrote it afterwards. Publishing now re-renders the
workspace, and the head strings are composed server-side with the same
precedence the portal uses in the browser.

**One shell.** The four public pages kept four hand-maintained copies of the
header and footer entry lists, which had drifted in three places. The entries
live in shared partials spliced in at generation. Nav labels are clipped in the
contract — one studio's English course label is 74 characters — with a parity
test between the two implementations of the rule.

**Studio Admin.** `Publish` had two meanings, one of which only saved a draft.
Nine "is this public" switches lived across four panels. The contract's reason
codes were printed to owners as identifiers. Three fields had four names.

**Chinese.** Sixty-eight visible strings had no translation, including the one
shown when a publish is still being confirmed. A coverage gate now mirrors what
the runtime walks.

**Public addresses.** `tenant_slug_aliases` records every address the platform
has issued. A studio can change its address once a year, from Platform Admin,
with the old one 301ing forever; addresses are never reissued, and a deleted
studio's leaves a tombstone that answers 410.

New migration: `0031_tenant_slug_aliases.sql`. No change to plan limits,
payment capability or the tenant data model.

## v9.8.9 released scope

This release makes Studio Admin’s public editing and publishing model
truthful end to end. The Hero secondary action has an explicit destination
contract and hides when its chosen target is not ready. Space & Experience is
a dedicated editor with six preserved highlights, ordered images, bilingual
alternative text and visitor-controlled thumbnails. Draft and Live previews
are separated, publish errors remain visible with a path back to the field,
and published-version verification covers the shared public-surface contract.

The portal, showcase, timetable and registration page now consume the same
server-authoritative module, navigation, footer and action contract. A local
resolver is only a visible fail-safe after the authoritative request settles;
it does not silently overwrite a successful server result.

## v9.8.8 released scope

This release separates publish writes from public verification, adds a shared
`publicSurfaceContract` for the portal, standalone showcase, timetable and
register footer, and gives Studio Admin a light, information-tinted navigation
rail with the existing 1.618 editor/preview split. Links now require both owner
intent and real published content, and consent revocation / timetable horizon
checks use the same server rules as the destination page. The bilingual manual
and Studio Admin copy explain the pending-verification state and retry path. The
guarded production switch created a logical database backup and volume archive
before changing the live symlink; v9.8.7 remains available as the immediate
rollback release.

## v9.8.7 ranked standalone showcase acceptance

The release adds an optional tenant-wide `featured_rank` (1–500). Lower
numbers lead the global public order, ranks 1–6 define the home preview, and
blank ranks keep the stable fallback order. The independent `/<slug>/showcase`
archive uses the same order, supports category URLs, loads 12 matching works
per page with C-scheme offset pagination and a visible Load more fallback, and
keeps the shared navigation/footer shell with the home page, timetable and
registration surfaces.

Plan changes preserve all stored works and ranks; only the number of Active
works eligible for public publication follows the plan. Studio Admin, the
bilingual online manual and customer-facing release notes use the same
Starter / 入门版, Studio / 工作室版 and Growth / 成长版 terminology.

The deployable source commit is `4e1894f12a31935701f3982757bd8fe0f441e0d0`.
Production migration `0030_showcase_featured_rank.sql` applied successfully;
the pre-switch logical backup is
`studiosaas_studiosaas_20260811T083534Z.dump` with manifest and the volume
archive is `pwestudio-volumes-20260811T083535Z.tar.gz`. Public deep health is
`appVersion=9.8.7`, `db=ok`, `mode=saas`, six tenants and
`themes.unreadable=0`; the v9.8.7 application container has no fresh
Traceback/Exception/Fatal/Error entries after deployment.

Read-only public acceptance returned `200` for the root, bilingual manual,
standalone showcase, timetable, register, Studio Admin, Platform Admin and
Release Notes. Ruby Studio's public API reports home `pageSize=6` with
`total=12`, archive `pageSize=12`, category filtering and a valid empty page at
`offset=12`. A real 390×844 production browser viewport has no horizontal
overflow (`documentWidth=390`), exposes the 44px mobile menu, opens a work in
the lightbox with an image and `1 / 12` counter, and closes it with focus and
scroll state restored.

## v9.8.6 online manual and timetable acceptance

The bilingual manual now has a dedicated public timetable and booking chapter,
with the Studio Admin settings and mobile request dialog shown in paired
screenshots. The release keeps the booking rule explicit: a request waits for
CMS review and does not reserve a seat before approval. No data migration or
customer record change was introduced.

The deployable v9.8.6 commit is `21d2cc70bcd116250fca4780bec164a855b45258`.
The documentation-only closure is pushed separately after the production
acceptance below; it does not change the running package. The production
controller created the logical backup
`studiosaas_studiosaas_20260811T064145Z.dump` with its manifest and the volume
archive `pwestudio-volumes-20260811T064146Z.tar.gz` before switching releases.

Local gates passed: `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`,
full pytest `2283 passed, 8 skipped`, CMS smoke `73 passed`, and tenant
isolation `237 passed, 0 failed`. The SaaS and Edition bundles passed checksum,
mode, `BUILD_INFO`, entrypoint and exclusion checks.

Production applied migrations through `0029_showcase_plan_values_and_states.sql`;
the entrypoint reported `Database is up to date` and `Generated variants: 0`.
The public root, bilingual manual, showcase portal and timetable, CMS, Studio
Admin, register page, and bilingual Release Notes all returned `200`.
The Chinese manual served the versioned timetable screenshot with the local
and public SHA-256 `6157b883c9c46d13a5eef10888f1cf739f5c3aa26db748856216a272ded70999`;
the resource returned immutable caching and a conditional request returned
`304`.

## v9.8.5 action context, editor review and plan-linked work counts

The Platform Admin `Actions` column now opens an anchored command menu for
frequent tenant and plan operations. Selecting an operation puts its review and
explicit next step in the right Inspector; opening CMS or Studio Admin remains
support-mode gated. Tenant editing now has section navigation, while the right
review shows changed entitlements, preserved content, tenant notifications and
blocking adjustments. Admin tenant usage includes active, draft and archived
showcase counts, and plan-change impact includes active works so a downgrade
cannot hide a works over-limit condition.

The v9.8.5 SaaS and Edition packages passed the release gates and the SaaS
package is deployed to production. The latest handoff records package hashes,
backup, migration, cache, media and public-route acceptance evidence.

## v9.8.4 plan-change safety and Platform Admin clarity

Plan upgrades and downgrades now show a server-backed impact review before an
operator can save: changed limits and features, content that remains preserved,
usage above a lower limit, and the tenants that must be notified. The UI
requires the operator to acknowledge both the impact and tenant notification;
the API independently rejects missing acknowledgements with a structured `409`
and records the accepted change in the audit log. Existing website, brand,
showcase, student, course, registration, media and audit data is not deleted by
a plan change.

The release is deployed as v9.8.4. Platform Admin tenant and plan rows now open read-only quick views on row click;
editing, lifecycle, support, archive and deletion actions are grouped under the
center `Actions` control. Bilingual plan labels are canonical: Starter / 入门版,
Studio / 工作室版, and Growth / 成长版, while API codes stay unchanged.

## v9.8.3 plan-linked showcase release

The showcase entitlement is now explicit end to end: starter publishes 15 active
works, studio 60, and growth 150. The public endpoint still pages 12 items at a
time; it no longer treats 12 as a storage or plan cap. Work records carry an
`active` / `draft` / `archived` state, so downgrades preserve the full portfolio
and new uploads beyond active capacity become drafts. The Super Admin plan form
also sends `showcaseLimit`, and PATCH requests preserve an existing value when a
legacy caller omits the field. The release is deployed to production; the public
plans endpoint now returns 15 / 60 / 150 and Ruby Studio retains all 12 active
works.

## v9.8.2 showcase safety hotfix

This hotfix is based on the exact v9.8.1 production commit. Platform Admin
tenant edits now lock and preserve the stored brand/website payload when the
operator changes commercial fields such as the plan. Omitted nested settings
are no longer normalised to defaults and overlaid on the tenant row. Showcase
lightboxes now own a bounded viewport box and use centered `object-fit: contain`
media, so portrait and landscape works cannot overflow into the action bar or
leave the image anchored to one side.

Ruby Studio's last valid published brand version 44 was recovered as linked
version 45 after a fresh database and volume backup. All 12 showcase items and
four categories are present again, the public showcase is enabled, and both the
tenant and subscription plan remain `growth`. Public browser acceptance opened
a real 1500×2000 work: it is centered and contained inside the stage, clears
the metadata/action bar, and produced no browser console errors.

## v9.8.1 Platform Admin workbench polish

This candidate closes the remaining Platform Admin workbench gaps identified in
the 2026-08-10 audit: the shell uses the full available canvas, plan and tenant
editing opens in the center workspace with a sticky save bar, the Inspector
shows form state and validation impact, row actions keep View as the default
path, and phones use a discoverable work-area drawer. New bilingual labels and
attention reasons remain aligned with the existing payment boundary; this does
not add online payments, bank-transfer settings, external email, SSE, WebSocket
or browser push.

Source and production evidence for v9.8.1 are intentionally closed only after
the candidate is committed, packaged, deployed and independently verified.

## v9.8.0 Platform Admin workbench

This release turns Platform Admin into a three-column operations workbench:
the left rail locates the supported work areas, the center performs the active
workflow, and the right Tenant/Plan/Audit Inspector carries the selected
context. Today leads with a Needs attention queue derived from the existing
tenant, subscription and usage data; Attention is a shortcut inside Today, not
a second dashboard.

The Inspector orders information as status → risk → subscription/resource
information → safe actions. Support Mode stays visually separate at the bottom
and still requires a reason with field-level feedback before the audited flow
starts. Mobile turns the Inspector into a responsive sheet without horizontal
overflow. Only capabilities that exist today are exposed in the rail: Today,
Tenants, Plans & Pricing, and Audit Logs.

Subscription lifecycle copy remains “Subscription past due”; this release does
not add online payments, bank-transfer configuration, Gmail/SMTP, AWS SES, SMS,
SSE, WebSocket or browser push, and does not invent Groups, Invitations,
Announcements, System Health or Settings pages that are not current
capabilities.

Release closure (2026-08-10): v9.8.0 was deployed through the guarded Lightsail
controller from the candidate commit above. Public deep health, critical routes,
the immutable Platform Admin asset hash/cache response, and the production
browser login boundary were accepted. Exact package, backup and verification
evidence is recorded in `docs/HANDOFF_LATEST.md`.

## v9.6.1 Studio Admin workspace polish

This small release keeps the approved Studio Admin information architecture and
improves its working surface: the shell now uses the available desktop width
like the CMS, with a compact navigation rail and a golden-ratio editor/preview
split inside it. Tablet layouts stack the preview before content becomes cramped,
and mobile stays single-column without horizontal overflow.

The preview language starts in the admin shell language so the interface does
not present an unexplained Chinese/English mismatch. Its own language control
still allows an explicit independent comparison. Surface health labels, draft
status and save status now follow the active admin language as well.

No data model, permissions, publishing contract, payment, notification or
external messaging behaviour changes in this release. Online payments,
bank-transfer configuration, Gmail/SMTP, AWS SES, SMS, SSE, WebSocket and
browser push remain outside scope.

## v9.6.0 Studio Admin information architecture and publication clarity

This release executes the approved Studio Admin handoff. The workbench now uses
grouped navigation for Brand & Website, Admissions, Publish and Insights while
preserving the editor/preview golden-ratio layout. Family messages remain in
Studio Admin, under Admissions, and continue using the existing compatible
`messageTemplates` payload; no message provider or automatic sending is added.

P0 repairs cover real dirty-state tracking for timezone, timetable and message
fields, a working Registration shortcut, bilingual timetable labels, safe space
for the sticky save bar and URL-addressable workbench views. The preview now
states that it is a private draft, while the publish center distinguishes draft,
published and unsaved states.

Payments, bank-transfer configuration, Gmail/SMTP, AWS SES, SMS, SSE, WebSocket
and browser push remain outside this release.

## v9.5.0 CMS Information Architecture and Persistent Notifications

The CMS now uses a stable information architecture: a top app bar for high-
frequency controls, grouped left navigation, role-specific workbenches and
route-aware deep links. Daily work is organized under Today, Teaching &
Operations, Business and Records; settings is a full workspace rather than a
large modal. Courses, works, students, pending requests and recharge/refund
operations each have a clear functional home.

The CMS also records new public registrations and class-booking requests in a
tenant-scoped, durable notification history. Operators with the relevant
registration visibility see unread counts, a bell/list view, per-user read
state and popup prompts. The first delivery refreshes every 30 seconds and
refreshes immediately when the browser becomes visible again.

This release deliberately does not include online payments, bank-transfer
configuration, Gmail/SMTP, AWS SES, SMS, SSE, WebSocket or browser push. The
publicly deployed package and the independent Edition package are both kept in
`dist/` locally; internal `docs/sales/` material was preserved and excluded.

PWE Studio (repo: studiosaas) is a Creative Studio Operating System for art schools, music studios, tutoring centres, creative academies, kids' activity providers, and small education businesses. One codebase supports a multi-tenant SaaS delivery model and a customer-owned standalone Edition.

It provides a lightweight SaaS-style platform for managing:

- tenant websites and public registration forms
- studio admin dashboards
- students, registrations, courses, packages
- credit (clock-hour) balances with ledger-style transactions
- portfolio media and branding settings
- platform-level tenant management

**Status:** public pilot stage, deployed. The multi-tenant SaaS runtime serves
`https://pwestudio.online` from a single AWS Lightsail instance in
`ap-southeast-2` (Ubuntu 24.04, 2 vCPU / 1.9 GB), live since 2026-07-30. Host
nginx terminates TLS with a Let's Encrypt certificate covering the apex and
`www`; the application binds to loopback only. Daily PostgreSQL logical dumps
and a media-volume archive run under cron, and the restore rehearsal passes.
**Cloudflare Tunnel is no longer the production path** — it is retained for
local development only and must not be reintroduced for this hostname. The
single-tenant **PWE Studio Edition** (`STUDIOSAAS_MODE=standalone`) ships as a
customer-installed package from the same codebase.

Still not claimed, and deliberately disclosed as absent: uptime monitoring,
backup-failure alerting, on-call ownership and a contractual SLA; multi-factor
authentication for privileged accounts; off-instance backup copies; managed AWS
services (RDS, S3, SES). See `docs/HANDOFF_LATEST.md` §0 for the measured
position.

Canonical product responsibilities and names are defined in `docs/Product_Surface_Model.md`: Super Admin is the commercial control plane, Studio Admin is the tenant brand/publication workspace, Studio CMS owns daily operations, the Studio Portal is the primary public acquisition experience, and Quick Registration is an alternate tenant-scoped entry.

---

## v8.1.0 Production Deployment and Tenant Theme Publication Release

v8.1.0 takes the service into production and then fixes what going live, and a
full readability review, exposed.

**Production (2026-07-30).** `https://pwestudio.online` on AWS Lightsail
(Ubuntu 24.04, 2 vCPU / 1.9 GB, `ap-southeast-2`); host nginx terminates TLS,
Let's Encrypt covers apex + `www`, `www` 301s to the apex, the application binds
to loopback only; daily PostgreSQL logical dump plus media-volume archive under
cron with a passing restore rehearsal. Cloudflare Tunnel is retired from the
production path and kept for local development only. Detail in
`docs/HANDOFF_LATEST.md` §0.

**Edge hardening.** One shared TLS snippet included by both 443 blocks,
duplicate security headers removed, a branded maintenance page for 502/503/504,
and **OCSP stapling deliberately off** — Let's Encrypt certificates no longer
carry an OCSP responder URL, so `ssl_stapling on` only produces a permanent
ignored-directive warning on every reload (§0.3).

**Tenant theme publication — the release's main product fix.**

- The portal registration success card was `background:var(--ink); color:#EFE9DD`.
  `--ink` is the tenant theme's `text_color`, so under the seven dark
  theme-modes that fixed light text sat on a light surface at **1.06:1 — the
  confirmation a parent saw after submitting a registration was invisible.** It
  now uses `var(--bg)`, a pair `backend/scripts/palette_gen.py:221` asserts at
  ≥4.5:1 across all 15 theme-modes.
- The portal's degraded-content band moved from a fixed warm yellow to the
  theme's own warning semantic, so it is no longer a light foreign strip on
  every dark theme.
- The CMS mapped **10 of the 21 theme tokens** and then applied
  `body { background:#f1f5f9 !important }` over the result, so every studio's
  CMS looked identical. Portal, registration and CMS now map the same complete
  21-token set, with a test asserting the three agree field for field.
- `product-home.html` focus ring: Family Amber measures **1.70:1** on Warm
  Paper, below the 3:1 WCAG 1.4.11 requires of a non-text indicator. The
  accessible amber measures 4.52:1 and is now used on light surfaces; the bright
  amber is retained on navy sections at 9.70:1.
- Dark-section form borders: `rgba(255,255,255,.28)` (2.51:1) →
  `.42` (3.90:1).
- `backend/tests/test_portal_theme_contract.py` (12 tests, new) holds all of it.

**Commercial plan quotas** (owner decision; prices, plan codes, names and
feature flags unchanged): Starter 1 team account / 2 GB, Studio 5 / 10 GB,
Growth 1,000 students / 50 GB with its 20 team accounts kept. Migration
`0021_plan_quota_revision.sql`. Over-quota behaviour is admission control on new
records only — nothing existing is archived or deleted.

**Compliance and brand.** `customer-resources/Privacy_Policy.html` and
`Terms_of_Service.html` are new and published (PWE GROUP PTY LTD, ABN
55 606 664 546), both carrying a draft qualifier pending Australian legal
review. The FAQ and release notes dropped the superseded "AWS not yet deployed"
answer and moved off the retired forest/sage palette onto the brand tokens.

**Deliberately not done in v8.1.0**, and disclosed as absent: uptime
monitoring, backup-failure alerting, on-call ownership and a contractual SLA;
privileged-account MFA; off-instance media/database backup copies. Inside the
CMS only, the second dark-appearance system is not yet merged into the
theme-mode one and 128 `text-gray-400`-class secondary labels still fall short
of AA — items 29, 7 and 8 of
`docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`. Neither touches a
parent-facing or student-facing surface.

Those CMS-internal items are historical v8.1.0 limitations. The v8.1.1
candidate resolves the second dark owner and maps weak/semantic utility classes
through the tenant's generated tokens; the source class names remain only as
implementation selectors.

---

## v8.0.1 Brand-Aligned Product Gateway and Customer-Readiness Release

v8.0.1 retains the v8.0.0 customer-demonstration scope and aligns its product
gateway with the canonical PWE brand and sales language:

- `/` uses Family Navy, Family Amber, accessible amber text and Warm Paper,
  with retired forest, sage and coral values guarded by regression tests;
- the bilingual sales story places administration behind the scenes and
  creativity in front, uses Let’s Paint Studio as the operating proof, and
  clarifies the recommended Studio plan and one-time setup range;
- the product gateway retains five role entrances, migration downloads and
  device-native Mail/Messages support actions;
- `lets-paint-showcase` is an isolated professional demonstration tenant with
  fictional records, synthetic artwork and a guarded one-click reset;
- recurring class schedules can be downloaded as a privacy-safe ICS calendar
  without student or roster data;
- Studio Admin and CMS retain separate responsibilities but expose stable,
  reciprocal navigation; the teacher mobile dashboard prioritises today's
  roster, student lookup and artwork upload;
- eight industry presets now include starter courses, registration focus,
  report focus and a demonstration story—not only colours and nouns;
- `docs/customer/` contains onboarding, FAQ, migration, support, pricing,
  integration, multi-campus, security/compliance and draft contract material;
- multi-campus remains one campus = one tenant in v8.0.1; organisation-level
  aggregation is deliberately deferred;
- shared `61.8 / 38.2` layout tracks for decision-oriented two-column surfaces;
- a Fibonacci-derived `5 / 8 / 13 / 21 / 34 / 55 / 89px` spacing scale;
- restrained `144 / 233ms` interaction timing with reduced-motion support;
- Portal hero, principal/about, family actions and Quick Registration hierarchy;
- Studio Admin editor/preview hierarchy and Super Admin operational spacing;
- CMS Today Command Centre plus KPI rail on wide screens, stacked on tablets;
- regenerated tenant workspaces and rebuilt browser-loaded CMS output.

Dense tables and operational lists intentionally retain their efficient layout.
Golden ratios establish emphasis; they never override 44px touch targets,
responsive collapse, contrast requirements, or tenant theme choices.

---

## 1. Stack

### Current (canonical)

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Flask, Waitress |
| Database | PostgreSQL 16+ (local), psycopg 3 |
| Frontend | Vanilla HTML/CSS/JS, static tenant templates |
| Auth | Session-based, role-based access control |
| Media | Local file storage (`storage_provider` field reserved for S3) |

This project does **not** currently use FastAPI, SQLAlchemy, Redis, or any microservice infrastructure.

### Target (v2 vision)

A target architecture (modular services: Auth/Tenant/Student/Course/Credit/Attendance/Portfolio/File/Notification/Report; Redis, S3, message queue, read replicas) is documented in `docs/Architecture.md` §7. **Adoption policy:** the current Flask monolith is organised along those module boundaries (modular monolith); heavier infrastructure is deferred to Roadmap Phase 3–5. Do not introduce it during the pilot.

---

## 2. User Levels and URLs

| Level | Who | Main surface |
|---|---|---|
| Product visitor | Prospective customer | `/` product gateway and role entrances |
| Platform Operator | SaaS owner | `/platform-admin` (direct app login); `/super-admin` may be Cloudflare Access protected |
| Studio Owner / Admin | One tenant studio | `/<tenant-slug>/cms` (daily operations) + `/<tenant-slug>/studio-admin` (website/brand/lead-capture settings) |
| Public Parent / Student | Visitors | `/<tenant-slug>` (portal), `/<tenant-slug>/register` |

**Every tenant gets four surfaces** (created from `tenant-template/`, branded via `/v1/public/<slug>/brand`):

| Surface | URL | Purpose |
|---|---|---|
| Portal (门户) | `/<slug>` | Public site: courses, gallery, FAQ, contact, in-page enrolment + private student area (name + mobile + studio-issued 6-digit access code) |
| CMS | `/<slug>/cms` | Staff daily surface: students, roster, check-ins, credits, payments/refunds, logs, analytics, portfolio, and registration review |
| Studio Admin | `/<slug>/studio-admin` | Website/brand console: logo, colours, bilingual public copy, registration fields, preview, draft, publish, and version restore (alias: `/<slug>/cms/studio-admin` redirects here) |
| Register | `/<slug>/register` | Standalone public registration form |

Local URLs (default port 8901):

```
http://localhost:8901/
http://localhost:8901/platform-admin
http://localhost:8901/lets-paint-showcase
http://localhost:8901/lets-paint-showcase/cms
http://localhost:8901/lets-paint-showcase/studio-admin
http://localhost:8901/lets-paint-studio
http://localhost:8901/lets-paint-studio/register
http://localhost:8901/lets-paint-studio/studio-admin
http://localhost:8901/s/lets-paint-studio/v1/tenant     # tenant-scoped API
http://localhost:8901/v1/health
```

Root `/register` is intentionally closed (404) — registration belongs to tenants.
Root `/studio-admin` is the neutral tenant-admin login and requires an explicit
tenant slug; it never redirects to the platform control plane or guesses a
tenant from browser storage.
Root `/cms` is the neutral tenant-operations entry and requires an explicit
tenant slug in SaaS mode; the canonical operational URL remains `/<slug>/cms`.

---

## 3. Project Structure

```
.
├── README.md                     # This file
├── achieve/                      # Local historical archive; not runtime or release source
├── START_STUDIOSAAS_LOCAL.command / start_studiosaas_local.sh
├── RESET_DEMO_TENANT.command      # Guarded reset for lets-paint-showcase only
├── product-home.html              # SaaS product gateway and role entrances
├── customer-resources/            # Reviewed FAQ/release pages and CSV/XLSX templates
├── super-admin.html              # Platform dashboard
├── tenant-template/              # Template copied into tenants/<slug>/ on creation
├── tenants/<slug>/               # GENERATED — never hand-edit (see §4.10)
├── legacy-root/                  # Tenant CMS — the core daily surface (src/cms-app.jsx + build)
├── docs/                         # Product, architecture, API, DB, QA, ops docs
├── deploy/
│   ├── aws/                      # AWS single-instance kit: Dockerfile, compose, nginx, systemd (v7.4.0)
│   └── launchd/                  # macOS LaunchAgent templates (on-demand pilot)
├── dist/                         # Built release bundles (build_aws_bundle.sh output)
└── backend/                      # Canonical runtime
    ├── server.py                 # Flask application (~1860 lines)
    ├── requirements.txt
    ├── pytest.ini
    ├── db/schema_v1.sql          # Kept in sync with migrations (through 0021); ordered migrations are canonical
    ├── studiosaas/
    │   ├── api_v1.py             # All API routes (~8500 lines — split planned, v7 P2-1)
    │   ├── auth.py               # Auth helpers and decorators
    │   ├── models.py             # Role/TenantStatus enums, contexts
    │   ├── errors.py / lifecycle.py / presets.py
    │   ├── db.py / tenant_context.py / workspaces.py / audit.py / config.py / migration.py
    │   └── services/             # media / notifications / student_access / tenant_archive
    ├── scripts/                  # Seed, import, verify scripts
    │   ├── check_terminology.py  # Enforces docs/Glossary.md in CI
    │   └── regenerate_tenant_workspaces.py
    ├── frontend/studio-admin.html
    ├── test_cms.py               # Script-style smoke test (run with python, not pytest)
    └── test_tenant_isolation.py  # Script-style isolation test
```

---

## 4. Local Development Setup

### 4.1 Requirements

- Python 3.11+, PostgreSQL 16+ (Homebrew: 16/18 both fine), pip
- macOS, Linux, or WSL-compatible shell

### 4.2 Virtual environment

The venv lives at the **project root** (`.venv/`), not inside `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 4.3 Database bootstrap

Local database name used throughout docs and scripts: `studiosaas_local_test`.

```bash
createdb -h localhost -p 5432 studiosaas_local_test
export STUDIOSAAS_DATABASE_URL="postgresql://$(whoami)@localhost:5432/studiosaas_local_test"

psql "$STUDIOSAAS_DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/db/schema_v1.sql
```

Preferred bootstrap (migration runner, applies `backend/db/migrations/` in order):

```bash
cd backend && python scripts/run_migrations.py
# existing databases bootstrapped from schema_v1.sql: baseline once first
#   python scripts/run_migrations.py --baseline 0001_schema_v1.sql
```

### 4.4 Seed local data

```bash
cd backend
STUDIOSAAS_ADMIN_PASSWORD='<strong unique local secret>' \
  python scripts/seed_super_admin.py
python scripts/seed_local_test_tenants.py
python scripts/seed_random_demo_data.py --students-per-tenant 24   # optional
```

### 4.5 Start the server

```bash
./start_studiosaas_local.sh          # from project root
# or
cd backend && python server.py
```

Server runs at `http://localhost:8901`.
The launcher checks Homebrew/PostgreSQL/Python dependencies, creates the local
database when needed, applies ordered migrations, and waits for `/v1/health`.
It does **not** seed demo students unless `STUDIOSAAS_SEED_DEMO=1` is explicitly
set.

### 4.6 Pilot credentials

The portable on-demand public launcher checks that the
`admin@studiosaas.local` platform membership exists but never changes any
password. Local/Pilot demonstration credentials live only in the ignored
`.runtime/` directory and move with the project folder. A deliberate shared
demo-password migration is performed only by
`backend/scripts/set_local_demo_passwords.py`; it is not a startup hook.

The shared-password policy applies to the local demonstration environment only
and must never reach the production instance. Privileged production accounts
still lack MFA and a second access layer — that is the highest-priority open
security item on a service that is already live (`docs/HANDOFF_LATEST.md` §0).

### 4.6.1 Portable online runtime

`START_STUDIOSAAS_ONLINE.command` resolves code, environment, CMS data, logs,
PID files and Cloudflare Tunnel credentials from its own project directory.
Move or copy the complete folder—including the hidden `.runtime/` directory—
and the launcher continues to work from the new path. It never reads
`~/.studiosaas`, `~/.cloudflared` or `/private/tmp` for runtime files.

See [`docs/Portable_Online_Runtime.md`](docs/Portable_Online_Runtime.md) for the
runtime layout, verification contract and production boundary.

### 4.7 v7.2.1 shared product improvements

- Public registrations are committed before best-effort applicant and studio-admin email notifications.
- Student profiles support an editable real enrolment date; older records remain unset and reports fall back to trustworthy activity history.
- Registration success pages use an accessible received/next-step/contact flow.
- Portal, Quick Registration, Studio Admin and CMS surfaces share `brand-system.css` semantic typography, colour, date/time and status-output tokens while retaining tenant-configurable accent colours.

### 4.8 v7.3.0 curated brand styles

- Industry presets now apply a recommended visual style together with industry copy and registration questions, with one-click undo before publishing.
- Seven curated styles cover monochrome, editorial, modern, artistic, friendly, bold, and neon-dark directions.
- Each style defines semantic page, panel, text, muted, border, action, and status colours; automatic button text and publish-time contrast checks keep every bundled palette at WCAG AA.
- Tenants can change visual style independently from industry, then fine-tune advanced colours in an explicit Custom state.

### 4.9 v7.3.1 brand-builder usability

- Brand setup now follows three clear steps: industry foundation, colour theme, and studio identity.
- Industry choices remain visual cards, while the seven colour themes use a compact selector with a large live palette preview.
- Manual colour and typography controls stay collapsed until needed, reducing visual noise without removing flexibility.
- Chinese/English labels and mobile navigation were refined and verified at desktop and 390px widths.

### 4.10 Tenant workspaces are generated, not edited

`tenants/<slug>/` is rendered from `tenant-template/` by
`backend/studiosaas/workspaces.py`. **Do not hand-edit a file in there.** A
hand-edit has to be pinned in `tenants/<slug>/.keep-local` to survive
regeneration, and a pinned file stops tracking the template: fixes to the
template never reach that tenant, and improvements made to that tenant never
come back. `lets-paint-studio` sat in exactly that state — 1072 lines against
the template's 956 — so five rounds of template fixes skipped the flagship
tenant.

When a tenant needs something the template cannot express, **add the capability
to the template as a brand field**, then move the tenant's content into its
brand settings. The studio-space carousel and the per-tenant SEO title were
reclaimed this way (`website_profile.about_*` and `website_profile.seo_*`); see
`backend/scripts/reclaim_letspaint_portal.py` for the pattern.

After changing anything under `tenant-template/`:

```bash
.venv/bin/python backend/scripts/regenerate_tenant_workspaces.py
```

### 4.11 v7.3.2 UI/UX, copy and logic pass

Addresses the historical July UI/UX review, now consolidated into
`docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`, across all four surfaces.

- **Security** — the portal's language switch renders with `textContent`, not
  `innerHTML`. Tenant-authored hero/FAQ copy from `/brand` can no longer execute
  as script in a visitor's browser.
- **No placeholder copy in public** — the principal, courses, gallery and FAQ
  sections render only when their data actually arrives. The generated
  "Meet the principal behind X…" default bio is gone.
- **One design system** — `assets/portal-theme.css` is the single palette,
  radius and type source for the portal and the register page, which previously
  declared conflicting `:root` blocks.
- **One registration implementation** — validation, submission and the privacy
  notice version live in `assets/public-register.js`; both public forms call it.
- **Industry vocabulary** — `%VENUE%` / `%WORK%` / `%WORKS%` resolve per
  industry from `presets.py`, so a piano or dance tenant no longer calls itself
  a 画室 with 作品.
- **Bilingual everywhere** — `assets/cms-i18n.js` gives the CMS the EN layer it
  never had, sharing the language choice with Studio Admin and Super Admin.
- **Terminology** — `docs/Glossary.md` fixes one word per concept, enforced by
  `backend/scripts/check_terminology.py` in `verify_local.sh`.
- **Family-facing messages** — editable per tenant under Studio Admin →
  Messages. They used to be literals naming the word "Studio".

### 4.12 v7.3.3 theme system and copy pass

Addresses A1-A4 and B1-B8 of the follow-up design review.

**Themes.** Eight presets, each a matched light/dark pair, in
`backend/studiosaas/presets.py`. Every value is solved for a measured WCAG
target by `docs/design/palette_gen.py` — 390 assertions across 15 theme-modes.
Never hand-edit a hex; change the generator and re-emit.

```bash
python3 docs/design/palette_gen.py            # verify (390 assertions)
python3 docs/design/palette_gen.py --table    # inspect every token
open docs/design/theme-proposal.html          # see all 15 rendered as real UI
```

| Theme | Industry | Hue relationship | Modes |
|---|---|---|---|
| Atelier Clay 陶土工坊 | art | split-complementary | light + dark |
| Vintage Press 复古印刷 | general | split-complementary | light + dark |
| Studio Ink 黑白纸墨 | — | monochrome + one slate note | light + dark |
| Harbour Calm 静谧海港 | math, language | analogous | light + dark |
| Cedar Grove 雪松林 | sports | triadic | light + dark |
| Recital Plum 独奏紫 | music | analogous | light + dark |
| Rehearsal Rose 排练玫瑰 | dance | split-complementary | light + dark |
| Arcade Lime 街机青柠 | game | split-complementary | **dark only** |

- **A1** `border_color` measured 1.26–1.87:1 on all seven old presets, failing
  WCAG 1.4.11 for the input borders using it. Split into `border_color`
  (dividers) and `border_strong_color` (interactive boundaries, ≥3:1).
- **A2** success/warning/danger had 4/2/5 unrelated values. Now fixed hue
  anchors (152/36/6) nudged 4% toward the theme, lightness re-solved per
  surface — identical contrast in every theme.
- **A3** five of seven accent pairs sat 140–175° apart (near-complementary).
  The set now spans split-complementary, analogous, triadic and monochrome.
- **A4** light/dark are designed together, and each carries
  hover/pressed/disabled/focus/scrim so interaction states exist in both modes.

Migrating existing tenants (idempotent; never touches a hand-tuned theme
unless you pass `--include-custom`):

```bash
.venv/bin/python backend/scripts/migrate_visual_themes.py --dry-run
.venv/bin/python backend/scripts/migrate_visual_themes.py
```

**Copy.** Section headings are per-industry (`INDUSTRY_SECTION_COPY`) rather
than one set shipped to every tenant; the hero has a single primary CTA;
empty states offer the next action; error messages state a cause and a way
out; destructive confirmations say what happens and whether it can be undone;
the student area explains where an access code comes from; and the English is
written rather than translated.

### 4.13 v7.3.4 bilingual chain, theme naming, brand-builder layout

**Two real bugs.** The portal's `setLang()` re-rendered programs, gallery, FAQ,
hero copy and the about block but not the contact rows, which build their own
key labels in JS — so 「地址 / 邮箱 / 电话」 stayed Chinese for an English
visitor. And `renderStylePresetGrid()` fell back to `['light']` whenever a
theme's `modes` was absent, then told the owner the theme "ships light only —
its accent cannot reach readable contrast on the other surface", a sentence
nothing had established. Missing data and a single-mode theme are now different
states: `schemes` keys count as evidence, an absent list says so and asks for a
refresh.

**Theme naming and description.** `label_zh` reached the API but no surface
printed it, so a Chinese console offered a choice between "Atelier Clay" and
"Rehearsal Rose". The generator was also emitting each theme's `mood` tag as
its `description`, which is why the panel read `warm, tactile, gallery`. Eight
full sentences now exist in both languages in `presets.py` **and** in
`palette_gen.py`, so re-emitting cannot reintroduce the fragments; `mood`
survives under its own name.

**Choosing a theme.** The dropdown was alphabetical, which opened an art
studio on Arcade Lime — a dark-only neon games palette. Order is now
recommended → both modes → dark-only. The colour relationship (`harmony`) was
already on the wire and is shown as a labelled chip. The palette preview grew
from three unlabelled bars to nine labelled chips, including the
`border_strong_color` and `focus_ring_color` the theme rework exists for.

**Brand-builder layout.** The two step-02 selects sat in different wrappers
(`.theme-picker-control` vs `.form-group`) and measured 214×46 at y=1169
against 380×42 at y=1149; they are one row of equal columns on one baseline.
Industry cards dropped `key.slice(0,3)` ("GEN" and "GAM" are one letter apart
at 10px) for the industry name and an accent dot, and their height follows
content instead of `aspect-ratio: 1.18/1` with a three-line clamp.

**Bilingual chain.** Studio identity joins the bundle that was already
bilingual, already normalised on read, and already preferred by the public
template: `settings.localized_copy` now carries slogan, welcome message,
category label, principal title/bio/quote, the four section labels and the
registration form title as `{zh, en}`. The older flat fields keep the English
value so the CMS, Super Admin and existing tenants are unaffected, and a
tenant's pre-bilingual string seeds both languages rather than being replaced
by an industry default. Studio Admin gained 中文/English twins for each.
`programs[]` and `gallery[].title` stay single-language by decision — see
`docs/Glossary.md`; both entry surfaces now say so on screen.

**Language surfaces.** `?lang=zh` / `?lang=en` makes each language of a public
page a distinct URL; first visit follows `navigator.language` instead of always
landing on Chinese; and `og:locale`, `og:locale:alternate`, the canonical URL
and `hreflang` alternates follow the rendered language, with Chinese as
`x-default`. The two storage keys (`pwe_lang_<slug>` for visitors,
`studiosaas_admin_language` for staff) are documented in `docs/Glossary.md` →
Language surfaces.

Also removed: a decorative "Founder / Principal / Mentor" chip row in the
portal template — hard-coded English with no `data-zh`, asserting three roles
about a real person that no studio had entered.

### 4.14 v7.4.0 role boundaries, accessibility, AWS deployment kit

**Role boundaries** (full audit of every route in `api_v1.py` + `server.py`
against `ROLE_PERMISSIONS` and the CMS UI gates):

- The unscoped legacy surface (`/api/*`, `/photos/*`, `/portfolio/img/*`) is
  **disabled (410) in pilot/production** — it has one shared password and no
  role/tenant model. `/api/ping` stays; `STUDIOSAAS_ENABLE_LEGACY_CMS=1`
  re-enables for a genuine single-studio install.
- `parent`-only users can no longer obtain a staff session: `/v1/auth/login`
  refuses them (403) until the family self-service surface exists, and the
  legacy projection fails closed to an empty payload for the role.
- Financial boundary enforced everywhere it was documented: `/v1/dashboard`
  returns revenue/average-price/liability only to `analytics:read` roles;
  `/v1/packages` (prices) now requires `credits:read`, matching the CMS
  projection that already blanked packages for teachers.
- New granular permissions: `credits:refund` (owner/manager — refunds move
  real money and were open to front-desk/staff) and `portfolio:share`
  (owner/manager — share links expose a named minor's photos publicly).
  Revoking a share link stays `portfolio:write` so any portfolio-writing
  staff can kill an exposed link fast.
- `/v1/legacy-cms/save` moved from owner/manager-only to `students:write` —
  the CMS's own student flows (create/edit/archive) were silently 403-ing for
  front-desk and staff while the UI reported success. `save()` in the CMS now
  propagates failure and resyncs, so no caller reports success on a rejected
  write. Package edits inside the payload still apply only for owner/manager.
- Teacher's dead-end fixed: the role held `attendance:write` but the CMS
  never showed it the roster tab where check-in lives. Teachers now get
  `roster`, and per-day roster actions follow a `canWriteAttendance` flag
  that matches the backend permission.
- Dead permission strings wired to real routes (`tenant:update`,
  `courses:write`, `analytics:read`, `settings:write`), the platform-level
  role-ranking ladder fixed (`manager` ranked below `staff`), tenant filter
  added to the schedule-roster DELETE, and both consoles now recognise only
  the platform (`tenant_id IS NULL`) `super_admin` membership — mirroring the
  backend rule a legacy tenant-scoped row could previously bypass in the UI.

**Accessibility pass** (ui-ux-pro-max review, all four surfaces): every form
control in both admin consoles has an associated label; modals restore focus
and trap Tab; the workbench tabs implement the ARIA tab keyboard contract;
the portal gallery/lightbox is fully keyboard-operable with a real dialog
role; custom registration fields joined the per-field error pattern
(`aria-invalid`, `aria-describedby`, focus move); `aria-label`s localise with
the language switch; the about carousel pauses on hover/focus; Super Admin's
text-glyph icons became inline SVGs; and the portal's last hard-coded warm
hexes became theme tokens (incl. a new `--on-success`).

**AWS deployment kit** — `deploy/aws/` ships Dockerfile, entrypoint
(wait-for-DB → migrations → waitress, refuses production boot without
secrets), docker-compose (RDS by default, `--profile local-db` rehearsal),
nginx and systemd configs, `.env.example`, and `build_aws_bundle.sh`, which
packages a clean git tree into `dist/PWE-StudioSaaS-aws-<version>.tar.gz`
with a `BUILD_INFO` stamp. Runbook: `deploy/aws/README_AWS.md`; verified
end-to-end in Docker (health, migrations, legacy-API 410).

### 4.15 v7.5.0 documentation refresh, UI/UX fixes, role guides

- **Documentation full refresh and correction** — every doc audited against the
  code on 2026-07-26: README enum tables brought back in line with the live
  schema, `docs/Architecture.md` and `docs/Design_System.md` rewritten, and
  stale sprint files (`achieve/codingprompt.md`, `achieve/docs/Current_Sprint.md`) archived in
  favour of `docs/HANDOFF_LATEST.md`.
- **UI/UX fix batch** across the three admin surfaces:
  `prefers-reduced-motion` support, `focus-visible` focus rings, touch targets
  ≥40px, CMS emoji icons reduced to zero, inline login error reporting, and
  `aria-label` coverage completed.
- **`docs/guides/`** — six per-role Chinese user manuals (new this round).
- **ui-ux-pro-max skill** project copy synchronised (84 styles / 192 palettes).

### 4.16 v7.6.0 audit remediation and Super Admin UI upgrade

Full remediation of the 2026-07-27 project audit
(`achieve/docs/Project_Audit_2026-07-27.md`): all 3 HIGH, 13 MEDIUM and 20 LOW
findings closed, plus a professional visual upgrade of the Super Admin
console.

**Backend:**

- `_is_local_request` now decides on `request.remote_addr` (the socket
  peer) instead of the spoofable Host header; the local-admin repair path
  only ever triggers for genuine loopback connections.
- `auth.py` restored the missing `jsonify` import; the CSRF exemption for
  public endpoints now also covers the slug-mounted spelling
  (`/s/<slug>/v1/public/*`).
- The in-memory public rate limiter is thread-safe (single lock) with lazy
  pruning so the store cannot grow without bound; the three call sites that
  mutated the dict directly now go through `_rate_limited()`.
- A bare `transactionType="refund"` is normalised to the `refund_out`
  semantics: credits leave the account, the fee is recorded negative, and
  the balance check applies (previously it *added* credits with a positive
  fee, silently polluting the cash-net roll-up; no shipped client sent it).
- Database-unavailable errors (503) return a fixed message in
  pilot/production instead of echoing driver/connection detail; local
  development keeps the actionable text.
- `check_ui_escaping.py` extended: it now follows template strings assigned
  to variables and passed into `openModal()`-style sinks (the blind spot
  that had produced a false green light).
- New test module `backend/tests/test_v760_backend_fixes.py`; the pytest
  suite is now **131 tests**.

**Database:**

- Migration `0020_drop_redundant_indexes.sql` drops two secondary indexes
  that duplicated the index already backing a UNIQUE constraint
  (`media_variants`, `tenant_brand_versions`); `ON CONFLICT` inference is
  unaffected.
- The DO blocks in 0016 and `schema_v1.sql` catch the correct
  `duplicate_table` exception, so both are safely re-runnable.
- `db.py connect()` accepts `statement_timeout_ms` / `lock_timeout_ms`
  overrides; `run_migrations.py` and `prune_event_tables.py` pass `0` to
  lift the 30s/10s app caps for maintenance work.
- `backup_postgres.py` validates `--keep` (rejects values that would delete
  every backup) and reports a clear hint when `schema_migrations` is
  missing; `schema_v1.sql` carries an explicit PG16+ header note.
- Tenant archives no longer snapshot `users.password_hash` — the `users`
  export is trimmed to an explicit `SNAPSHOT_COLUMNS` list.
- 0001 opens with a migration-freeze policy note: applied migrations are
  never edited retroactively; changes go in new migration files.

**Frontend:**

- `super-admin.html`: logout crash fixed (null guard); status pills meet
  WCAG contrast (4.84–6.92:1); the three destructive confirm buttons
  re-enable via `try/finally`; 29 escaping blind spots closed;
  `admin-i18n.js` gained ~75 keys plus 21 dynamic-string rules (no more
  mixed-language state); dead code removed; and a professional visual
  upgrade of the KPI cards, funnel visualisation, alert components, table
  filters and header button groups (new `--line-strong` / `--row-hover` /
  `--head-bg` tokens).
- `studio-admin.html`: `changePassword` and `restoreBrandVersion` report
  failures instead of failing silently; `categoryOptions` escaped;
  `aria-pressed` on the preview toggles; the hard-coded slug fallback
  removed; the CSS `✎` glyph replaced with an SVG.
- `shared-portfolio.html`: the lightbox is fully keyboard-operable (focus
  trap + Escape) and the page gained a minimal bilingual layer
  (`?lang=` / localStorage / browser language).
- `legacy-root/register.html`: all 16 emoji replaced with SVGs, the
  third-party CDN fallback and `maximum-scale` removed, dynamic
  registration fields get real `label for`/`id` pairs.
- `cms-i18n.js`: language-switch buttons meet the 40px touch target.

### 4.17 v7.7.0 roadmap clear-out, brand identity, Super Admin round 2

**Roadmap leftovers cleared** (Development_Roadmap.md items, all closed):

- **Support gate enforced.** A platform super admin reaching into tenant
  routes now requires an active, audited support session for that exact
  tenant (403 `support_session_required` otherwise; per-tenant; ending the
  session closes access; override `STUDIOSAAS_ENFORCE_SUPPORT_GATE=0`).
  The console's CMS/Studio-Admin quick links route through the
  support-reason dialog; public Portal/Register links stay direct.
  Pinned by five tenant-isolation checks (201 total).
- **Owner audit trail.** `GET /s/<slug>/v1/audit-logs` (owner-only,
  limit/action filters) + an 操作审计 panel in Studio Admin → 数据分析.
- **studio-admin fully tokenised.** 161 raw hex in styles → 0, via 28 new
  semantic tokens; the 33 remaining hex are theme *data* (colour-input
  values, contrast math, API payload defaults) and deliberately stay.
- **Brand form inline errors** — 12 fields validate per-field
  (required/email/phone/URL/timezone/`#RRGGBB`), aria-wired, bilingual.
- **Media token hex 化 closed as no-change**: `media:<uuid>` is already
  122-bit random behind auth/consent gates (rationale in the roadmap).
- **P3-04 Redis** stays deferred by adoption policy (pilot forbids Redis).

**PWE brand identity** (`docs/design/Brand_Identity.md`): "spark inside
the P" — geometric P monogram (platform) with an amber four-point spark
(creativity) in its negative space; Family Navy `#0E1729` + Family Amber
`#F5B335`; wordmark authored as pure geometry (no font dependencies).
All root icons/manifest regenerated deterministically from one geometry
table (`docs/design/brand/render_assets.py`); theme-aware `favicon.svg`;
every surface carries the platform favicon set; the Super Admin header
mark is the inlined SVG.

**Super Admin console round 2**: the 54 untranslated strings found in the
live walkthrough all translate now (plan quota lines restructured into
per-limit nodes to be dictionary-matchable); audit timestamps render
locale-aware with raw values in tooltips; health badges joined the status
pill system (AA contrast, SVG icons); spacing moved to a token scale.

**CMS/Portal walkthrough fixes**: pending-list timestamps shortened to
minutes (raw in tooltip), all 10 registration statuses render in Chinese,
same-mobile pending entries get a 疑似重复 badge, course duration is
bilingual (60 分钟 / 60 MIN), broken gallery/hero images degrade cleanly
(tiles removed from tab order, hero falls back to decorative art).

**Role guides** (`docs/guides/`, current guides stamped 8.1.0): new dedicated
Front Desk/Staff guide (previously "see Manager"), support-gate and
owner-audit sections rewritten to match enforced behavior, share-link
create/revoke permissions corrected everywhere, and each guide gained a
role-specific FAQ (login failure kinds, missing-button explanations,
refunds, access codes, share links, language keys, duplicates).

### 4.18 v7.7.7 production-readiness remediation, DB security pass, sales kit

Two formal audits (AWS Well-Architected + a dedicated database-security
sweep) ran against v7.7.0 with one tenant already holding real data; every
blocker and pre-launch item was fixed:

**Deployment kit** — production pins in `deploy/aws/requirements.lock`
(the image no longer resolves floating ranges); `pg_dump` inside the image
plus a real backup section (README_AWS §9: daily cron, 0600 dumps, EBS DLM
volume snapshots for media/archives/tenants, quarterly restore drill);
nginx TLS bootstrap config ends the certbot chicken-and-egg; a tenants
volume + boot-time workspace regeneration so runtime-created portals
survive image rebuilds; compose log caps, SMTP/SES + DB-timeout env
passthrough; systemd ReadWritePaths covers tenants/archives; migration
steps gain data-volume copy + chown.

**Database security** — least-privilege RDS role + `sslmode=require`
mandated in the kit; `backup_postgres.py` chmods dumps 0600, keeps the DB
password off argv (PGPASSWORD), and warns when the target directory syncs
to iCloud; `/public/<slug>/balance-query` requires the student's access
code once one is issued (closing a name+phone enrolment oracle for real
families); `/student/unlock` gains a flat per-IP ceiling and constant-work
dummy verification (timing oracle closed). The audit otherwise returned
SECURE: parameterized SQL throughout, PBKDF2-600k credentials, hashed
tokens, complete tenant isolation, support-gate coverage.

**Observability** — `/v1/health?deep=1` probes the database and the
container healthcheck uses it; CloudWatch minimum-alarm set and event-table
pruning are in the §8 checklist.

**Sales kit** — `docs/sales/PWE_Studio_销售介绍.pptx` (13 slides,
Feather Star brand story, every product claim verified against the repo) plus
`talk_track.md` presenter script with objection handling.

### 4.19 v7.7.8 dual-mode release closure

**Edition install and upgrade** — standalone startup now requires exactly one
tenant in total, exactly one active tenant, and zero platform memberships.
The installer places secrets, backup history and the current-release pointer
in stable host paths, installs a root-owned backup schedule, creates the first
dump, and runs the web process with a dedicated least-privilege PostgreSQL
role. `upgrade.sh` backs up before switching releases and automatically rolls
back code/config when deep health fails; `maintenance.sh` provides explicit
backup, restore rehearsal and write-stopped real restore operations.

**Migration integrity** — Edition export format v2 inventories database and
media payload files. Import requires the separately trusted outer bundle
SHA-256 and rejects missing, changed or undeclared payloads before applying
data.

**Release gate** — CI and the local release verifier run PostgreSQL migrations,
pytest, the 73-check CMS smoke suite, tenant-isolation checks, CMS source/build
consistency and clean-tree builds of both SaaS and Edition bundles. Bundle
metadata must match version, mode and commit, while internal handoff/audit
materials stay out of customer packages.

**Deliberate boundaries** — v7.7.8 validates the local service and on-demand
Cloudflare invitation path. AWS deployment and automated media-volume backup
remain deferred by product decision.

### 4.20 Current brand family integration

**Brand architecture** — PWE Studio uses the Feather Star: the four-point star
is the starting point of creativity, while the three feather blades represent
growth, ascent and possibility. Paradise Production · 天域文创 retains the wing
producer mark. Both use
Family Navy `#0E1729`, Family Amber `#F5B335` and Warm Paper `#F7F5F2`
without merging the two identities. `01 BRAND ASSETS/` is the complete
delivery kit, including placement rules, machine-readable tokens, normalized
raster exports, deterministic generators and a SHA-256 asset manifest.

**Tenant identity** — Studio Admin, Portal, Register and CMS keep the tenant
Logo/name in the primary position in both operating modes. They use only the
compact `Powered by Paradise Production` footer credit by default; paid
removal remains an explicit, strict
`STUDIOSAAS_SHOW_PRODUCER_CREDIT=0` deployment setting.

**Product and sales sync** — platform shell, PWA icons/manifests,
password setup, admin chrome, 13-slide sales deck and talk track share the
same family palette. Functional blue/status colours and tenant themes stay
semantically separate from family amber.


---

## 5. Environment Variables

```bash
export STUDIOSAAS_DATABASE_URL="postgresql://localhost/studiosaas_local_test"
export STUDIOSAAS_ENV="local"
export PORT="8901"
export STUDIOSAAS_API_KEY="independent-random-secret-at-least-32-characters"
export STUDIOSAAS_SESSION_SECRET="different-random-secret-at-least-32-characters"
export STUDIOSAAS_MEDIA_DIR="./media"
export CMS_DATA_DIR="/private/tmp/studiosaas_cms_data"
# Edition only; defaults to 1 in standalone mode. Set 0 only under the paid
# attribution-removal commercial option.
export STUDIOSAAS_SHOW_PRODUCER_CREDIT="1"
```

Production must not rely on local secret files (`backend/.api_secret`, `backend/.session_secret`, `backend/.cms_password` are local-only and git-ignored). Production startup requires independent API and session secrets and rejects equal values. See `docs/Release_Runbook.md` for the complete release configuration and gate.

---

## 6. Canonical Enums (as enforced by the database today)

These are the values the schema actually CHECKs (through migration 0019; roles per 0013, lifecycle states per 0012). Code, seeds, UI, and docs must match them. **`docs/Database.md` §3 is the authoritative reference** — this table is a convenience copy. Extensions go through migration files only.

| Concept | Where | Values |
|---|---|---|
| Membership role | `memberships.role` | `super_admin`, `owner`, `manager`, `teacher`, `front_desk`, `staff`, `parent` |
| Tenant status | `tenants.status` | `lead`, `trial`, `onboarding`, `active`, `past_due`, `paused`, `cancelled`, `archived`, `deleted` |
| Subscription status | `subscriptions.status` | `trialing`, `active`, `past_due`, `paused`, `cancelled`, `archived` |
| Credit transaction | `credit_transactions.transaction_type` | `purchase`, `consume`, `adjustment`, `refund`, `expire`, `migration` |
| Registration status | `registrations.status` | `pending`, `contacted`, `trial_booked`, `waiting`, `approved`, `converted`, `rejected`, `duplicate`, `lost`, `archived` |
| Media visibility | `media_assets.visibility` | `private`, `public_token` |

**Note:** `users` has **no role column** — roles live on `memberships` (user × tenant). A platform administrator is a `super_admin` membership with `tenant_id IS NULL`, which grants access to every tenant including ones created later (P0-01, done 2026-07-03).

---

## 7. Testing and Verification

```bash
# Syntax check (from project root)
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py

# Unit/boundary tests (install dev deps first: pip install -r backend/requirements-dev.txt)
cd backend && ../.venv/bin/python -m pytest -q

# Script-style smoke tests (run with python, NOT pytest)
cd backend
../.venv/bin/python test_cms.py                 # expected: 73 checks passing
../.venv/bin/python test_tenant_isolation.py

# Reproducible source package (requires a clean committed tree)
bash scripts/package_release.sh

# Terminology (one agreed word per concept — docs/Glossary.md)
python3 backend/scripts/check_terminology.py

# Regenerate tenant workspaces after a tenant-template/ change
.venv/bin/python backend/scripts/regenerate_tenant_workspaces.py

# Full local verification
bash backend/scripts/verify_local.sh

# Release gate: PostgreSQL checks may not be skipped
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh
```

Manual checks with the server running:

```bash
curl -sS http://localhost:8901/v1/health
curl -i -X POST http://localhost:8901/v1/admin/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Bad","slug":"bad","planCode":"starter"}'   # must be 401/403
```

---

## 8. Security Baseline

- All admin mutation routes require authentication; tenant routes enforce membership; platform routes require super admin.
- Public endpoints and login endpoints are IP/email rate-limited in memory for the local pilot; failed logins are audited.
- Uploads validate extension/MIME/size; media is tenant-scoped; no path traversal.
- Passwords: PBKDF2-HMAC-SHA256; legacy unsalted SHA-256 hashes are accepted once on successful login, then upgraded in place.
- Secrets are never committed; see `.gitignore`.
- Cross-tenant access must always fail — covered by `test_tenant_isolation.py`.

---

## 9. Documentation Index

| Document | Content |
|---|---|
| `docs/HANDOFF_LATEST.md` | **Current status and open work — start here** |
| `achieve/codingprompt.md` | Archived v7.0 sprint prompt (historical; no longer maintained) |
| `achieve/docs/Current_Sprint.md` | Archived v7.0 sprint status tracking (historical) |
| `docs/StudioSaaS_Blueprint_v2.md` | Product vision, market, pricing, MVP acceptance criteria |
| `docs/Product_Surface_Model.md` | Canonical surface names and responsibilities |
| `docs/Architecture.md` | Current architecture + target architecture (v2 vision) |
| `docs/API.md` | Endpoint reference, auth model, route protection |
| `docs/Database.md` | Schema reference, canonical enums, migration strategy |
| `docs/Development_Roadmap.md` | Phases 0–5, target-stack adoption mapping |
| `docs/QA_Checklist.md` | Pre-release checklist |
| `docs/Admin_Guide.md` | Platform ops: setup, backup, troubleshooting |
| `docs/Release_Runbook.md` | Provider-neutral migration, media backfill, release, rollback, and recovery gate |
| `docs/Deployment.md` | Deployment stages; Stage 2 (AWS Lightsail) live since 2026-07-30 |
| `docs/Design_System.md` | UI tokens and component standards |
| `docs/Glossary.md` | One agreed word per concept (enforced by `check_terminology.py`) |
| `docs/guides/` | Per-role user manuals in Chinese (applicable to v9.8.0) |
| `01 BRAND ASSETS/` | PWE/Paradise family delivery kit and validated asset manifest |

---

## 9.1 Current CMS information architecture

The CMS workspace is organised by work location rather than one flat list:
「今日」 contains **工作台** and **待处理**；「教学运营」 contains
**课程安排、课程、学员、作品**；「经营」 contains **充值与退款** and
**经营统计**；「记录」 contains **操作日志**. 账号、团队、运营默认和
数据维护 remain under **系统设置**. Public-site brand and registration-field
configuration remains in Studio Admin, while the Portal remains family-facing.

## 10. Project Philosophy

**Clarity creates trust.**

- For studio owners, daily operations get simpler.
- For parents, registration feels clear and reassuring.
- For platform operators, tenant management stays controlled and auditable.
- For developers, the codebase gets easier to understand after every sprint.

The product grows from a working local CMS → stable multi-tenant pilot platform → polished creative studio SaaS, without losing data integrity, tenant isolation, or operational clarity.

Do not add payments, complex billing, or enterprise features before pilot data safety and tenant isolation are stable.

---

## 11. License

Copyright 2026 Lee Liu.

Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE)
for attribution information.

---

*Powered by Paradise Production · 天域文创*
