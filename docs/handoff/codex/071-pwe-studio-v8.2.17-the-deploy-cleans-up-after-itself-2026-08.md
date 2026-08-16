# PWE Studio v8.2.17 — the deploy cleans up after itself (2026-08-02)

## Result

```text
                      before          after
disk                  9.4 GB          8.3 GB      of 58 GB
docker images         21 / 1.91 GB    6 / 994 MB
release directories   18 / 340 MB     3 / 57 MB
uploaded bundles      23 / 295 MB     1 / 14 MB
build cache           1.67 GB         1.49 GB     converging on a 1 GiB cap
/opt/pwestudio        1.47 GB         952 MB
```

`prune-artifacts` runs automatically at the end of every successful deploy, so
this stays true without anyone remembering.

## Why there were 19 image tags with 2 in use

This is the tail of an earlier fix, and worth understanding before changing it.

`docker-compose.yml` tags the image `studiosaas:${STUDIOSAAS_VERSION}`. Nothing
used to update that variable, so **every release overwrote the same tag**:
deploying 8.1.0 produced an image labelled `studiosaas:8.0.1` running an app
that reported 8.1.0. `docker images` lied to whoever was diagnosing an incident,
and the tag was useless as a rollback point.

The fix pinned the version per release — correct, and it turned one
overwritten tag into one new tag per deploy with nothing ever removing them.
**Retention is the half that was missing, not the tagging.** Keeping 3 gives an
instant `compose up` fallback without a rebuild; the automated rollback path
does not need them at all, because it re-points `current` and runs
`compose up --build` from the release directory.

## Why the build cache was 1.7 GB, and why `prune -a` is the wrong tool

`docker builder du --verbose` on the largest entry:

```text
Description:  mount / from exec /bin/sh -c pip install -r deploy/aws/requirements.lock
Size:         96.05MB
Usage count:  23
Last used:    7 minutes ago
```

That entry is why a deploy takes a minute instead of five, and `builder prune
-a` deletes it. It would also slow the rollback path, which rebuilds.

The rest is per-build layers: the Dockerfile does `COPY deploy/aws/requirements.lock`
→ `RUN pip install` → `COPY . .`, so the pip layer is stable and everything
after `COPY . .` is rebuilt on every deploy — about 30 MB a build, retained
forever.

**An age filter was tried first and reclaimed 0 B.** `until=336h` finds nothing
on an instance whose entire history is four days old. Cache pressure here is a
function of deploy count, not of time. The cap is a size with least-recently-
used eviction, which keeps the hot pip layer and drops the stale per-build
layers; the first run evicted 303 MB, all of it last accessed 2–3 days ago.

The flag was renamed between engine versions — `--keep-storage` on Docker ≤ 28,
`--max-used-space` on 29+, and this host runs 29.6.2. The script probes rather
than pins, because pinning the wrong one prunes nothing while printing what
looks like success.

## Two small bugs the first live run exposed

* `*.tar.gz` left every `.sha256` sibling behind. The match now covers both and
  is scoped to `PWE-Studio*`, so a portable snapshot or a one-off export parked
  in `incoming/` is never touched.
* A stray `hello-world:latest` image is still on the host from some early
  smoke test. Harmless (25 kB) and deliberately not auto-removed — the prune
  only ever touches `studiosaas:*` tags.

## Ordering that matters

`prune-artifacts` runs **only after the new release reports healthy**, so it can
never race the rollback branch for the directory that branch needs. And the
current release is protected **by name, not by position**: it is usually the
newest, but a rollback makes it older than the release it replaced, and a
`ls -1t | tail` rule would then delete the running release.

## Knobs

```text
PWESTUDIO_KEEP_RELEASES          3            current + rollback target + spare
PWESTUDIO_KEEP_IMAGES            3
PWESTUDIO_BUILD_CACHE_MAX_BYTES  1073741824   1 GiB
```

## Future work, in the order it will matter

1. **Nothing watches disk.** Every retention rule now exists, but if one breaks
   the first symptom is a full volume. A `df` threshold in the deep-health
   payload, or a cron that alerts past 80%, is the cheap next step.
2. **Backups are on the same disk as the data.** `backups/` is 881 MB of the
   8.3 GB used, and an instance loss takes both. README_AWS.md §9.2 already
   recommends S3 or EBS snapshots; neither is set up.
3. **The build could be smaller.** `COPY . .` copies the whole tree including
   `docs/`, `customer-resources/` and tests. A tighter `.dockerignore` would cut
   both image size and the per-build cache layer.
4. **`hello-world` and the 8.0.1 checksum stray** suggest the instance has never
   had a from-scratch inventory. Worth one pass now that retention exists.

---

