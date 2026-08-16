# PWE Studio v8.2.14 — orphan accounts disabled; server storage audited (2026-08-02)

## Orphan accounts

Six accounts had no membership at all — leftovers from `isolation-alpha`,
`isolation-beta` and `lets-play-game`. They could authenticate and reach
nothing. All six are now `status='disabled'`, which is reversible; the rows are
still there.

```text
active   11  every one with a real role
disabled  6  frontdesk@isolation-alpha.test  owner.alpha@studiosaas.local
             owner.beta@studiosaas.local     owner@lets-play-game.test
             teacher@isolation-alpha.test    tenant-admin.alpha@studiosaas.local
```

**A bug shipped and fixed in the same session.** `--disable-orphans` ran inside
`rotate()` and then fell through into the rotation, so asking for the tidy-up
would have silently changed every password in the database. Disabling orphans
is maintenance; rotating is incident response. `--skip-rotation` separates them,
and the production run used it.

## Server storage — measured, nothing cleaned yet

```text
disk                     9.4G used of 58G (17%)
memory                   1.9G total, 668M used, 1.2G available
containers               app 57 MB, db 45 MB — 3% each, idle CPU

reclaimable                                          size
  docker build cache     57 entries, 0 active        1.67 GB
  docker images          17 of 19 studiosaas tags    1.05 GB
  shared/incoming        23 release tarballs         295 MB
  releases/              18 unpacked dirs            283 MB (keeping 3)
  /var/cache/apt                                     110 MB
                                                     ------
                                                     ~3.4 GB

not reclaimable
  backups/volumes        39 tarballs, 7-day window   831 MB
  backups/postgres       14 dumps, 30-day window     5.9 MB
  docker volumes         live data                    95 MB
```

## The structural finding: the deploy path has no retention for its own output

`deploy` calls `ctl backup` first, so backups are covered — but everything the
deploy itself produces accumulates forever. Per release:

```text
shared/incoming/<bundle>.tar.gz     14 MB   never deleted
releases/<name>/                    19 MB   never deleted
studiosaas:<version> image          ~50 MB unique, never pruned
build cache                         grows,  never pruned
```

That is ~33 MB of permanently retained cruft per deploy before images, and
today alone had 13 deploys. It is the same class of gap as the postgres dumps
in v8.2.12: retention exists for the thing labelled "backup" and for nothing
else. The fix belongs in `pwestudio_remote.sh deploy` / `lightsail_ctl.sh`,
keeping the current release plus two for rollback and pruning the rest.

---

