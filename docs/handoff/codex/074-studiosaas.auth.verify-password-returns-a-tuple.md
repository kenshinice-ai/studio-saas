# studiosaas.auth.verify_password returns a TUPLE:
def verify_password(password, expected_hash) -> tuple[bool, bool]:   # (ok, needs_upgrade)

if verify_password(seed, row["password_hash"]):   # (False, False) is TRUTHY
```

Every account matched because every non-empty tuple is truthy. Re-run with
`verify_password(...)[0]`:

```text
seed admin123456 : 0 of 16
no match         : 16 of 16
```

Nothing was rotated — the bulk credential change was blocked by a permission
prompt before it ran — so no damage was done. The lesson is the ordinary one:
a security claim that says *everything* is affected is far more likely to be a
bug in the check than a real finding, and should be re-derived a second way
before it is written down. The user disputing it ("I log in with that password
every day") was the signal that found it.

## Actual account state on production

```text
admin@studiosaas.local        System Administrator   super_admin @ PLATFORM
lee.liu.melbourne@gmail.com   Lee Liu                super_admin @ PLATFORM   (new)
dance@dancedance.com                                 owner       @ dance-dance
mengqi.wu9364@gmail.com                              owner       @ ruby-s-studio
owner@dance-dance.test                               owner       @ dance-dance
owner@lets-paint-studio.test                         owner       @ lets-paint-studio
owner@lets-play-piano.test                           owner       @ lets-play-piano
owner.showcase@pwe-studio.invalid                    owner       @ lets-paint-showcase
manager.showcase@pwe-studio.invalid                  manager     @ lets-paint-showcase
frontdesk.showcase@pwe-studio.invalid                front_desk  @ lets-paint-showcase
teacher.showcase@pwe-studio.invalid                  teacher     @ lets-paint-showcase
frontdesk@isolation-alpha.test                       (no membership)
teacher@isolation-alpha.test                         (no membership)
tenant-admin.alpha@studiosaas.local                  (no membership)
owner.alpha@studiosaas.local                         (no membership)
owner.beta@studiosaas.local                          (no membership)
owner@lets-play-game.test                            (no membership)
```

All hashes are pbkdf2. The six membership-less rows are leftovers from deleted
tenants — they can authenticate but reach nothing. Disabling them is a
tidiness item, not an exposure: `rotate_pilot_credentials.py --disable-orphans`.

## The one real credential defect found

`rotate_pilot_credentials.py` selected `role IN ('super_admin', 'owner',
'staff')`. The role vocabulary in production is **super_admin / owner / manager
/ front_desk / teacher** — there is no `staff` role at all. A rotation run
against this database would have silently skipped every manager, front-desk and
teacher login and reported success. Now selects every active membership
whatever the role, and gained `--exclude`, `--disable-orphans` and `--dry-run`.

## isolation-alpha permanently deleted

Archived first, then deleted with the `DELETE isolation-alpha` confirmation
phrase. The archive survives the delete by design, and now carries the final
snapshot too:

```text
/app/backend/archives/tenants/isolation-alpha-20260802-082317
  db/                       31 JSON snapshots
  final-delete-snapshot/    31 JSON snapshots
  media/
```

Its four users are now membership-less rows in the list above.

## Release evidence no longer goes stale by design

The page sat at v8.1.0 while production ran v8.2.11, and the cause was the
filename. `Release_Notes_v8.1.0.html` carried the version, so keeping it current
meant renaming a file, editing an allowlist, a link, a CSS comment and three
tests — every release. The step that gets skipped is the one nothing checks.

* The file is now `Release_Notes.html`. No version in the URL, nothing to rename.
* Every versioned name ever published still 301s to it.
* Content extended with a "Since v8.1.0" section covering v8.2.3 → v8.2.13 in
  customer-readable terms.
* `test_release_notes_track_the_shipped_version` asserts the page mentions
  whatever `VERSION` says, so the next release cannot quietly leave it behind.

## Second platform super-admin

`lee.liu.melbourne@gmail.com`, platform-level `super_admin` (tenant_id IS NULL,
so it covers tenants created later). Generated password, never printed, at
`/data/credentials/platform-admins.txt` (0600) on the `studiosaas-data` volume:

```bash
ssh pwestudio "cd /opt/pwestudio/current && docker compose -p pwestudio --env-file /opt/pwestudio/shared/production.env -f deploy/aws/docker-compose.yml -f deploy/aws/docker-compose.lightsail.yml --profile local-db exec -T app cat /data/credentials/platform-admins.txt"
```

`seed_super_admin.py` gained `--random-password`, which generates the value,
suppresses printing and writes it to the 0600 file — because passing a secret
through `STUDIOSAAS_ADMIN_PASSWORD` puts it in the process list on a shared
host. To set a password of your own choosing instead:

```bash
ssh pwestudio
cd /opt/pwestudio/current
read -rs -p 'new password: ' PW && export STUDIOSAAS_ADMIN_PASSWORD="$PW"
docker compose -p pwestudio --env-file /opt/pwestudio/shared/production.env \
  -f deploy/aws/docker-compose.yml -f deploy/aws/docker-compose.lightsail.yml \
  --profile local-db exec -T -e STUDIOSAAS_ADMIN_PASSWORD app \
  python backend/scripts/seed_super_admin.py --email <address> \
  --reset-password --no-print-password
unset STUDIOSAAS_ADMIN_PASSWORD
```

`read -rs` keeps it off the terminal and out of shell history.

---

