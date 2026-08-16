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

