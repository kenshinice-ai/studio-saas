# The live nginx configuration (canonical baseline)

These files are **what is actually running on the host**, fetched with
`bash deploy/aws/fetch_live_nginx.sh`. They are not templates and not a
proposal — they are a record. The templates one directory up
(`../studiosaas.conf`, `../studiosaas-bootstrap.conf`) are the historical
starting point and have drifted from the host.

## Why this exists (OPS-03)

A deploy replaces the application container. It does **not** touch
`/etc/nginx`. So the live web configuration was the one production surface
with no version control at all, and the only record of how it differed from
the repository was a sentence passed between handoff documents:
"不要整体覆盖" — do not overwrite it wholesale. That is a rule that survives
exactly as long as somebody remembers to repeat it.

Fetching the live file makes the divergence readable instead of remembered.

## What is here

| File | Live path | Note |
|---|---|---|
| `pwestudio.conf` | `/etc/nginx/sites-available/pwestudio.conf` | the only file in `sites-enabled` (a symlink to this) |
| `paradise-production.conf` | `/etc/nginx/snippets/paradise-production.conf` | included by the above; serves the studio's own marketing site from `/var/www` — never reaches the application |

`/etc/nginx/snippets/pwestudio-tls.conf` is also included and is byte-identical
to `../pwestudio-tls.conf`, so it is not duplicated here.

Known divergence from `../studiosaas.conf` as of 2026-08-20: the template
carries an explanatory comment block about `text/javascript` that the live file
does not (the `gzip_types` directive itself is identical), and the live file
includes the Paradise Production snippet, which the repository had no record of
until this baseline was taken.

## The edit workflow — repo first, then the host, line by line

1. Change the file **here** and review the diff.
2. Apply the same lines on the host by hand, then `sudo nginx -t` and reload.
3. Re-run `bash deploy/aws/fetch_live_nginx.sh`; it must report `unchanged`.

Step 3 is the check that the two are in sync. If it reports a difference you
did not make, somebody edited the host directly — reconcile before deploying
anything else.

**Never copy a template over the live file wholesale.** The host carries
certificate paths, the marketing-site include and log destinations that no
template in this repository knows about; a wholesale copy silently drops them.
