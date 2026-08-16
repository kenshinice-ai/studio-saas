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

