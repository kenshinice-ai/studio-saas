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

