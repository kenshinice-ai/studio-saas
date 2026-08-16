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

