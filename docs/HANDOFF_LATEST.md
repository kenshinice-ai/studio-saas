# PWE Studio v8.2.4 — Current Handoff

## Theme completeness, console information architecture, SEO — packaged (2026-08-01)

**Baseline:** v8.2.3. **Branch:** `claude/ui-ux-pro-max-audit-073a82`.

### The Tailwind debt was measured, not guessed

The CMS carries 1,422 Tailwind colour utility uses across 154 distinct
utilities, remapped to tenant tokens by role (danger/success/structure) in the
shell stylesheet. Scripted coverage analysis against the `[class*=]` mapping
table found **148 of 154 already re-pointed** — the architecture works. The
entire gap was `ring-*`, which Tailwind implements through its own
`--tw-ring-color` and which the role map never claimed: all 65 focus rings drew
Tailwind indigo, so a clay or forest studio got an indigo halo on every focused
input, and on a dark theme an indigo ring against a dark panel can fall under
the 3:1 WCAG 1.4.11 requires of a focus indicator. The tenant palette had
shipped `focus_ring_color` all along.

`ring-*` is now mapped by family — not by the six utilities in use today — so a
ring added later is themed on arrival. Coverage is now 1,421/1,422; the
remaining `placeholder-gray-400` is already handled by the shell's generic
`::placeholder` rule. **No tenant rebuild was needed**: the problem lived in one
shared stylesheet, not in tenant data, so deleting and recreating the six
workspaces would have carried risk for zero benefit.

### Platform console reordered as a work surface

Overview presented eight counters in one undifferentiated grid, giving "Past
Due" (chase an invoice) the same weight as "Total Tenants" (a standing fact),
and put the list naming the at-risk tenants *below* all eight. It is now
ordered by what the operator does with each block: **Needs attention** (Past
Due / Trials Ending / Onboarding, with Commercial Attention directly beneath) →
**Business health** (five standing totals) → **30-Day Acquisition Funnel**,
last and collapsed by default. All ids unchanged; the JS addresses them by id,
so no data path moved.

### Studio Admin controls simplified without losing customisation

- Six "Show / Hide" dropdowns — two taps and a popup each to set a boolean —
  are one switch list. State is carried by knob position as well as colour, so
  it survives a colour-blind reading. Same six settings, same ids.
- The eight visibility controls moved from `<select>.value` to
  `.checked` via `toggleOn()` / `setToggle()` helpers; 24 call sites converted,
  zero `.value` references left. `change` listeners were untouched (checkboxes
  fire it too).
- Five fine colour inputs are collapsed behind a disclosure. Every field stays
  present and editable — the theme picker above already produces a complete,
  contrast-checked palette, so this is refinement, not setup.

### Product home

Release-evidence link removed from the public footer and placed inside
`/platform-admin` (it is an internal delivery record, and the public link had
gone stale — still pointing at the v8.1.0 notes two releases later).
Reachability for both audiences is now asserted by tests rather than assumed.

SEO: the title led with the brand and a tagline, so the page ranked for nothing
but its own name. It now leads with what a studio owner searches for, under 60
characters, plus canonical, keywords and Open Graph/Twitter cards so a shared
link renders as a titled card instead of a bare URL.

### Verification

```text
pytest: 309 passed (2 new reachability tests)
Legacy CMS smoke: 73/73 · Tenant isolation: 228/228
Tailwind coverage: 148/154 -> 153/154 distinct (1,421/1,422 uses)
Browser (local, Chrome):
  platform console order: Needs attention -> Commercial Attention ->
    Business health -> funnel (collapsed); funnel still loads on expand
  Studio Admin switches: all 8 load from server state as checkboxes
  round-trip: Gallery off -> Save Draft -> websiteProfile.showGallery=false
    in DB, other seven unchanged -> reload shows off -> restored to on
  switch geometry 46x26, on=brand accent knob right, off=grey knob left
  both consoles verified in Chinese and English; no console errors
```

Two defects were found by browser verification and fixed before release: the
new group headings were not in the i18n dictionary (English text on a Chinese
page), and the switch resolved `--accent`/`--panel`/`--focus-ring`, none of
which Studio Admin defines — it uses `--brand-accent` — so the track rendered
transparent and 42px tall under the global `input` rule.

# PWE Studio v8.2.3 — Historical Handoff

## Audit remediation round — packaged (2026-08-01)

**Baseline:** v8.2.2, commit `dc06b8c`. **Branch:** `claude/ui-ux-pro-max-audit-073a82`.

### Release hygiene repaired first

`main` had been left at v8.0.1 while v8.2.0/8.2.1/8.2.2 shipped from
`codex/v8.2.1-ics-p0`, and the tag series stopped at `v8.0.1`. Anyone starting
from `main` would have silently reverted the ICS and consent-checkbox repairs.
`main` was fast-forwarded to `dc06b8c` (no divergence — 23 commits ahead, 0
behind) and the missing annotated tags `v8.2.0`, `v8.2.1`, `v8.2.2` were
created on their release commits. Keep releasing onto `main` from here.

### What v8.2.3 fixes

**Operations log was structurally incomplete.** In SaaS mode the CMS log is
synthesised from the credit ledger, so it could only ever show check-ins,
top-ups, adjustments and refunds. Archiving, renaming, roster changes,
portfolio and consent edits were sent inside `save()`, which persists students
and packages and drops everything else — those operations were recorded in
`audit_logs` server-side but no CMS surface read that table. The log page now
merges `/v1/audit-logs` into the ledger rows under a whitelist that excludes
platform noise (`auth.*`, `support.*`, `tenant.*`) and the three actions the
ledger already covers, so nothing appears twice. Each merged row names the
actor. The endpoint is owner-scoped; other roles get 403 and keep the
ledger-only view rather than an error they cannot act on.

**Roster entries had no time.** "加入今日排课" from a student profile and
班组模板套用 both called the roster endpoint without `classTime`, so the entry
stored `class_time` NULL and the day grouped the student under 时间未设置 —
while the roster page's own add box has always defaulted to the studio's
configured time. Both paths now send a time: the weekly schedule's slot when
one already places that student, otherwise the studio default.

**Assets could be served from a previous release.** `/assets/cms-app.js` and
its siblings live at stable paths, so a browser, PWA or CDN edge holding an
older copy runs last release's JavaScript against the current API — which is
what the reported "编辑后无页面" turned out to be, and it survives a reload.
Every HTML shell now carries an `__APP_VERSION__` placeholder on each JS/CSS
URL, stamped at serve time from `APP_VERSION`, so the version can never drift
from the running release. All eight HTML-serving routes were moved onto the
stamper; browser verification caught one route
(`/<slug>/studio-admin`) still leaking the raw placeholder, now fixed. The six
generated tenant workspaces were regenerated so they carry it too.

**Polish:** the dashboard's 长期未到访 list printed the `daysSince` sentinel
as "9999天前" and now reads 从未上课; the student-card roster button said
去排课 when the student was already on today's roster and 排课 when they were
not (backwards on both) and now matches the profile sheet's 查看排课/加入排课;
the ledger's importer note ("Core opening balance import source:…") is shown
as 数据迁移期初余额; the balance field in the edit form no longer uses a
tinted fill that read as disabled.

**Not changed:** the CMS carries ~1,389 Tailwind colour utilities remapped to
tenant themes by the shell stylesheet. It is architectural debt, not a defect —
every tenant theme verified correct in this round — so it was left alone per
the "fix it if it breaks" instruction. An earlier audit note claiming the CMS
sidebar buttons lacked accessible names was a misread of the browser tool's
output; the buttons carry visible text and `Icon` is already `aria-hidden`.

### Verification

```text
pytest: 307 passed
Legacy CMS smoke: 73/73
Tenant isolation/privacy: 228/228
UI escaping, terminology, inline scripts, CMS bundle freshness: pass
Browser (local, v8.2.3, Chrome):
  operations log 43 -> 45 rows; the profile-path roster add that was
    previously invisible now appears with its actor
  roster add via profile -> class_time 14:30 in daily_roster_entries
    (the pre-fix entry on the same day remains NULL, shown side by side
    as 14:30 / 时间未设置)
  student cards: 23 加入排课 + 1 查看排课, matching roster state
  长期未到访: 12 rows read 从未上课, zero "9999"
  front-desk role -> /v1/audit-logs 403, log page degrades to ledger view
  all 9 HTML surfaces: zero unsubstituted placeholders, assets stamped v8.2.3
  no console errors
```

`media derivative backfill is incomplete` is the one non-passing gate line. It
is a worktree artifact: `backend/media/` is git-ignored, so the original files
live only in the primary checkout and no derivative can be generated from an
absent original. It is unrelated to this round's changes.

# PWE Studio v8.2.2 — Historical Handoff

## P0 public-registration consent visibility hotfix — deployed (2026-08-01)

**Current production truth:** branch `codex/v8.2.1-ics-p0`, packaged application
commit `976385874c085d30379f8ffc475ca4cb20a2e235`, active Lightsail release
`/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.2.2`, image
`studiosaas:8.2.2`. Internal and public deep health report
`appVersion=8.2.2`, `db=ok`, `mode=saas`. This release retains the complete
v8.2.1 ICS endpoint-kind repair and adds the public registration fix below.

### Root cause and repair

The Studio Portal wraps its mandatory privacy checkbox in `.fld`. The shared
`.fld input` rule intentionally sets `appearance:none` for text inputs and
selects, but it also matched this checkbox. Chrome changed the checked value
while continuing to draw an empty box, and the existing validation error stayed
visible. Visitors therefore had no credible feedback that their click worked
and reasonably believed the form could not proceed.

v8.2.2 restores the native checkbox control on both public registration
surfaces, retains the tenant accent colour, resets inherited text-input padding,
and keeps the whole consent label as the 44px-or-larger touch target. Once the
mandatory box is checked, its field error and ARIA invalid state clear
immediately. Generated tenant workspaces were refreshed from the authoritative
templates so existing and future tenants receive the same repair.

### Acceptance evidence

```text
Focused portal/theme/workspace tests: 32 passed
Full pytest suite: 305 passed, 2 skipped
Legacy CMS smoke: 73/73
Tenant isolation/privacy: 228/228
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
Local browser, Studio Portal:
  checkbox click -> accessibility state [checked]
  native visible tick rendered in the tenant theme
  validation error shown when unchecked and cleared immediately when checked
Local browser, Quick Registration:
  checkbox click -> accessibility state [checked]
Production browser, Studio Portal:
  checkbox click -> accessibility state [checked] and visible tenant-colour tick
  unchecked validation error -> checked -> error cleared immediately
Production browser, daily roster ICS retained from v8.2.1:
  preview 2 events (1 class + 1 explicit 1-to-1)
  GET daily-roster/calendar.ics 200
  downloaded 1469-byte vCalendar, 2 VEVENT, Melbourne TZ
No registration was submitted and no production roster data was changed during
browser acceptance.
```

Release artifacts:

```text
PWE-StudioSaaS-aws-8.2.2.tar.gz
  sha256 2d5a2fd2d3e487be656e6027599c21a071a12347a8a361fe0763431d86930917
PWE-Studio-Edition-8.2.2.tar.gz
  sha256 6945cfe7b5fa50fd2fa7f06d59b0dab3dc1868364e95ae0db3144888da44201a
```

Both bundles passed checksum, BUILD_INFO, entrypoint and exclusion checks. The
deployment controller created a PostgreSQL logical dump and media-volume archive
at 06:15 UTC before switching from retained v8.2.1 to v8.2.2. HTTP redirects to
HTTPS, TLS verification is 0, the public edge returns HTTP/2 200, and both
containers are healthy.

# PWE Studio v8.2.1 — Historical P0 ICS handoff

## P0 ICS endpoint-kind hotfix — deployed (2026-08-01)

**Current production truth:** branch `codex/v8.2.1-ics-p0`, application commit
`1cada917d05c09e50fd5fc4b7f658baf274de517`, active Lightsail release
`/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.2.1`, image
`studiosaas:8.2.1`. Internal and public deep health report
`appVersion=8.2.1`, `db=ok`, `mode=saas`.

### Root cause and repair

Production access logs proved the selected-day button first requested
`/daily-roster/calendar`, then incorrectly downloaded
`/class-schedules/calendar.ics` and received 409. The browser merged
`{kind, ...calendar}`: the server-owned document kind `daily-roster`
overwrote the UI endpoint selector `roster`, so the download branch fell into
the weekly-schedule endpoint. Its automatic conflict refresh then replaced the
correct daily preview with the tenant's empty fixed schedule, producing the
reported zero-event dialog.

v8.2.1 keeps the two concepts separate:

- server document kinds remain `daily-roster` and `weekly-schedules`;
- UI routing uses a separate `downloadKind` constrained by one explicit
  preview/download endpoint contract;
- the browser rejects a preview whose server kind does not match the requested
  export instead of silently selecting another endpoint;
- the same `downloadKind` is retained during revision-conflict refresh.

### Acceptance evidence

```text
Focused ICS/API/UI/resource suite: 126 passed
Full pytest suite: 303 passed, 2 skipped
Legacy CMS smoke: 73/73
Tenant isolation/privacy: 228/228
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS

Local browser, populated fixed schedule:
  preview 3 events -> GET class-schedules/calendar.ics 200
  downloaded file 1975 bytes, 3 VEVENT, weekly RRULE, Melbourne TZ, valid VCALENDAR
Local browser, selected day:
  preview 1 group event -> GET daily-roster/calendar.ics 200
  downloaded file 1144 bytes, 1 VEVENT, Melbourne TZ, valid VCALENDAR
Production browser, selected 2026-08-01 roster:
  preview 2 events (1 class + 1 explicit 1-to-1)
  GET daily-roster/calendar.ics 200
  downloaded lets-paint-studio-roster-2026-08-01 (1).ics
  1469 bytes, 2 VEVENT, Melbourne TZ, valid VCALENDAR
```

The production tenant currently has no saved fixed classes. Therefore
`固定课表 ICS` is correctly disabled there rather than producing an empty
file; its populated-data browser path was accepted against the isolated local
PostgreSQL tenant. No production schedule or roster data was added, removed or
changed during this hotfix.

Release artifacts:

```text
PWE-StudioSaaS-aws-8.2.1.tar.gz
  sha256 fdeff388c2367ba0a9219cd95cbaeac2635306941f84326040c3b4f4694fbbe3
PWE-Studio-Edition-8.2.1.tar.gz
  sha256 5d97eb8d2796be9a0d8ffa8fbaa7f440256cc50036fe99f838885913e112d4d6
cms-app.js local/live
  sha256 b03371eac4ed321b9bc4a53cf9e97548e337386e18419997c5866fa9190e20f9
```

The deployment controller created fresh logical and media-volume backups at
05:57 UTC before switching from retained v8.2.0 to v8.2.1. HTTP redirects to
HTTPS, TLS verification passes, the public edge returns HTTP/2 200, and the CMS
asset is `no-cache`, so a normal page refresh retrieves the repaired bundle.

# PWE Studio v8.2.0 — Historical release handoff

## Active release — daily roster convergence and lighter product home (2026-08-01)

**Current repository truth:** branch `codex/v8.0.1-aws-production`, version
sources set to **8.2.0**. Application commit
`ccc3b9cba3063d74382b83f6d628c4ad5d2546e0` was packaged and deployed to
Lightsail on 2026-08-01. The active release is
`/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.2.0` and the running image is
`studiosaas:8.2.0`.

The post-v8.1.1 user acceptance screenshots exposed a context bug rather than
an ICS serializer bug: the top button previewed an empty recurring schedule
while the visible Lucas 12:30 row belonged to the selected day's private
roster. v8.2.0 makes those two products explicit:

- **Fixed schedule ICS** stays in the weekly-schedule card, contains no student
  identities and is disabled when there are no fixed classes.
- **Export selected day ICS** stays with the selected roster, appears only when
  the day has effective students, requires `data:export`, warns that it contains
  student names and never includes guardian names.
- Same-time ordinary entries remain one group event; only explicit 1-to-1
  entries split and conflict. A 409 revision mismatch now refreshes inside the
  modal and requires confirmation again without a page-level red toast.
- Tenant-wide `defaultClassTime` is stored in PostgreSQL settings, initially
  **14:30**, editable by Owner/Manager in CMS Settings, and seeds new manual,
  template and fixed-class controls without rewriting existing bookings.
- The selected-day planner uses the 38.2/61.8 date/action hierarchy; batch
  templates start folded, inherited schedule times render correctly, reminders
  include the effective time and mobile has no floating language control over
  roster actions.

The product homepage now follows the same golden hierarchy: Warm Paper owns
61.8% of the desktop hero and Navy is a 38.2% artwork anchor. Owner/industry
cards are light, and the support section limits Navy to the 38.2% copy panel.
Mobile uses a light story followed by a contained Navy artwork panel. Mail and
Messages remain device-native; no acquisition automation was introduced.

Behavioural comparison and retained PWE security advantages are recorded in
`docs/Daily_Roster_ICS_Drift_2026-08-01.md`.

### Current verification evidence

```text
Focused roster/calendar/security tests: 82 passed
Full pytest suite: 302 passed, 2 skipped
Legacy smoke: 73/73
Tenant isolation/privacy: 228/228
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
Desktop roster: 1440px client = 1440px scroll; default 14:30; empty fixed ICS disabled
Mobile roster: 375px client = 375px scroll; templates folded; language overlay absent
Desktop home: CSS hero split resolves to Warm Paper 0–61.8%, Navy from 61.8%
Mobile home: 375px client = 375px scroll; Warm Paper hero; contained Navy artwork panel
Live home: desktop 1440=1440, mobile 375=375, theme #F7F5F2, version 8.2.0
Internal/public deep health: appVersion=8.2.0, db=ok, mode=saas
Public routes: home, product, CMS, Studio Admin, register, FAQ, privacy, terms, support = 200
Unauthenticated tenant-scoped operational-settings write: 401
```

Release artifacts and deployment identity:

```text
PWE-StudioSaaS-aws-8.2.0.tar.gz
  sha256 b8a8b68f99bc99ffa8aabcc7d6ae468f6713834d5e00158f378eb828c3b7fb13
PWE-Studio-Edition-8.2.0.tar.gz
  sha256 beaade6016388c75701eac3fb36de54544266e0ed7045c6a93f0a870172d135d
cms-app.js local/live
  sha256 c732f9a5830b93165d10c0858b8acb36141b66f6b960a066d78cf41e00889caa
cms-i18n.js local/live
  sha256 122bc3580cc3f1c537195ce5ddc41d3ce6fd3776c7c545addab389d38e6ea4c1
```

The deploy controller created fresh pre-mutation logical and media-volume
backups and retained the validated v8.1.1 release for rollback. The daily
same-instance backup cron last completed successfully at 03:15. Off-instance
or local backup remains an explicit future task and is not called disaster
recovery.

The authenticated roster/calendar behaviour is covered by route, permission,
revision, grouping and serializer tests plus local browser acceptance. Live
assets and the tenant-scoped authentication boundary were verified without
using or disclosing a production operator credential. The only delivery item
outside the running service is Git push: the configured remote must be
explicitly confirmed as owner-controlled before the nine local commits are
published.

# PWE Studio v8.1.1 — Deployed production record

## v8.1.1 release acceptance (2026-08-01)

**Historical truth:** repair commit `282e384` was packaged and deployed to
Lightsail. Internal and public deep health reported `appVersion=8.1.1`,
`db=ok`, `mode=saas`; the public CMS asset matched the local SHA-256. The later
v8.2.0 section above supersedes this release for current work.

### Completed in the v8.1.1 candidate

- **ICS end to end:** canonical revision-bound preview/download, deterministic
  filenames, all-day semantics, 409 refresh/reconfirmation, explicit private
  daily-roster warning, `data:export` enforcement and modal keyboard handling.
  Weekly schedule ICS contains no identities; daily roster ICS may contain
  student names and never guardian names.
- **PIN decision:** removed the reversible Base64/localStorage PIN. It was not
  authentication and had an unsafe mobile recovery path. CMS now relies on the
  server session and provides an explicit server logout.
- **One CMS visual system:** all Tailwind colour families resolve by role to
  the tenant's 21 semantic tokens; OS dark preference is only a pre-brand
  fallback. Once `/brand` resolves, `data-brand-scheme` is the sole theme owner.
- **Golden-ratio core:** shared 61.8/38.2 hierarchy and
  `5/8/13/21/34/55/89` spacing remain canonical. Shared interaction tokens now
  include 44px touch targets, 46px controls, 8px gaps and 8/13/21px radii.
- **CMS/mobile accessibility:** 36/40px target classes removed, primary modals
  trap and restore focus, portfolio thumbnails are keyboard actions, image alt
  text is present, and nested portfolio dialogs no longer compete.
- **Registration:** required identity/contact/privacy fields stay visible;
  optional details, message and publication consent use progressive disclosure.
  Mobile gets a compact header, safe-area sticky submit and touch-sized labels.
- **Deployment rollback:** controller captures and validates the previous
  version before mutation, treats internal/public health separately, restores
  both symlink and version, and fails explicitly if rollback restart or health
  verification fails.
- **Legal/support:** public Support Policy added and linked from Terms/FAQ;
  privacy text now distinguishes weekly schedule and daily roster ICS. Internal
  product/legal consistency review is complete in
  `docs/customer/Legal_Review_2026-08-01.md`; Australian lawyer sign-off and the
  listed commercial particulars remain mandatory before first signature.

### Deliberately deferred

- Main-site acquisition automation: unchanged. Actions continue to open the
  user's own Mail or Messages client; no delivery claim is made.
- Off-instance/local backup copy: deferred by owner decision. Lightsail's daily
  same-instance backup and restore evidence remain; do not call that disaster
  recovery.
- MFA, monitoring, backup-failure alerting, on-call ownership and contractual
  SLA remain disclosed live-service gaps.

### Verification completed so far

```text
Focused legal/UI/deployment suite: 124 passed, 1 skipped
Post-document UI contract suite:   91 passed
Legacy smoke:                      73 passed
Tenant isolation/privacy:          225 passed
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
```

# PWE Studio v8.1.0 — Deployed production record

Current version: **8.1.0** (`VERSION`, `backend/server.py` `APP_VERSION`,
`deploy/aws/lightsail.env.example`)
Working branch: `codex/v8.0.1-aws-production`
Baseline: tag `v8.0.0`, commit `abc01ce6e4f281056c3c22fa665e42d7811e0688`
Prior release branch: `codex/v8.0.1-product-home-brand-release`
Post-release corrective branch: `codex/super-admin-tunnel-chain-fix`

**Section order is newest first for §10, then the 2026-07-29/30 record in
§0–§9.** §0 is the production truth and stays the first thing an operator reads
after §10.

## 10. Post-launch P0 fixes and the 8.1.0 version bump (2026-07-31)

Everything below shipped after `pwestudio.online` went live (§0). The version
moved 8.0.1 → **8.1.0** because the release now contains a production
deployment, a customer-visible defect fix and a commercial quota change — not a
patch-level correction.

**Read §7.5 with this section.** §7.5 records the v8.1.0 deploy itself and the
two defects that deploy exposed (an image tag naming the wrong version; the
renamed release-notes URL 404ing). This section records the version bump, the
product fixes it carries and the documentation sweep that made the repository's
prose match the deployed reality. §7.5 is the current runtime truth; §0 is the
2026-07-30 measurement it superseded in part.

### 10.1 Version bump — the four files that define it

| File | Change |
|---|---|
| `VERSION` | `8.0.1` → `8.1.0` |
| `backend/server.py` `APP_VERSION` | `8.0.1` → `8.1.0` (this is what deep health reports) |
| `deploy/aws/lightsail.env.example` | `STUDIOSAAS_VERSION=8.1.0` |
| `README.md` | `Current release: **v8.1.0**` |

Version assertions that had to move with it, all now green:
`backend/tests/test_health.py:14`, `backend/tests/test_tunnel_parity.py:14,25,44`,
`backend/tests/test_product_home_brand.py:57`,
`backend/tests/test_standalone_mode.py:113`.

The customer release-evidence pages were renamed with `git mv`, so history
follows:

```
customer-resources/Release_Notes_v8.0.1.html -> Release_Notes_v8.1.0.html
docs/customer/Release_Notes_v8.0.1.md        -> Release_Notes_v8.1.0.md
```

Seven referencing sites were updated: `product-home.html:393`,
`backend/server.py:991` (the served allow-list), `customer-resources/FAQ.html:127`,
`customer-resources/Privacy_Policy.html:190,191,200`,
`customer-resources/Terms_of_Service.html:44,45,153`,
`backend/frontend/assets/customer-resources.css:5`, `docs/customer/README.md:11`,
plus the three test files above and
`backend/tests/test_customer_resources_brand.py:7,60,225`.

§8.1 below still names the old filename. That is deliberate: it is a historical
statement about what the file was called at the time, not a live pointer.

### 10.2 The registration success card was invisible on seven themes

`tenant-template/index.html:270` (and the six generated tenant workspaces) read:

```css
.result-card{ background:var(--ink); color:#EFE9DD; }
```

`--ink` is the tenant theme's `text_color`. Under a light theme-mode that pairs
a fixed cream on a dark surface — 13.69:1, fine. Under the **seven dark
theme-modes `--ink` is itself the light text colour**, so the same fixed cream
sat on a near-identical surface at **1.06:1**. The 56px `✓` measured 1.21:1 and
the "back to home" control at `:543` had the same fault.

This is the confirmation a parent sees immediately after submitting a
registration — the single highest-consequence surface in the funnel, and it was
blank on nearly half the palettes a studio can choose.

Fix: `color:var(--bg)` against `background:var(--ink)`. That exact pair is the
`('body / page', 'text_color', 'background_color', 4.5)` row of `CHECKS` in
`docs/design/palette_gen.py:221`, so the generator already refuses to emit a
theme where it falls below 4.5:1 — the card can no longer fail silently for any
of the 15 theme-modes, including ones added later.

`tenant-template/index.html:263` — the degraded-content band was a fixed
`#FDF3D5` / `#6b4f00` pair, i.e. a light warm strip pinned across the top of
every dark theme. It now carries `brand-status` with `data-tone="warning"` and
takes the theme's own warning semantic (`brand-system.css:98`).
`:447` dropped a hard-coded `#9d9484` eyebrow for `var(--muted)`.

### 10.3 Every studio's CMS looked the same

Two independent causes, both in `legacy-root/index.html`:

1. `:62` mapped **10 of the 21 theme tokens**. `border_strong_color`, the accent
   hover/pressed states, `focus_ring_color`, the disabled pair and `scrim_color`
   were simply not applied, so a studio that picked one of the eight palettes
   got a CMS that was only partly theirs.
2. `:334` was `body { background:#f1f5f9 !important }` — Tailwind slate-100, a
   cold blue-grey that outranked any tenant theme by `!important`.

Both fixed. The map at `:62` is now the same declarative table the registration
page uses at `tenant-template/register.html:365`, covering all 21 fields, and
the body background is `var(--bg, #f1f5f9)` — the old value survives only as a
fallback until `/brand` answers.

### 10.4 Focus and control boundaries on the product gateway

| Surface | Before | After |
|---|---|---|
| `product-home.html:56` focus ring on light surfaces | Family Amber `#F5B335` on Warm Paper — **1.70:1** | accessible amber `--family-amber-text` — **4.52:1** |
| `product-home.html:62` focus ring on navy sections | — | Family Amber retained — **9.70:1** |
| `product-home.html:171` dark-section form border | `rgba(255,255,255,.28)` → composites to `#576173` — **2.51:1** | `.42` — **3.90:1** |

WCAG 1.4.11 asks 3:1 of a non-text indicator, so the old focus ring failed by a
wide margin on exactly the surface a keyboard user needs it.

### 10.5 What the new test file guards

`backend/tests/test_portal_theme_contract.py` — 12 tests, new:

- no colour declaration on a themed surface may name a literal hex, checked
  across `tenant-template/` and every generated workspace (scrim rules are the
  one documented exception);
- the success card must pair `--ink` with `--bg`, not with a chosen colour;
- **the generator still asserts that pair** — if someone deletes the
  `body / page` row from `palette_gen.py` `CHECKS`, the card's guarantee
  evaporates silently, so the test guards the assumption and not only the code;
- the degraded band must use the theme's warning semantic;
- `portal-theme.css` remains the single place fallback literals may live;
- each of portal, registration and CMS must map **every** theme field, and the
  three must agree field for field;
- the CMS base background must follow the tenant theme;
- the second CMS dark system is asserted to still be *recorded as open*, so the
  known gap cannot quietly fade out of the plan document.

### 10.6 Deliberately NOT done in this round

| Item | Where it is tracked |
|---|---|
| Uptime monitoring, backup-failure alerting, on-call ownership, contractual SLA | §0 "Not yet done"; disclosed on the FAQ and release-evidence pages |
| MFA for privileged accounts | §0; disclosed as an open gap **on a live service** |
| Off-instance copy of database and media backups | §0; backups exist and restore, but live on the same instance |
| Managed AWS services (RDS, S3, SES) | §0 |
| CMS's two dark systems not merged | `docs/design/UI_UX_Upgrade_Plan_2026-07-30.md` **item 29**, `legacy-root/index.html:151-238` |
| 128 `text-gray-400` occurrences below AA (2.31:1 at worst) | same document **item 8**, `legacy-root/src/cms-app.jsx` |
| 8 Tailwind semantic-colour steps not on the semantic scale | same document **item 7** |

Items 7, 8 and 29 are CMS-internal: they affect staff-facing screens, not the
parent- or student-facing surfaces fixed in §10.2.

Migration 0021 **is** applied to production — §9.2 describes it as pending, but
the v8.1.0 deploy in §7.5 carried it in. The instance reports 21 migrations and
`starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`.

## 0. AWS production is LIVE (2026-07-30)

`https://pwestudio.online` serves v8.0.1 from AWS Lightsail. **The Cloudflare
Tunnel is no longer the production path** and must not be reintroduced for this
hostname: the tunnel existed because the runtime had no public IP. With a static
Lightsail IP and Route 53 delegation, a tunnel would add a third-party hop, a
second credential to rotate, and would compete with certbot HTTP-01 for the
same hostname.

| Item | Truth |
|---|---|
| Instance | Lightsail `PWESTUDIO`, Ubuntu 24.04 x86_64, 2 vCPU / 1.9 GB / 58 GB, Sydney Zone A |
| Static IP | `13.237.190.58` |
| DNS | Route 53; `pwestudio.online` and `www.pwestudio.online` both A → the static IP |
| Edge | host nginx terminates TLS; app listens on `127.0.0.1:8899` only; 80 → 443; HSTS `max-age=31536000; includeSubDomains` |
| Certificate | Let's Encrypt, SAN = apex + www, lineage `pwestudio.online`, expires 2026-10-28, `certbot.timer` active |
| Runtime | Compose project `pwestudio`: `studiosaas:8.0.1` (commit `cdd204e`) + `postgres:16-alpine`, both healthy |
| Database | 6 tenants / 15 users / 65 students / 37 registrations / 81 media assets / 4276 audit rows; 20 migrations |
| Least privilege | migrations use the owner role inside entrypoint only; runtime uses `studiosaas_app` |
| Backups | `/etc/cron.d/pwestudio-backup` 03:15 UTC → logical dump + volume tarball; restore rehearsal passes |
| Release layout | `/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.0.1-cdd204e`, `current` symlink, env at `/opt/pwestudio/shared/production.env` (600) |
| Canonical host | `www` 301s to the apex over TLS; one origin, no duplicate content |
| Operator entry | `ssh pwestudio` (see §0.2) and `bash deploy/aws/pwestudio_remote.sh <cmd>` |
| Not yet done | RDS, S3, SES, MFA for privileged accounts, off-box backup copy, uptime monitoring |

**Superseded in part by §7.5.** The version, commit, migration count and release
path in this table are what was measured on 2026-07-30. The v8.1.0 deploy has
since landed: the instance runs `studiosaas:8.1.0`, commit `30da029`+, with 21
migrations applied and the revised plan quotas live. Everything else in this
table — instance, IP, DNS, edge, certificate, least privilege, backups,
canonical host, operator entry and the "not yet done" row — is unchanged and
still current. This section is left as the 2026-07-30 measurement rather than
rewritten, so the two deploys stay separately auditable; §7.5 is the current
runtime truth.

### 0.1 "Not Secure" in Chrome was a client-side cache, not a server fault

Measured from outside on 2026-07-30 after the edge went up:

```
http://pwestudio.online/   -> 301 -> https://pwestudio.online/   (1 redirect)
ssl_verify_result = 0      certificate chain = 4 certs, Verification: OK
homepage absolute http:// references = 0   (CSP is default-src 'self', so
                                            mixed content is structurally
                                            impossible, not merely absent)
```

Chrome had cached the HTTP 200 from before TLS existed and kept loading over
HTTP without re-following the new 301. Visiting `https://` once takes the HSTS
header, after which the browser refuses HTTP for a year. Nothing to fix
server-side. If it recurs on a device: hard-reload, or clear the site's data.

Optional permanent hardening not done: submitting the domain to the HSTS
preload list would make browsers refuse HTTP even before a first visit. It is a
one-way door — the domain must then always serve HTTPS — so it is a decision to
take deliberately, not a side effect of a deployment round.

### 0.2 Operating the instance

Access is an `ssh_config` alias; the key is **not** in the repository or in
iCloud. The private key was moved out of the synced project folder — iCloud
cannot hold mode 600, and a synced private key is a copy you do not control:

```
~/.ssh/pwestudio-lightsail.pem        mode 600   (byte-identical to the
                                                  Lightsail default key)
~/.ssh/config      Host pwestudio -> 13.237.190.58, user ubuntu
```

`deploy/aws/pwestudio_remote.sh` is the laptop-side half. It holds no
credentials and delegates everything that touches production data to
`lightsail_ctl.sh` on the instance, so a laptop is never the source of truth
for a production procedure:

```bash
bash deploy/aws/pwestudio_remote.sh status     # containers + deep health
bash deploy/aws/pwestudio_remote.sh health     # public HTTPS, DNS, cert, redirect
bash deploy/aws/pwestudio_remote.sh backups    # what is on disk, and the cron log
bash deploy/aws/pwestudio_remote.sh backup     # dump + volume tarball, now
bash deploy/aws/pwestudio_remote.sh drill      # rehearse a restore (safe)
bash deploy/aws/pwestudio_remote.sh certs      # expiry + renew timer
bash deploy/aws/pwestudio_remote.sh deploy dist/PWE-StudioSaaS-aws-<ver>.tar.gz
bash deploy/aws/pwestudio_remote.sh ssh
```

`deploy` refuses a `mode=standalone` tarball before uploading it, backs up
first, and **rolls the `current` symlink back automatically if deep health
fails**. Commands that remove a volume, drop a database, or perform a real
restore are deliberately absent — those live on the instance where the operator
reads the confirmation prompt in context.

### 0.3 Edge hardening (2026-07-30, second pass)

- **One shared TLS snippet** (`deploy/aws/nginx/pwestudio-tls.conf`, installed to
  `/etc/nginx/snippets/`) included by both 443 blocks. A hardened apex beside a
  default-configured `www` block is a downgrade path hiding in plain sight.
  TLS 1.2 is limited to forward-secret AEAD suites; no CBC, no RSA key exchange,
  no 3DES. Session cache on, tickets off.
- **OCSP stapling is deliberately OFF.** Every hardening guide says to enable it;
  it is now dead configuration for Let's Encrypt. The certificate's AIA carries
  only `CA Issuers - URI:http://ye1.i.lencr.org/` and no OCSP responder URL, so
  nginx accepts `ssl_stapling on` and then logs `"ssl_stapling" ignored` on
  every reload — a permanent warning that trains an operator to stop reading
  reload output, which is where real errors appear. Re-check after any renewal:
  `openssl s_client ... | openssl x509 -noout -ocsp_uri` should print nothing.
- **No duplicate security headers.** `backend/server.py:777-796` already sends a
  complete CSP, X-Frame-Options, Permissions-Policy, Referrer-Policy and
  X-Content-Type-Options. nginx was repeating two of them. HSTS stays at the
  edge on purpose: it must also cover responses the application never produced,
  and nginx's 502 while the container restarts is exactly when a downgrade must
  not be on offer.
- **Branded maintenance page** for 502/503/504 (`/var/www/pwestudio/__maintenance.html`,
  `internal`, no-store, `Retry-After: 30`). An upgrade restarts the container for
  a few seconds; nginx's stock "502 Bad Gateway" reads like the studio's website
  is broken rather than briefly updating.
- **nginx 1.24 constraint**: HTTP/2 is a `listen` parameter on Ubuntu 24.04. The
  1.25+ `http2 on;` directive fails `nginx -t` — caught by the config test
  before reload, so the live site was never affected.

Nine contract tests in `backend/tests/test_lightsail_deployment.py` hold all of
the above, including that the operator script carries no credentials and cannot
destroy anything.

### Four defects this deployment round found and fixed

All four looked fine from the outside and would have surfaced only during an
incident:

1. **Daily backups had never once succeeded.** `lightsail_ctl.sh` invoked
   `scripts/backup_postgres.py`, but the script is at `backend/scripts/` inside
   the image (WORKDIR `/app`). Nothing read the cron output.
2. **Even with the right path, the dump could not be written.** The bind-mounted
   backup directory was `ubuntu:ubuntu 0755` while the container runs as uid
   10001 → `Permission denied`. Now owner uid 10001, group the operator, mode
   2750, asserted on every run so a human can also list backups without sudo.
3. **The restore rehearsal could never pass.** The image installed an unpinned
   `postgresql-client`, resolving to 17, against a PostgreSQL 16 server; a 17
   `pg_restore` emits `SET transaction_timeout = 0`, a PG17-only GUC, which
   PG16 rejects. The client is now pinned to `postgresql-client-16` from PGDG.
   Dumps produced by the 17 client were deleted — a 16 client cannot read them,
   so keeping them would hand an operator an unusable backup mid-incident.
4. **The media volume was empty.** The database referenced 81 media assets and
   160 derivatives; the volume held only Linux's stock `/media/{cdrom,floppy,usb}`
   from the image layer. Every brand logo returned 404. The 2032-file media tree
   was extracted with uid 10001 ownership, and `backfill_media_variants.py` was
   fixed to verify that a derivative's **file** exists rather than only its row
   — it previously reported "Generated variants: 0" while 126 files were missing.

## 1. Historical delivery boundary (pre-2026-07-30)

v8.0.1 was first shipped as a verified local release and customer-demonstration
package, before the AWS deployment above.

| Area | Truth at the time |
|---|---|
| SaaS runtime | Local Waitress + PostgreSQL behind the controlled `studiosaas-v8-controlled` Cloudflare Tunnel |
| Public product URL | `https://studiosaas.cc.cd` reported v8.0.1 from the same runtime as `http://127.0.0.1:8901` |
| Role entry contract | `/platform-admin` = platform control plane; `/studio-admin` = neutral tenant-admin login; `/cms` = neutral tenant-operations login |
| AWS/RDS/S3/SES | Not purchased or deployed *(Lightsail now deployed; RDS/S3/SES still not)* |
| Production backups/restore/monitoring/SLA | Deferred *(backups + restore rehearsal now live; monitoring/SLA still deferred)* |
| Online payment, provider SMS/email, custom domains | Deferred |
| Multi-campus | One campus = one tenant/subscription; future organisation aggregation is deferred |

Do not describe local testing, a source bundle or Cloudflare invitation access
as production acceptance. Production acceptance is `https://pwestudio.online`
answering deep health with `appVersion=8.0.1`, `mode=saas`, `db=ok` — see §0.

## 2. What v8.0.1 delivers

### P0 — customer-safe demonstration and commercial readiness

- SaaS `/` is a bilingual product gateway with a clear product story, five
  role entrances, sales journey, plans, migration downloads and support CTA.
- v8.0.1 brings that gateway onto the canonical PWE family palette: Family
  Navy `#0E1729`, Family Amber `#F5B335`, accessible amber text `#A16207` and
  Warm Paper `#F7F5F2`. Retired forest, sage and coral values are rejected by
  a dedicated regression test.
- The gateway now follows the approved sales story—administration behind the
  scenes, creativity in front—uses Let’s Paint Studio as the demonstration
  proof, identifies Studio at AUD 99/month as the recommended plan and
  discloses the AUD 299–999 setup range.
- `lets-paint-showcase` is the only professional demonstration tenant. It uses
  fictional people/contact records and synthetic artwork.
- `RESET_DEMO_TENANT.command` and
  `backend/scripts/reset_professional_demo.py`:
  - refuse standalone mode;
  - require the exact phrase `RESET-LETS-PAINT-SHOWCASE`;
  - can only touch the permanently marked `lets-paint-showcase` tenant;
  - keep four staff roles on the configured stable local/Pilot password and
    rotate the separate student code on every reset;
  - write credentials to `.runtime/credentials/showcase-credentials.txt` as
    mode `0600`, never to stdout.
- `docs/customer/` contains a customer-readable delivery index, pricing and
  package boundaries, service agreement draft, onboarding checklist, FAQ,
  migration guide, support policy, integration boundary, multi-campus policy,
  security/privacy/compliance disclosure, demonstration runbook and release
  evidence.
- Security/compliance material explicitly discloses the pre-production state,
  privileged MFA gap, backup gate and incident-response boundary.

### P1 — connected operating experience

- Studio Admin remains the website/brand workspace and CMS remains daily
  operations; both now provide stable reciprocal navigation.
- Onboarding is documented from commercial discovery through tenant creation,
  brand publishing, operational rehearsal, migration and acceptance.
- Reviewed CSV and five-sheet XLSX templates define the supported migration
  shape. Arbitrary historic spreadsheets require assessment and may require
  separately quoted clean-up.
- Family private access shows balance, next class, attendance and portfolio,
  then opens tenant-addressed device Messages/Mail actions for schedule or
  absence enquiries.
- Active recurring schedules download as a tenant-timezone ICS file with stable
  UIDs and weekly recurrence. The export contains no roster/student data.
- Teacher mobile mode prioritises three steps: today's roster, student lookup
  and artwork upload. Non-financial roles see attendance KPIs, not revenue
  labels with zeroed values.
- Product-home Support & Feedback opens the device Mail/Messages application;
  there is no claim of automated delivery, delivery log or retry.

### P2 — sales story and deliberate extension points

- The demonstration runbook follows Let’s Paint Studio from enquiry → trial →
  enrolment → recurring schedule → attendance/credit → artwork → family view →
  owner report.
- Eight industry presets now include three bilingual starter courses,
  registration focus, report focus and a demonstration story in addition to
  industry terminology and visual themes.
- v8.0.1 supports CSV/XLSX export/import templates, ICS and device-native
  messaging. Stripe, Xero, Google/Outlook APIs, provider SMS/email and webhooks
  remain explicit extension points.
- Organisation-level multi-campus aggregation is not modelled prematurely;
  campus tenants remain isolated for permissions, billing and operations.

## 3. Demonstration data evidence

The guarded reset was run twice successfully.

| Tenant | Students | Courses | Packages | Schedules | Memberships | Credit balance |
|---|---:|---:|---:|---:|---:|---:|
| `lets-paint-showcase` | 12 | 3 | 3 | 3 | 4 | 78 |
| `lets-paint-studio` | 43 | 3 | 5 | 0 | 1 | 165 |

`lets-paint-studio` retained its pre-reset counts and balance. The showcase
also contains five enquiry states, three private portfolio works and six
metadata-sanitised display/thumbnail variants.

## 4. Verification evidence

### Repository and database gates

- `backend/tests`: **182 passed, 2 skipped**.
- Legacy CMS smoke: **73 passed, 0 failed**.
- PostgreSQL tenant isolation/privacy/Edition suite: **216 passed, 0 failed**.
- Migration check: current.
- Media derivative check: current.
- Python compile, inline scripts, shared JS, CMS source/build consistency, UI
  escaping, terminology and release/Edition shell syntax: passed.
- `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`: passed.

### Browser acceptance

Real Chrome, no page errors and no HTTP 5xx:

| Surface | Viewport | Result |
|---|---:|---|
| Product home | 375×812 | no overflow; 44px actions; skip link; language switch; reduced motion; 125% text |
| Product home | 812×375 | no overflow |
| Product home | 768×1024 | no overflow |
| Product home | 1024×768 | no overflow |
| Product home | 1440×900 | no overflow |
| Studio Admin | 1024×900 | 8 industry cards + 8 operational starter-course summaries |
| Owner CMS | 768×1024 | no overflow; authenticated ICS download |
| Teacher CMS | 375×812 | three-step flow; no financial label; no schedule mutation |
| Family private area | 375×812 | balance 8, four attendance rows, one private work, native contact actions |

The post-release tunnel correction was also accepted in the in-app browser
against the public hostname. `/platform-admin` remained on the direct
application login, `/studio-admin` required an explicit slug without browser
storage fallback, `/cms` exposed an explicit tenant selector, and
`/lets-paint-showcase/studio-admin` locked the correct slug. The showcase CMS
rendered the Let's Paint Studio login and no tested page had horizontal
overflow.

Product-home display images are 760×760 WebP with intrinsic dimensions and
total **229,582 bytes** in the browser. Five role entrances render at every
tested viewport; local page load during the acceptance run was approximately
0.56 seconds.

The v8.0.1 product-home pass also verified the computed Navy hero, Warm Paper
canvas, accessible amber text, bilingual sales copy, every visible 44px target,
125% text and reduced-motion behavior. Measured contrast includes 17.90:1 for
white on Navy and 4.52:1 for amber text on Warm Paper.

The ICS response contains three recurring events, `TZID=Australia/Melbourne`,
stable weekly recurrence and no tested student name, mobile or family email.

### Migration artifacts

- `customer-resources/PWE_Studio_Data_Import_Template.csv`
- `customer-resources/PWE_Studio_Data_Import_Template.xlsx`

The XLSX contains Instructions, Students, Courses, Packages and Field Guide
sheets. All five sheets were rendered and visually inspected; ZIP integrity
and spreadsheet error-token scans passed.

## 5. Cloudflare operating truth (LOCAL DEVELOPMENT ONLY as of 2026-07-30)

> **The tunnel is no longer the production path.** `https://pwestudio.online`
> serves production from Lightsail with nginx terminating TLS (§0). Everything
> below now describes the *local* runtime and the `studiosaas.cc.cd` demo
> hostname only. Do not point production DNS at a tunnel, and do not treat
> tunnel parity as production acceptance.
>
> Why no tunnel in production: the tunnel existed because the runtime lived on a
> home Mac with no public IP. A Lightsail static IP plus Route 53 removes that
> constraint, so a tunnel would add a third-party hop and a second credential to
> rotate in front of production, for nothing.


`START_STUDIOSAAS_ONLINE.command` now:

- pins `STUDIOSAAS_MODE=saas`;
- defaults the application runtime to port `8901`;
- reads the expected application version from `VERSION`;
- supports an explicit public base domain;
- resolves environment, logs, CMS data, PID files and Tunnel credentials from
  the project-local, Git-ignored `.runtime/` directory;
- never reads `~/.studiosaas`, `~/.cloudflared` or `/private/tmp` for runtime
  files and never resets application passwords during startup;
- uses the explicit project-local Tunnel credential JSON and configured Tunnel
  name instead of selecting an arbitrary credential;
- waits for local and public health;
- runs `backend/scripts/verify_tunnel_parity.py` against deep health;
- refuses to call the tunnel accepted when version, mode, database or release
  identity differs.

Current observation on 2026-07-29:

- local and public deep health agree on
  `appVersion=8.0.1`, `mode=saas`, `db=ok`;
- DNS for `studiosaas.cc.cd` points to the controlled
  `studiosaas-v8-controlled` tunnel, whose ingress targets
  `http://localhost:8901`;
- the public platform-admin API returned all six local tenants;
- `lets-paint-showcase` owner authentication, tenant API and brand workspace
  all returned the exact showcase tenant;
- `/super-admin` remains a Cloudflare Access-protected compatibility alias;
  `/platform-admin` is the direct application-login route;
- the old tunnel was left intact but is no longer the hostname route, preserving
  rollback without allowing two runtimes to answer the same hostname.
- moving a runtime-complete copy to a path containing spaces and starting from
  that new location passed local health, public health and release parity; the
  15-user password-hash fingerprint was unchanged across restart.

The previous split-brain state is therefore resolved. Do not change the DNS
route back to the historical tunnel or start a second connector with a
different ingress for this hostname.

## 6. Packages and release closure

The clean-commit package gate passed for both delivery modes:

```bash
bash deploy/aws/verify_release_bundles.sh
```

Verified outputs:

- `dist/PWE-StudioSaaS-aws-8.0.1.tar.gz`
- `dist/PWE-Studio-Edition-8.0.1.tar.gz`
- matching `.sha256` sidecars.

The SaaS package includes the product gateway, customer resources,
professional showcase workspace/assets and guarded reset. The Edition package
excludes the showcase workspace and reset command while retaining the shared
runtime and customer/operator documentation. Both archives passed SHA-256,
entrypoint, forbidden-content and `BUILD_INFO` checks. The `.sha256` sidecars
generated from the final tagged commit are the authoritative hashes.

## 7. Operator commands

Production commands are in §0.2. The list below is the **local development**
set; running the tunnel parity check against production is meaningless because
production does not use a tunnel.

```bash
# Local service
bash START_STUDIOSAAS_LOCAL.command

# Guarded professional showcase reset
./RESET_DEMO_TENANT.command

# PostgreSQL-required release gate
STUDIOSAAS_REQUIRE_POSTGRES=1 \
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
bash backend/scripts/verify_local.sh

# Tunnel split-brain/version parity
.venv/bin/python backend/scripts/verify_tunnel_parity.py \
  --local-base-url http://localhost:8901 \
  --public-base-url https://studiosaas.cc.cd \
  --expected-app-version 8.1.0 \
  --expected-mode saas

# Clean-commit SaaS + Edition bundles
bash deploy/aws/verify_release_bundles.sh
```

Presenter credentials are intentionally excluded from Git, bundles, docs and
this handoff. Read the protected local file only when presenting.

## 7.5 v8.1.0 deployed — and the two defects the deploy itself exposed

`https://pwestudio.online` runs **v8.1.0**, image `studiosaas:8.1.0`,
commit `30da029`+, 21 migrations applied, plan quotas live at
`starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`.

Neither defect below was caught by a test. Both were caught by reading the
deploy output and probing the live edge afterwards, which is the argument for
doing that every time rather than trusting a green suite.

### The image tag named the wrong version

`docker-compose.yml` tags `studiosaas:${STUDIOSAAS_VERSION}`, and that variable
lives in `/opt/pwestudio/shared/production.env` — the file that deliberately
survives a release because it holds the secrets. Nothing updated it. Deploying
8.1.0 therefore built:

```
studiosaas:8.0.1     <- the tag
appVersion 8.1.0     <- what is actually inside it
```

Two consequences, both only felt during an incident: `docker images` lies to
whoever is diagnosing, and the tag stops being a rollback point because every
release overwrites the same one.

`pwestudio_remote.sh deploy` now reads the version out of the **bundle's own
BUILD_INFO** — not the laptop's `VERSION` file, which can already be ahead of
what is being deployed — and pins it before the rebuild.

### Renaming the release notes killed its public URL

`/customer-resources/Release_Notes_v8.0.1.html` returned 404 the moment the
file became `v8.1.0`. That URL is in sent mail, in the sales deck footer, and
in whatever a prospect bookmarked.

Any superseded versioned name now 301s to the current one. The pattern is
version-shaped (`Release_Notes_v\d+\.\d+\.\d+\.html`), so the next release
does not need this touched, and the traversal guard still runs first — the
redirect can only ever land on the allow-listed current file.

Verified live:

```
/customer-resources/Release_Notes_v8.0.1.html
  -> 301 https://pwestudio.online/customer-resources/Release_Notes_v8.1.0.html
```

### What v8.1.0 fixed in the product

The release's own reason for existing: **a studio's brand choice did not reach
every surface it was supposed to reach.**

- The CMS mapped 10 of 21 theme fields and forced its own background with
  `!important`. Every studio's CMS looked identical regardless of which of the
  eight palettes they chose. Portal, register and CMS now map the same 21
  fields, and a test asserts the three are equal **field for field** rather
  than each merely complete — so adding a token later fails on the first
  surface to adopt it, which is when drift begins.
- The registration success card paired a fixed `#EFE9DD` against
  `background:var(--ink)`. `--ink` is the tenant's `text_color`, so under the
  seven dark theme-modes it is LIGHT and that text measured **1.06:1** — the
  card a family sees after submitting an enrolment was invisible. It now pairs
  `--ink` with `--bg`, which `palette_gen.py:221` already asserts at 4.5:1 for
  all 15 theme-modes, and a second test guards that assertion itself.
- Focus ring was Family Amber at **1.70:1** on Warm Paper, under the 3:1 that
  WCAG 1.4.11 requires. Swapped to the accessible amber (4.52:1); the five
  navy-backed surfaces keep the bright amber at 9.70:1.

### Still open, deliberately

The CMS carries a second dark system in its `prefers-color-scheme` block that
still uses `!important`. Merging the two is item #29 of
`docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`. A partial merge would leave
Tailwind surfaces dark while the page background followed a light tenant theme
— worse than either system alone. `test_portal_theme_contract.py` records the
gap so it cannot fade into the file, and fails when someone finishes it.

Also open from the same plan: items #7 and #8, the ~128 `text-gray-400` uses in
the CMS that measure 2.31–2.54:1. Monitoring, an SLA, privileged-account MFA
and off-box media backup remain absent and remain disclosed as absent.

---

## 7.6 Roster slots, and the CMS colour audit (2026-07-30, after the v8.1.0 deploy)

### Roster slots — migration 0022

The roster answered "who is coming today" but not "when". A studio running a
13:30 group and a 17:00 one-to-one saw one flat list, so the front desk could
not tell whether a student was due now or in four hours, and a one-to-one booked
into an occupied hour surfaced when both families arrived.

`daily_roster_entries` gains `class_time time` (NULLABLE) and
`one_to_one boolean`.

**`class_time` is nullable on purpose.** Every existing row predates the column
and there is no honest value to backfill; inventing 09:00 for 43 imported
students would look like data rather than the absence of it. The UI groups those
rows under 「时间未设置」 and sorts them last, keeping the gap visible.

**`time`, not `timestamptz`.** This is a wall-clock slot in the studio's own
timezone ("the 17:00 class"), not an instant. An instant moves when the offset
changes, which is exactly wrong for a recurring lesson.

Two semantics worth knowing:

- `POST /daily-roster` COALESCEs the slot, so re-adding a student without naming
  a time cannot erase one already set.
- `PATCH /daily-roster/<id>` is the correction path. Moving a student from 10:00
  to 17:00 must not reset their source and status the way re-adding would.

Nine isolation checks cover the round trip, the COALESCE, cross-tenant refusal,
and that `25:00` / `10:75` / `noon` / `10` are rejected while `""` remains a
legitimate way to say the slot is not decided.

The CMS shows a slot panel grouping the day by time, and flags what the flat
list hid: **a one-to-one sharing its slot with anyone else.** Rows carry an
inline time control, so a correction sits next to where the problem is visible.

### The CMS colour audit

`legacy-root/index.html` re-points Tailwind utility colours at the tenant theme.
It covered indigo and purple, shades 50/100/600/700 — correct for the shades
that existed when it was written, and silently rotten as the app grew.

Measured: **cms-app.jsx carries 1,322 colour utilities across 149
family+shade combinations in 12 families.** Two families were covered.

So a studio on the clay palette saw a green 「网站与品牌」 button, a blue
「长期未到访」 panel, green row actions, pink birthday chips, a purple-to-pink
report gradient and a stock-blue language switch. The CMS read as four products
stacked together — and the previous release, which themed the content area, made
it *more* conspicuous rather than less.

All 149 combinations now resolve to the theme, **mapped by role rather than by
hue**:

| Tailwind | Role | Resolves to |
|---|---|---|
| gray / slate / zinc / neutral / stone | structure | `--bg2`, `--line`, `--muted`, `--ink2`, `--ink` by shade band |
| green / emerald / teal / lime | success | `--success` |
| amber / yellow / orange | warning | `--warning` |
| red / rose | danger | `--danger` |
| blue / sky / cyan / pink / fuchsia | informational | `--accent-dark` |
| indigo / violet / purple | primary | `--accent` |

Role, not hue, because the role is what survives a palette change; and because
`palette_gen.py` already solves `--success` / `--warning` / `--danger` against
both page and panel for every theme-mode, routing through them inherits that
contrast instead of re-deriving it by eye. Soft fills use `color-mix` against
`--panel`, so they stay light under a light theme and dark under a dark one
rather than becoming a pale slab on a dark page.

Dark chrome (sidebar, mobile bar, login backdrop) maps to `--ink` with `--bg` as
the foreground — the inversion `palette_gen.py:221` guarantees at 4.5:1 — because
a fixed `text-white` is only readable while the surface stays dark.

`--brand` is now defined as `--accent`: the shared admin language switch reads
it, and with it undefined the switch fell back to stock blue `#3b82f6`.

**The test derives the required list from cms-app.jsx** rather than restating
it, so a newly-used shade fails the build at the moment it is introduced. That
matters more than this audit: the old rules were right when written and rotted
without a single failure.

### Also fixed

`backend/frontend/cms-entry.html` focus ring was `rgba(245,179,53,.55)`, which
composites to **1.40:1** on white — the translucency made it worse than the
solid amber, itself already too light for an indicator that WCAG 1.4.11 requires
at 3:1. Now the accessible amber at 4.92:1.

### Open

- The ICS export is **spec-invalid**: `DTSTART;TZID=Australia/Melbourne` with no
  `VTIMEZONE` component (`grep -c VTIMEZONE` = 0). RFC 5545 §3.6.5 requires the
  referenced timezone to be defined in the same calendar object; `X-WR-TIMEZONE`
  is an Apple extension and does not substitute. Apple leans on local time,
  Google is inconsistent, Outlook may refuse the import — so a class lands at
  the wrong moment in a family's calendar, silently, and `RRULE:FREQ=WEEKLY`
  repeats it weekly. Being fixed in a separate stream together with the download
  dialog and the preview API shape.
- Still not done from `docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`: per-day
  counts on the week strip, the inline status menu, the day's roster change log,
  item #29 (merging the two CMS dark systems), items #7/#8 (CMS-internal
  readability).

---

## 7.7 Calendar export: spec-invalid, and downloading as JSON

Two separate defects. Both are fixed; the second is the one the studio actually
hit.

### The file was spec-invalid

`DTSTART;TZID=Australia/Melbourne:...` with **no `VTIMEZONE` component** —
`grep -c VTIMEZONE` returned 0. RFC 5545 §3.6.5 requires the referenced timezone
to be defined in the same calendar object; `X-WR-TIMEZONE` is an Apple extension
and does not substitute. Apple leans on local time, Google is inconsistent,
Outlook may refuse the import — so a class lands at the wrong moment in a
family's calendar, silently, and `RRULE:FREQ=WEEKLY` repeats that weekly.

`VTIMEZONE` is now derived from `zoneinfo`, not hard-coded, so a tenant in
Shanghai or London gets its own rules and abbreviations. Verified by parsing the
output back:

```
8月  DTSTART;TZID=Australia/Melbourne:20260805T160000  AEST +10:00 -> 06:00Z
11月 DTSTART;TZID=Australia/Melbourne:20261104T160000  AEDT +11:00 -> 05:00Z
```

The same "Wednesday 16:00" resolving to different UTC instants either side of
the transition is the proof the TZID is now honoured. Line folding was checked
at 75 **octets** against Chinese course names (3 bytes per character): 0 lines
over.

### The download was JSON

The control was `<a href="…calendar.ics" download>`. A plain navigation carries
no `X-Requested-With` header and is not a fetch, so the authenticated endpoint
answered **401 with a JSON body — and the browser saved that JSON as the
calendar file.** That is the garbled download the studio reported; it had
nothing to do with the ICS format.

Downloading from an authenticated endpoint requires a credentialed fetch and a
blob. The client now also refuses to hand the visitor a `.ics` whose
`Content-Type` is not a calendar, so this exact failure cannot recur silently.

### The dialog

Preview then download, both rendered from the **same `CalendarDocument`** the
`.ics` is serialized from, so the counts on screen cannot disagree with the file
that arrives. Shows event/class/one-to-one counts, each event with duration and
time range, the timezone with its abbreviations read from `zoneinfo`, anything
skipped and why, and Apple/Google import guidance.

Two honesty details: the dialog warns when a file **contains student names**
(it leaves the system and lives in someone's calendar), and it only claims the
file is a snapshot when `subscribable` is actually false.

Four endpoints: preview + `.ics` for the recurring schedule (no student data,
subscribable) and for a dated roster (student names, snapshot).

### The empty calendar and the wrong filename (2026-07-31)

The studio downloaded `~/Downloads/weekly-classes.ics`: 639 bytes, a valid
`VCALENDAR` with a correct `VTIMEZONE` — and **zero `VEVENT`s**. The dialog was
equally blank. Two independent causes, neither of them the ICS format:

1. **Every roster row predates migration 0022's `class_time` column.** The
   roster builder refused to invent a slot (correct — see the migration's own
   reasoning) and *skipped* those rows, so a studio that had not yet set any
   slot exported nothing. They are now exported as **all-day events**
   (`DTSTART;VALUE=DATE` / `DTEND;VALUE=DATE` on the next day, per RFC 5545),
   which asserts "expected today" and nothing about when. `skipped` is now only
   cancellations, reported by name. `test_roster_with_no_slots_set_still_
   exports_every_student` pins the whole path.
2. **The recurring-schedule export was genuinely empty** — Let's Paint Studio
   keeps no `class_schedules` rows, it works from the daily roster. That file
   was truthful; the *dialog* was the defect, saying nothing and still offering
   a download. The download button is now disabled at zero events and the empty
   state names the next action ("在「每周课表」新增班次后，这里就会有内容").

The filename was wrong because the client invented one. The server has always
put the correct name on the `CalendarDocument` (`<slug>-roster-<date>.ics`,
`<slug>-weekly-classes.ics`) and exposes it as `preview.filename`; `downloadIcs`
now uses that, falling back to `Content-Disposition` and only then to a literal.
A roster export saved as `weekly-classes.ics` was the visible symptom.

Skip reasons were also being rendered as raw machine codes (`no-class-time`);
they are now mapped to studio-facing Chinese with the student's name.

### CMS readability pass — the colour map was right, the contrast was not (2026-07-31, v8.1.1)

§7.6 mapped all 1,322 Tailwind colour utilities onto theme tokens by role. That
answered *which token does this colour come from*. It did not answer *can you
still read the text once both ends follow the theme* — a value can be perfectly
on-brand and invisible. Replaying every (text token x background token) pair the
CMS can produce against the 15 theme-modes in `backend/studiosaas/presets.py`
gave **197 failures in 645 pairs**. After this pass: **0 in 660**.

Every number below is the worst case across all 15 theme-modes, computed with
the same WCAG relative-luminance formula as `docs/design/palette_gen.py::ratio`,
and spot-checked against `getComputedStyle` in a real browser on both
`atelier-clay/light` and `arcade-lime/dark` (the model and the browser agree to
within 0.05).

| what | before | after | worst theme-mode |
|---|---:|---:|---|
| body text on a card (`bg-white` + `text-gray-900`) | **1.02** | **13.25** | arcade-lime/dark |
| soft text on a card | 1.40 | 9.67 | arcade-lime/dark |
| muted text on a card | 2.44 | 5.56 | arcade-lime/dark |
| white label on an accent fill | 2.08 | 5.83 | studio-ink/dark |
| label on a disabled primary button | 1.25 | 3.00 | rehearsal-rose/light |
| semantic text on its own soft fill | 3.15 | 5.57 | arcade-lime/dark |
| semantic text on `--bg2` | 2.86 | 5.00 | arcade-lime/dark |
| semantic text on `--panel` | 3.72 | 6.39 | arcade-lime/dark |
| `--muted` on the `bg-gray-200` chip | 4.17 | 4.56 | studio-ink/dark |
| the faintest text tier (`text-gray-300`) | 3.03 | 5.56 | all 15 |
| secondary accent text on `--bg2` | 4.44 | 4.72 | arcade-lime/dark |
| selected profile tab | 1.00 | 5.17 | atelier-clay/light |
| `--ink` on the page under OS dark + a light tenant theme | 1.16 | 14.57 | atelier-clay/light |

Four root causes, three of which are the same bug wearing different clothes —
`[class*="bg-red-50"]` is a substring test, so it also matches `bg-red-500` and
`active:bg-red-50`:

1. **`bg-white` (99 uses) and `text-white` (73) were never re-pointed.** They are
   not `<family>-<shade>` utilities, so the audit regex that produced the §7.6
   map never saw them. Under the eight dark theme-modes a card stayed `#ffffff`
   while its text became `--ink` — near-white on white, **1.02:1**. `bg-white`
   now resolves to `var(--panel)`; `bg-white/NN` is deliberately excluded because
   those sit on a `bg-black` scrim over a photograph.
2. **The `-500` solids were being caught by the `-50` soft fills.** The refund
   button, the low-balance badge and the portfolio delete button rendered as a
   12% tint under a white label. The 500s are now restated after the soft fills
   and each is paired with the on-colour the generator asserts.
3. **A `disabled:` / `active:` / `after:` prefix is invisible to `[class*=]`.**
   `disabled:bg-gray-300` sits on seven primary buttons (create class, join
   today's roster, save, top up) — they wore the disabled chip *at rest* under a
   white label, **1.25:1**. The disabled fill now binds to the real `:disabled`
   pseudo-class with the `--disabled-surface` / `--disabled-text` pair (3.00:1 —
   legible, deliberately under AA so it still *reads* as unavailable, which is
   also why it no longer needs the blanket opacity). A single guard keyed on the
   `:` that only a variant prefix can contain now stands down for `:hover` /
   `:active` / `:disabled` and nowhere else. Only those three prefixes are used
   with `bg-` in the whole file (126 `active:`, 7 `disabled:`, 4 `hover:`), so
   the guard cannot catch a responsive variant.
4. **Two dark systems were both in charge.** The `@media (prefers-color-scheme:
   dark)` block predates the role map and the role map outranks almost all of it
   by source order. *Almost*: `html`/`body`, the row hover and the input
   placeholder had no later counterpart, so under OS dark + a **light** tenant
   theme those three stayed dark while everything else followed the light theme.
   Rather than merge the two systems (plan item #29, still open), the outcome is
   scoped: once `/brand` answers, `data-brand-scheme` is on `<html>` and the
   tenant theme owns those three. Before it answers the OS block still prevents a
   white flash, which is the case it was written for.

**Semantic text now mixes toward an anchor rather than being used raw.**
`palette_gen.py:174` solves `--success`/`--warning`/`--danger` against the
**page** only, and `CHECKS` (`:231-233`) only asserts that. The CMS also puts
that text on `--panel`, on `--bg2` and on the role's own soft fill. The fix is
one ratio that works in both modes: `color-mix(in srgb, var(--ROLE) 61.8%,
var(--text-anchor))`, where `--text-anchor` is `--ink` on content surfaces and
flips to `--bg` inside the inverted chrome (sidebar, mobile top bar, bottom nav)
— declared as an inherited custom property, so a semantic colour dropped into the
sidebar later cannot darken itself into the surface. Measured in-browser on the
`#211B19` chrome: warning 6.16, success 6.06, muted 8.49. **68% is the exact AA
boundary; 61.8% is the golden section and buys 0.5 of margin for six points of
chroma.** The brand accents get the same treatment at a far lighter dose (94%),
enough to clear the single remaining miss without a perceptible hue change.

**The faintest text tier was deleted, not adjusted.** `text-gray-300` was
`color-mix(--muted 70%, --panel)` and measured 3.03:1 on `--panel` in *all 15*
theme-modes — necessarily, because `--muted` is already solved to sit on the AA
floor, so anything fainter is by construction below it. It now collapses into
`--muted`; hierarchy at that level has to come from size and weight.

#### Student profile: five tabs, three actions outside them

Grouped by *the question being answered*, not by field type: **概览** (who do I
call, when were they last here — what the front desk needs in five seconds),
**资料** (is the record correct), **记录** (what happened), **作品集** (what have
they made, and may we publish it), **专区** (can the parent log in — a different
audience). The publication-consent panel lives with the portfolio because consent
only ever means "may this piece go public"; splitting the two is what made the
old single column a wall of unrelated panels.

Three actions stay **outside** the tabs, in a sticky bar below the scroll:
加入今日排课 (performed many times a day), 快速充值 (what you reach for the moment
the balance badge reads low) and 编辑 (a mode switch that has to work from
whichever tab you are on). They used to be the *last* thing in the scroll, below
a portfolio grid and a consent panel. 归档学员 moved to the end of 资料 — a
lifecycle decision taken a few times a year that was sitting one thumb-width
below 生成成长报告. 生成成长报告 moved into 作品集, because it is assembled from
the portfolio.

The tabs implement the full WAI-ARIA tab pattern, not just `role="tab"`: roving
tabindex (exactly one tab stop), Left/Right with wrap, Home/End,
`aria-controls`/`aria-labelledby` both ways, `role="tabpanel"`. Verified by
driving the keyboard in a real browser. Same contract as
`backend/frontend/studio-admin.html`, so the two admin surfaces behave
identically. Targets are 44px and the strip scrolls rather than wrapping — a
wrapped tablist puts two rows of targets under a thumb aiming for one.

The selected-tab indicator is a real child element. Written as
`after:bg-indigo-600` it read to the override layer as `bg-indigo-600` and filled
the **button** with the accent under accent-coloured text: **1.00:1**. This was
caught in the browser, not in the model — the model does not know about variant
prefixes. It is the reason cause 3 above got a general guard rather than a
one-line patch.

#### Golden ratio, concretely

Every number comes from the φ ladder already in `assets/ui-tokens.css`
(5 · 8 · 13 · 21 · 34 · 55 · 89, each step ≈1.618x the last), so the sheet is
measured against the same scale as the dashboard:

- profile sheet width **34rem** (544px), height cap **89dvh**
- panel padding **21px** (`--ui-space-4`), row gap **13px**, action gap **8px**
- action bar columns **1.618fr : 1fr** — the primary action takes the golden
  major share, the secondary the minor; a lone action spans both rather than
  leaving a 38.2% hole
- semantic text mix **61.8% / 38.2%** role-to-anchor (AA boundary is 68%)
- row-hover fill **38.2%** of `--line` into `--panel`
- language switch inset **21px**, label **13px**

#### The two named controls

**中英切换 (bottom-right).** The control named in the brief was
`admin-i18n.js`, which reads `--brand`; the switch the CMS actually shows is
`cms-i18n.js`, and it was **fully hardcoded** — `#fff`, `#e2e8f0`, `#64748b`,
`#4f46e5`. Both are fixed. Every colour is now a token with the pre-theme palette
as fallback: surface `--panel`, hairline `--line` (1.34:1, floor 1.18), resting
label `--muted` on `--panel` **5.56:1** (the hardcoded `#64748b` measured
**3.06:1** once the panel followed a theme), selected label `--on-accent` on
`--accent` **5.83:1** (a fixed `#fff` on a bright dark-theme accent measured
2.08:1). The focus ring moved from `--brand`/`--accent` to **`--focus-ring`** —
`--accent` is solved as a *text* colour against the page, `--focus-ring` is the
one solved to clear 3:1 against every surface it can land on: measured 4.13 on
`--panel`, 3.60 on `--bg`, 3.22 on `--bg2`. Positionally it was sitting **on top
of the mobile bottom nav**; it now docks above it at the same 88px offset
`.toast-bottom` already uses, so the two agree about where the bottom of the page
is. Toasts still cover it briefly (z-index 999 vs 90), which is the correct order.

**左侧「网站与品牌」.** It was `bg-emerald-50/700`. Green was picked when the CMS
had no palette; once every colour maps by role it made an **outbound navigation
link read as a success state**. It and 公开网站 are a *pair of links out of the
CMS*, so the difference between them has to be hierarchy, not hue: editing the
brand is the accented action (`--tenant-primary` + `--on-accent`), viewing the
live site is the quiet read-only peer and keeps the chrome inset that 刷新 / 设置
already use. That contrast survives a palette change; green-vs-blue did not. The
same judgement is applied to the mobile settings sheet, where the list already
reads *filled = do it, soft accent = secondary, neutral = read-only, danger =
destructive* — 网站与品牌 takes the single filled slot.

#### Still open after this pass

- **Plan item #29 — merge the two CMS dark systems.** Scoped, not solved. The
  `@media (prefers-color-scheme: dark)` block still carries ~60 hardcoded hexes
  for Tailwind surfaces. They are now unreachable on a themed page, i.e. dead
  weight that will mislead the next reader. `test_the_second_cms_dark_system_is_
  still_recorded_as_open` still guards it. **Risk: low** (dead code), **cleanup
  cost: a day**, because the whole Tailwind dark table has to be re-derived.
- **Pressed-state feedback is still flattened for ~53 of the 133 `active:bg-*`
  utilities.** The rest state is now correct everywhere, and `active:bg-gray-*`
  and `active:bg-indigo-*` were given explicit pressed fills, but families like
  `active:bg-amber-100` map to the same token as their resting fill, so the press
  is invisible on those. **Risk: low** — a missing affordance, not a contrast
  failure. The global `button:active` transform still fires.
- **The contrast audit is not a test.** The 660-pair sweep was run from a
  scratch script; nothing in `backend/tests/` will fail if someone re-introduces
  a `bg-white` or relaxes a mix ratio. `test_portal_theme_contract.py` still only
  checks that a *mapping exists*, not that it is *readable*. **Risk: medium —
  this is the most likely way the pass regresses.** Porting the sweep into
  `test_portal_theme_contract.py` is the highest-value follow-up.
- **`disabled:opacity-40/50` is still used on ~10 buttons.** Only the
  `disabled:bg-gray-*` path was moved onto the token pair; the opacity-only
  buttons still signal unavailability with transparency, which is the pattern
  `docs/Design_System.md:111-127` rules out. **Risk: low.**
- **Hardcoded hexes remain outside the override layer**: `.sl::-webkit-scrollbar-
  thumb` (`#c7d2fe`), `.pin-dot` / `.pin-input` (`#e5e7eb`, `#6366f1`), and
  `.img-skel`'s shimmer gradient. All are small, none carry text, none were
  measured. **Risk: low, cosmetic.**
- **The edit form inside the profile sheet was not restructured.** It is still
  one long column; only the read view was tabbed. **Risk: none** — it is a form,
  and a form is legitimately linear — but it is now visibly inconsistent with the
  read view beside it.
- **Not verified against a logged-in CMS.** Authenticating was out of scope, so
  the tab structure was verified by mounting the component in the real page and
  driving it, and the colour work by measuring `getComputedStyle` on synthesised
  class combinations. The *assembled* profile sheet with real student data has
  not been seen on screen. **Risk: medium for the tab layout specifically** — the
  contrast numbers do not depend on it, but a layout mistake inside a panel would
  not have been caught.

---

## 8. Customer-facing compliance pages and brand repair (2026-07-30)

### 8.1 What was wrong

The product gateway footer links two pages that the brand migration missed
entirely. `customer-resources/FAQ.html` and `Release_Notes_v8.0.1.html` still
declared the **retired** palette inline — forest `#15312e` on `#f7f3eb`, a sage
`#dce9df` note band, a `#d7a93d` focus ring.

Root cause of the miss: `backend/tests/test_product_home_brand.py:7` only ever
loaded `product-home.html`. Nothing in `customer-resources/` was inside the
regression net, so the two pages kept an obsolete palette without a single test
failing.

The FAQ was also **factually wrong after today's launch**. It answered "Is this
already a production AWS deployment?" with "No. The current service runs locally
… exposed through Cloudflare Tunnel. AWS hosting, production backups, restore
testing … are pending." All of that is stale as of §0.

### 8.2 What changed

- Both pages re-based on the canonical tokens through a shared
  `backend/frontend/assets/customer-resources.{css,js}`, so the next brand
  change touches one file rather than four.
- FAQ and release notes rewritten against the facts in §0. Deliberately **not**
  over-corrected: monitoring, an SLA, privileged-account MFA and off-box media
  backup are still absent and are still disclosed as absent.
- Two new compliance pages, bilingual on the same `data-lang` mechanism as the
  gateway:
  - `customer-resources/Privacy_Policy.html`
  - `customer-resources/Terms_of_Service.html`
- `product-home.html` footer links both; `backend/server.py` allow-lists both.

### 8.3 Legal identity (owner-supplied, 2026-07-30)

```
PWE GROUP PTY LTD
ABN 55 606 664 546        ACN 606 664 546
Caulfield North, Melbourne, Victoria, Australia
lee.liu.melbourne@gmail.com      Privacy contact: Lee L
Governing law: Victoria, Australia
```

The ABN checksum verifies (weighted sum 534, `534 mod 89 = 0`) and the ACN it
implies verifies independently (check digit 6). **Format and checksum only —
registration status was not looked up**, so neither page asserts more than the
identity itself.

### 8.4 Still open before these pages are relied on

| | Item | Note |
|---|---|---|
| 🟠 | Deliverable postal address | Suburb-level only. A privacy policy normally needs an address that can receive a written access/correction request. Nothing was invented. |
| 🟠 | Domain mailbox | `pwestudio.online` has **no MX record** — `info@` cannot receive mail, which is why the owner's Gmail is published instead. Move to `privacy@pwestudio.online` once MX exists. |
| 🔴 | Australian legal review | Two sections carry `Needs legal review` on the page itself: retention of children's teaching records, and how a deletion request interacts with record-keeping duties. The studios teach children; this is not a wording preference. |
| 🟠 | Liability and insurance | `Terms_of_Service.html:126` marks the cap, indirect-loss exclusion and insurance requirements as intentionally unresolved. |

Both pages carry a draft qualifier at the top, matching how
`docs/customer/Service_Agreement_Draft.md` positions itself.

### 8.5 The regression net that was missing

`backend/tests/test_customer_resources_brand.py` (new, 17 tests) now covers
**every** page in `customer-resources/`, not one hand-picked file:

- retired palette values fail the build; canonical tokens must be present
- no page may declare its own palette instead of reading the shared asset
- bilingual `data-lang` coverage, no leftover `{{PLACEHOLDER}}`
- legal entity present on the compliance pages, draft qualifier present
- the privacy policy must cover children and publication consent, must disclose
  the open gaps, and **must not promise a response deadline** while the
  contact channel is a personal mailbox
- the FAQ must state the live deployment, not the retired boundary
- Family Amber `#F5B335` may never be used as text on a light surface — that is
  what the accessible `#A16207` exists for
- the gateway footer must link every page, and `server.py` must allow-list every
  page shipped

Verification: **242 pytest** (was 206) + terminology, escaping and inline-script
checks all green.

### 8.6 UI/UX upgrade plan

`docs/design/UI_UX_Upgrade_Plan_2026-07-30.md` (1,593 lines) — analysis only,
no code changed by it. Highest-priority finding, which is a live defect rather
than a polish item: `tenant-template/index.html:265` `.result-card` hard-codes
`color:#EFE9DD` against `background:var(--ink)`. Under a light theme that is
13.69:1; under a dark theme `--ink` becomes the light text colour and the
registration success card renders at **1.06:1 — invisible**. The 56px check mark
sits at 1.21:1 and the "back to home" control at :538 has the same problem.

---

## 9. Commercial plan quota revision (2026-07-30, owner decision)

Quotas only. **Prices, plan codes, plan names and feature flags are unchanged**
(Starter 49 / Studio 99 / Growth 199 AUD per month; one-off Setup fee AUD
299–999 also unchanged).

| Plan | AUD/month | Students | Team users | Storage | `storage_limit_mb` |
|---|---:|---:|---:|---:|---:|
| Starter | 49 (unchanged) | 100 (unchanged) | 2 → **1** | 5 GB → **2 GB** | 5120 → **2048** |
| Studio | 99 (unchanged) | 500 (unchanged) | 8 → **5** | 30 GB → **10 GB** | 30720 → **10240** |
| Growth | 199 (unchanged) | 1500 → **1000** | **20 (unchanged)** | 100 GB → **50 GB** | 102400 → **51200** |

`growth.user_limit` stays at **20**: the owner revised only Growth's storage
allowance and student ceiling and did not specify a team-account figure, so the
existing value was preserved rather than invented.

### 9.1 Files changed

Database / seeds:

- `backend/db/migrations/0021_plan_quota_revision.sql` — **new**, idempotent
  quota UPDATEs scoped by plan code (the pending production change, see §8.2).
- `backend/db/schema_v1.sql` and `backend/db/migrations/0001_schema_v1.sql` —
  baseline `INSERT INTO plans` seed rows carry the new quotas, so a fresh
  bootstrap is already correct and 0021 is a no-op there. Both stay in sync per
  the migration discipline.
- `backend/scripts/seed_local_test_tenants.py` — the isolation-fixture `studio`
  plan row now seeds `5, 10240`.
- `backend/test_tenant_isolation.py` — the storage-quota check restores
  `studio.storage_limit_mb` to `10240` instead of `30720` after temporarily
  forcing it to 1 MB.

No new tables, so `backend/studiosaas/services/tenant_archive.py`
`SNAPSHOT_TABLES` is **verified unchanged** — `plans` is a platform-global
table and was never a tenant-scoped snapshot member.

Customer-facing surfaces:

- `product-home.html` — the three public pricing cards, both `en` and `zh`
  spans (Starter "1 team user / 1 个团队账号" is singular).
- `docs/customer/Pricing_and_Package_Boundaries.md` — subscription catalogue.
- `docs/StudioSaaS_Blueprint_v2.md` — plan table.
- `docs/sales/PWE_Studio_销售介绍.pptx` (**current deck**, referenced by
  `README.md` and `docs/sales/talk_track.md`) and
  `docs/sales/PWE_StudioSaaS_销售介绍.pptx` (superseded earlier copy still in
  the repo) — slide 11 pricing table only. Both decks were rewritten
  part-by-part so that `ppt/slides/slide11.xml` is the **only** changed entry
  of 97; `scripts/office/validate.py --original` passes and a LibreOffice
  render of slide 11 before/after shows identical layout with no overflow.

Migration-inventory references bumped 0020 → 0021: `docs/Database.md` (with a
new 0021 paragraph), `docs/Architecture.md`, `docs/Development_Roadmap.md`,
`README.md`.

### 9.2 Production change — APPLIED 2026-07-30 (was: SQL only, not applied)

> **Superseded.** This section was written before the v8.1.0 deploy. Migration
> `0021` is now applied in production: 21 migrations recorded, quotas read
> `starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`. The
> procedure below is kept because it documents the two application paths and
> the reasoning; the "not applied" framing no longer describes reality. See
> §7.5 for the deploy that applied it.

`pwestudio.online` still holds the old catalogue. Editing the repository seed
does not touch a running database. Two ways in, neither performed here:

1. **Preferred — normal deploy.** `deploy/aws/entrypoint.sh` runs
   `scripts/run_migrations.py` with the owner role on every container start, so
   0021 applies by itself with the next
   `bash deploy/aws/pwestudio_remote.sh deploy <tarball>` once the bundle
   contains it. `schema_migrations` gains
   `0021_plan_quota_revision.sql` and the instance moves from 20 to 21 applied
   migrations (the §0 table still records the measured 20).
2. **Quota-only, without a redeploy.** Run the migration body by hand as the
   owner role, then insert the ledger row so the next deploy does not re-run it:

```sql
BEGIN;

UPDATE plans SET user_limit = 1, storage_limit_mb = 2048
 WHERE code = 'starter' AND (user_limit <> 1 OR storage_limit_mb <> 2048);

UPDATE plans SET user_limit = 5, storage_limit_mb = 10240
 WHERE code = 'studio' AND (user_limit <> 5 OR storage_limit_mb <> 10240);

UPDATE plans SET student_limit = 1000, storage_limit_mb = 51200
 WHERE code = 'growth' AND (student_limit <> 1000 OR storage_limit_mb <> 51200);

INSERT INTO schema_migrations (version)
VALUES ('0021_plan_quota_revision.sql')
ON CONFLICT DO NOTHING;

COMMIT;
```

Verify afterwards:

```sql
SELECT code, monthly_price_aud, student_limit, user_limit, storage_limit_mb
  FROM plans WHERE code IN ('starter','studio','growth')
 ORDER BY monthly_price_aud;
-- expect: starter 49/100/1/2048, studio 99/500/5/10240, growth 199/1000/20/51200
```

### 9.3 Safety review of the reduction

1. **Over-quota behaviour is refuse-to-add, never delete.** Three enforcement
   points, all admission control on a *new* record:
   `api_v1._student_capacity` + its two call sites (student create, registration
   conversion) return 403 when `current >= student_limit`; the team
   create/reactivate paths return 403 when active non-`parent` memberships
   `>= user_limit`; `services/media._assert_storage_quota` raises
   `MediaQuotaExceededError` before an upload is written. Nothing archives,
   truncates or deletes existing students, members or media, so a tenant found
   above a lowered ceiling keeps all of its data and simply cannot grow until
   the plan is upgraded.
2. **`lets-play-piano` sits exactly at the new Starter ceiling** (1 of 1 team
   accounts). It keeps working; it cannot add a second account. The refusal
   text is explicit rather than a bare 403 body:
   `User limit reached (1). Upgrade the plan before adding another team member.`
   — plan name, the actual number and the required remedy. The student-side
   equivalents read `Student limit reached (N). Ask the StudioSaaS
   administrator to upgrade the plan.` and `… Upgrade the plan before
   converting this registration.`
3. **`isolation-no-portfolio` (price 1) exists in the production `plans`
   table.** It is the `backend/test_tenant_isolation.py` fixture plan
   (`500 / 8 / 1024 MB`, portfolio flag off) that leaked into the production
   database — reported, deliberately **not** deleted and deliberately **not**
   re-quoted by 0021, which is scoped to the three real plan codes. Cleaning it
   up is a separate decision because a tenant row may still reference it.

Known cosmetic non-issue, **not changed**: `super-admin.html
formatStorageMb()` prints one decimal below 10240 MB, so the Starter quota
renders as "2.0 GB" where the pricing page says "2 GB" (previously "5.0 GB"
vs "5 GB" — same pre-existing behaviour, not a regression). The decimal is
load-bearing for *used*-storage display, so the formatter was left alone. The
"Add Plan" form defaults (`149 / 800 / 12 / 51200`) describe a hypothetical new
custom plan, not Starter/Studio/Growth, and were also left alone.
