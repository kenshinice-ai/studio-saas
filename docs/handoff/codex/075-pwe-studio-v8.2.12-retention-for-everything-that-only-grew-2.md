# PWE Studio v8.2.12 — retention for everything that only grew (2026-08-02)

**Shipped.** Audited every store on the box that accumulates. Four had no
ceiling; the notable part is that the retention *policy* already existed and had
simply never been connected to anything.

## What was measured

```text
store                          cap                    state
docker app container log       10 MB x 5              capped
docker db container log        none                   UNCAPPED  -> fixed
volume tarballs                find -mtime +7         capped (743 MB on disk)
postgres dumps                 none                   UNCAPPED  -> fixed (30d)
audit_logs                     script exists, 730d    NEVER SCHEDULED -> fixed
public_analytics_events        script exists, 365d    NEVER SCHEDULED -> fixed
notification_logs              none                   not in the script -> added
student_access_sessions        none                   not in the script -> added
student_access_attempts        none                   not in the script -> added
/var/log/pwestudio-*.log       no logrotate entry     -> documented
```

`audit_logs` is already the **largest table in the database** — 4,413 rows in
31 days (~142/day, 1.3 MB of a 13 MB database) across six pre-launch tenants,
and the rate scales with tenant count.

## The interesting failure: a policy nobody called

`prune_event_tables.py` shipped with the retention window in its docstring and
the instruction "Schedule monthly", and was then never scheduled. The only cron
entry on the instance is the backup. Two years of default retention means
nothing would have gone wrong for two years, by which point nobody would
remember to look.

It is now a first-class command so a schedule has something stable to call:

```bash
bash deploy/aws/lightsail_ctl.sh prune --dry-run   # on the box
bash deploy/aws/pwestudio_remote.sh prune          # from a laptop
```

That indirection is not decoration — README_AWS.md §9 already records that a
cron line pointing straight at a path inside the image is exactly how the daily
backup silently failed for weeks (`scripts/` vs `backend/scripts/`).

## Three tables added to the policy

The original pass covered the two that grow with *operator* actions and missed
the three that grow with *traffic*: a row per message sent, a row per student
login, a row per rate-limit window.

```text
notification_logs         created_at        365 days
student_access_sessions   expires_at         30 days   (dead once expired)
student_access_attempts   updated_at         30 days   (lockout long past)
```

**`student_publication_consent_events` is deliberately excluded and must stay
that way.** It is legal proof of consent, and a tenant archive snapshot is the
only other copy.

Verified against the local database with a one-day window, which is the only
way to prove the column names resolve — every table returned rows
(6096/44/6/3/0). Production dry run: 0 rows to delete, as expected for a
one-month-old database.

## Installed on the instance

Both files are in place; the code change alone would have changed nothing.

```text
/etc/cron.d/pwestudio-prune      15 4 1 * *  (after the 03:15 backup, so a dump exists first)
/etc/logrotate.d/pwestudio       monthly, rotate 6, compress
```

`logrotate -d` validates the config; `cron.d` now holds `pwestudio-backup` and
`pwestudio-prune`. A backup run after the change completed clean with the new
dump-retention step, and both containers report `max-size 10m / max-file 5`.

## isolation-alpha archived

A local isolation-test tenant seeded into **production** on 2026-07-29 —
`settings.test_fixture = true`, four users on `@isolation-alpha.test` and
`@studiosaas.local`, all data synthetic. Archived, not permanently deleted:
archiving is reversible (`/v1/admin/tenants/<id>/restore`) and writes the
snapshot, while permanent delete is irreversible and the product asks for a
typed `DELETE isolation-alpha` for that reason. Finish it in the console when
you want the records gone.

```text
/app/backend/archives/tenants/isolation-alpha-20260802-082317
  db/    31 JSON snapshots
  media/
  352K total
```

That is also the **first end-to-end proof of the v8.2.10 archive fix** — before
it, this call died with `PermissionError` on the retention volume.

`archived_by` is NULL on purpose: no console operator did this.

---

