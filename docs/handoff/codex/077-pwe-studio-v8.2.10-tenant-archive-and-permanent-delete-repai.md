# PWE Studio v8.2.10 — tenant archive and permanent delete repaired (2026-08-02)

**Shipped.** Archiving a studio returned "Internal Server Error" from the
platform console, three toasts deep, *after* the operator had typed the slug to
confirm. Permanent delete was unreachable behind it (it only accepts archived
tenants). Neither had ever worked in production.

## Root cause: a volume Docker had to invent a mountpoint for

```text
PermissionError: [Errno 13] Permission denied: '/app/backend/archives/tenants'

in the container:  drwxr-xr-x  0:0      /app/backend/archives     <-- root
                   drwxr-xr-x  10001    /app/tenants
                   drwxr-xr-x  10001    /data
                   drwxr-x---  10001    /media
```

Two correct decisions that fail together, the same shape as the v8.2.6 upload
bug:

* `backend/archives` is excluded by **both** `.gitignore` and `.dockerignore` —
  archives are mutable legal-retention data (they carry the only surviving copy
  of publication-consent evidence) and must never ride inside an image.
* `docker-compose.yml` mounts a named volume at `/app/backend/archives` so they
  survive image replacement.

So the path does not exist in the image. **Docker seeds a named volume from the
image path it covers and inherits that path's ownership — but when the path is
absent it creates the mountpoint root-owned.** The app runs as uid 10001. The
Dockerfile's `chown -R ... /app` runs at build time and cannot reach a volume
that is mounted at run time.

## The fix

`deploy/aws/Dockerfile` now creates `/app/backend/archives/tenants` before the
chown, so the volume seeds as 10001.

**Deploying was enough here, and the reason is worth knowing.** Docker seeds a
named volume from the image path whenever the volume is *empty*, not only at
first creation — and this volume had always been empty, because the feature it
existed for had never once succeeded. So recreating the container on v8.2.10
copied in the new directory with its ownership. Verified in the container after
deploy:

```text
drwxr-xr-x 3 10001 10001  /app/backend/archives
archive root OK: /app/backend/archives/tenants     # _ensure_archive_base(), as the app user
```

Had a single archive ever been written, the volume would not have been empty,
nothing would have been re-seeded, and the repair would have needed a one-time
`exec -u 0 app chown -R 10001:10001 /app/backend/archives`. Keep that in mind
for any other volume mounted over a path absent from the image.

## Why the symptom was a bare 500

`archive_tenant` began snapshotting immediately and hit the permission error
mid-way. `_ensure_archive_base()` now runs first and raises `TenantArchiveError`
— which the route already maps to a 400 with the message — naming the path and
pointing at the mount rather than the code. `permanently_delete_tenant` calls it
too: that final snapshot is the only surviving copy of the tenant's
publication-consent evidence, so it must refuse rather than delete with nowhere
to write the proof.

`_archive_root()` also hardcoded `current_app.root_path / "archives"`, ignoring
configuration that the media path beside it already honoured. It now reads
`ARCHIVE_DIR` (`STUDIOSAAS_ARCHIVE_DIR`), so the retention volume can move
without a code change.

## Guards

`backend/tests/test_tenant_archive_storage.py` — 4 cases, including the
production failure reproduced with a read-only parent, asserting the error names
the path and mentions the volume. Suite: 425 passed.

---

