# PWE Studio v8.2.6 — Historical Handoff

**All findings below are fixed and released.** The diagnosis is kept in full
because the P0 was a two-component failure that neither component owned, and
that shape will recur.

## Verification for v8.2.6

```text
pytest: 316 passed (309 + 7 new in test_media_upload_privileges.py)
Legacy CMS smoke: 73/73 · Tenant isolation: 228/228
Least-privilege role rehearsal (role owning nothing, as in production):
  old code path -> InsufficientPrivilege: must be owner of table media_assets
  new code path -> ensure_media_schema() completes, no DDL issued
Upload round-trip: owner 200, super-admin without session 403 (actionable),
  super-admin with session 200
Image resources, 24 MP source (6000x4000):
  before  decoded 6000x4000, peak RSS +139 MB, 0.22s
  after   decoded 3000x2000, peak RSS  +17 MB, 0.14s
  81 MP bomb rejected as a 400, not an OOM
Browser: preview language now drives previewSections (中文 主理人/课程与班次
  <-> Principal/Courses & Classes); CTA pair switches; 3 disclosures hiding 21
  fields, all collapsed, all summaries translated; theme-picker and
  settings-shell both measure exactly 1.618; 0 overflow; no console errors
```

The regression test was checked by reverting the guard: it fails, then passes
again once restored. `media derivative backfill is incomplete` remains the
known worktree artifact (`media/` is git-ignored, so originals live only in the
primary checkout).

## What was wrong, and why it took a production log to find

## P0 (fixed) — every media upload in production returned 500

Production log, reproduced three times today (06:00, 06:37, 11:51 UTC):

```text
psycopg.errors.InsufficientPrivilege: must be owner of table media_assets
POST /s/lets-paint-showcase/v1/tenant/logo 500
```

`store_media_asset()` calls `ensure_media_schema()` as its **first statement**,
and that helper runs `ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS …`.
`ALTER TABLE` requires table ownership, and PostgreSQL checks the privilege
*before* evaluating `IF NOT EXISTS` — so the statement fails even though the
column has existed since `0001_schema_v1.sql` and `0017` already widened its
CHECK constraint. The production role is the least-privilege role introduced in
v7.7.7; it holds DML rights but does not own the table.

`store_media_asset()` is the only entry point for media, so this breaks
**logo, hero/principal images, student photos, registration photos and
portfolio uploads alike** — not only the logo.

It is not caused by the super-admin account: an owner account fails identically
in production, and locally (where the role owns the schema) both accounts
succeed.

**Fix:** stop issuing DDL on the upload path. Probe
`information_schema.columns` first and only attempt the `ALTER` when the column
is genuinely absent, so a correctly migrated database — every deployed one —
executes no DDL and needs no ownership. The helper's stated purpose is
compatibility for *older local* databases, which that preserves. Do not grant
table ownership to the application role; that would undo v7.7.7 for a code
path that should not need it.

## P1 (fixed) — super-admin support gate was correct but undiscoverable

A super-admin with no active support session gets
`403 support_session_required` with an actionable bilingual message, and
`api()` surfaces `data.message`, so the message does reach the user. After
starting a session from the Super Admin console the same upload returns 200.
The boundary works and should stay.

What is missing is the route to it: Studio Admin never tells a super-admin that
a session is required, nor offers a way to start one. **Fix:** on 403
`support_session_required`, show the reason with a link back to the tenant's
Super Admin entry. Every super-admin action on a tenant is already written to
`audit_logs` with the support-session marker merged in (`api_v1.py:1278`), so
the logging the user asked about already exists — it needs surfacing, not
building.

## P1 (fixed) — preview language switch covered 6 of 11 nodes

Measured by snapshotting every `[id^="preview"]` node in both languages:
only `previewRegisterTitle` and `previewRegisterIntro` actually changed for
this tenant. Two separate causes:

1. **Not wired.** `renderPreviewSections()` reads only the Chinese label
   fields (`settingCoursesLabel`, `settingGalleryLabel`, `settingFaqLabel`,
   `settingContactLabel`) and ignores the `*LabelEn` inputs that sit right
   beside them in the form. It also hardcodes English strings — `Principal`,
   `Student Area`, `Program cards`, `Student works` — which stay English in
   Chinese mode. `previewHeroEyebrow` has only a single-language input.
2. **Data, not code.** For `lets-paint-showcase`, `localizedCopy.heroTitle` is
   `{en: "Let's Paint Studio", zh: "Let's Paint Studio"}` and `coursesLabel` is
   `{en: "Courses & Classes", zh: "Courses & Classes"}` — both languages hold
   the same string, so a correctly wired switch still shows no visible change.
   This is why the switch reads as broken even where it works.

**Fix:** route every bilingual field in the preview through `localizedValue`,
move the hardcoded section nouns into the i18n dictionary, and mark fields
whose English is empty or identical to the Chinese so the operator can see
what still needs translating rather than guessing the switch is broken.

## P2 (fixed) — dead duplicate of the schema helper

`api_v1.py:1582 _ensure_media_schema` has no callers and its CHECK constraint
is missing `website_image`, so it is both dead and stale. Delete with the P0
fix.

## P2 (fixed) — tab density, and where disclosure belongs

Field counts per tab, measured in the running page:

| Tab | form-groups | inputs | disclosures today |
|---|---:|---:|---:|
| 报名 register | 23 | 29 | 0 |
| 品牌 brand | 22 | 26 | 2 |
| 官网 website | 18 | 23 | 0 |
| 首屏 hero | 12 | 13 | 0 |
| 常见问答 faq | 8 | 16 | 0 |
| 家长话术 messages | 5 | 5 | 0 |
| 数据分析 analytics | 0 | 2 | 0 |
| 预览与发布 advanced | 0 | 0 | 0 |

Three tabs carry 23–29 inputs in one flat column. The split that works here is
**what a studio must set to go live** versus **what it will only ever revisit**
— not "basic versus advanced", which invites hiding things people need.

- **brand**: keep studio name, logo, theme preset and the two brand colours
  open. Fold contact details (phone/email/address), the bilingual slogan pair,
  CMS layout + welcome message, and timezone. Plan is read-only and belongs
  with them.
- **register**: the tab already has two headings — 报名表 and 报名问题. The
  question editor is a repeating list that only changes when the studio
  rethinks its intake; fold it and leave the form's own copy open.
- **website**: the six switches are the tab's real subject and stay open. The
  per-section label pairs (courses/gallery/faq/contact, each 中文+English) fold
  behind one "版块名称" disclosure — six inputs that exist only to rename
  headings.
- **hero**: 13 inputs is tolerable; fold nothing. Do **not** fold the English
  half of a bilingual pair anywhere — that reads as "optional" and is exactly
  the habit that produced the untranslated `localizedCopy` above.

Reuse the `.disclosure` component added to this page in v8.2.4 (44px summary,
chevron, focus ring, `prefers-reduced-motion` handled) rather than introducing
a second pattern, and add each new summary string to `admin-i18n.js` — an
English summary on a Chinese page is the defect this page hit twice already.

Sequencing note: this and the preview-language fix touch the same panels, so
they should land in one round to avoid two passes over the same markup.

## P2 (fixed) — golden ratio applied unevenly

`.settings-shell` already uses `minmax(0, 1.618fr) minmax(360px, 1fr)`, the
proportion used across the CMS profile sheet and the product-home hero.
`.content-grid` (line 656) uses `1.5fr : 1fr` and `.theme-picker` (line 1121)
uses `.9fr : 1.1fr` — the second inverts the emphasis, giving the swatch grid
more room than the picker controls. Aligning both to 1.618 : 1 would make the
brand workspace internally consistent with the rest of the product.

