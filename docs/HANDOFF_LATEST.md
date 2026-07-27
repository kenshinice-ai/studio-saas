# StudioSaaS v7.7.8 — Current Handoff

Date: 2026-07-27

Authoritative release marker: `VERSION` + Git tag `v7.7.8`

Current delivery boundary: local service + on-demand Cloudflare invitation test

Explicitly deferred: AWS deployment; automated media-volume backup

## 1. Current product truth

The repository now supports two deliberate operating modes from one codebase:

| Mode | Contract |
|---|---|
| SaaS | Multi-tenant platform control plane, Super Admin, tenant support sessions, local pilot + Cloudflare invitation path |
| PWE Studio Edition | One customer-owned installation, exactly one tenant total and active, no platform membership, platform routes closed |

The local service is currently verified from this checkout at
`http://localhost:8899`; deep health reports `appVersion=7.7.8` and `db=ok`.
The public URL remains `https://studiosaas.cc.cd` and is only expected to be
online while the on-demand tunnel launcher is running.

## 2. v7.7.8 changes completed

### P0

- Fixed Edition bundle construction and made an explicit build version differ
  from `VERSION` fail loudly.
- Moved Edition secrets, backup state and current-release pointer out of
  versioned release directories:
  - `/etc/pwe-studio/<slug>.env`
  - `/var/lib/pwe-studio/<slug>/backups`
  - `/opt/pwe-studio/<slug>/current`
- Added root-owned daily PostgreSQL backup scheduling and mandatory first dump.
- Added `upgrade.sh`: pre-upgrade dump, stable symlink switch, named-volume
  preservation and automatic code/config rollback on failed deep health.
- Added `maintenance.sh`: explicit backup, owner-role restore rehearsal and
  write-stopped real restore.
- Removed the fixed Super Admin password from launchers and seed defaults.
  Launchers preserve the existing password; only an explicitly supplied
  `STUDIOSAAS_ADMIN_PASSWORD` may create/reset it.
- Health now separates API contract (`version=v1`) from product release
  (`appVersion=7.7.8`).

### P1

- Edition startup now requires one tenant total, one active tenant and zero
  platform-scoped memberships of any role or status.
- Added a dedicated least-privilege PostgreSQL runtime role. Migrations and
  grants use the owner URL; the server process does not retain that URL or
  runtime-role password.
- Edition bundle format v2 hashes database and media payloads, rejects missing
  or undeclared files and unsafe tar members, and requires the separately
  trusted outer bundle SHA-256 during installation.
- Added clean-tree dual-mode bundle verification and a GitHub Actions release
  gate. Internal handoffs, audits, prompts, CI metadata and sales-source
  materials are excluded from customer archives.
- Updated Edition install/deploy/database/requirements/runbook/operations
  documentation and all role-guide applicability markers.
- Updated the 13-slide sales deck cover to v7.7.8 without changing sales copy
  or layout; full render, overflow and template-fidelity QA passed. Removed the
  tracked `copy.pptx` duplicate after confirming its cover still said v7.7.7.

## 3. Verification evidence

Latest completed local evidence:

- `pytest backend/tests`: **167 passed** with PostgreSQL integration enabled.
- Legacy CMS smoke suite: **73 passed, 0 failed**.
- PostgreSQL tenant-isolation/privacy suite: **216 passed, 0 failed**.
- `STUDIOSAAS_REQUIRE_POSTGRES=1 backend/scripts/verify_local.sh`: **all checks
  passed**.
- CMS source/build consistency: passed.
- Shell parsing, Python compilation, inline JS, UI escaping and terminology:
  passed.
- Local runtime:
  - `/`, `/super-admin`, portal, CMS, Studio Admin and tenant register: 200.
  - root `/register`: 404 by design.
  - `/v1/health?deep=1`: `appVersion=7.7.8`, `db=ok`.
- Cloudflare invitation runtime:
  - `https://studiosaas.cc.cd/v1/health?deep=1`:
    `appVersion=7.7.8`, `db=ok`.
  - Portal, CMS, Studio Admin and tenant register: 200.
  - root `/register`: 404; unauthenticated `/super-admin`: 302 to login.
  - Cloudflare DNS, UDP/QUIC, TCP/HTTP2 and API connectivity pre-checks:
    passed; four tunnel connections registered.

Release packaging evidence:

- The v7.7.8 implementation is committed.
- Clean committed-tree SaaS and Edition archives both passed SHA-256,
  `BUILD_INFO` version/mode/commit, delivery-entrypoint and internal-file
  exclusion checks.
- Final artifact hashes are regenerated from the final tag commit; the
  `.sha256` sidecars in `dist/` are authoritative.

Still required before the release is declared closed: fast-forward `main`,
create/push tag `v7.7.8`, and remove confirmed stale branches/worktree.

## 4. Branch reconciliation

`codex/studiosaas-v7.3.1` is the complete v7.7.7 lineage and already contains
the merged remote review branch plus all later work. Remote
`codex/studiosaas-v7.2.1`, `v7.3.0`, `v7.3.1` and
`codex/keep-studio-admin-registration-review` are ancestors of the release
lineage.

The divergent local `codex/keep-studio-admin-registration-review` commit
`9e60134` is an obsolete alternative snapshot, not an unmerged feature branch:
its lifecycle module and Ruby tenant are already present, while its presets
were subsequently expanded by 457 lines and its tree predates migrations
0015–0020, privacy modules, Edition and release tooling. Merging it would
reintroduce old files and delete current features; it should be deleted after
`main` is updated.

The `.claude/worktrees/project-audit-review-37738f` worktree points at old
v7.6.0 `main`. A server from that worktree was found occupying port 8899 and
was explicitly stopped before the current v7.7.8 runtime was started. Remove
that worktree during branch cleanup after confirming it is clean.

## 5. Deferred items and honest limitations

- Media files remain on persistent volumes and Edition transfer bundles verify
  media integrity, but v7.7.8 does **not** automate media-volume backup or an
  offsite copy. Do not describe database backup as full disaster recovery.
- AWS/RDS/S3/SES code and historical runbooks remain in Git, but no AWS resource
  change or deployment is part of this release.
- The pilot rate limiter is process-local and remains accepted for one-process
  local/Cloudflare operation; a shared store is required before multi-instance
  deployment.
- PWE Studio Edition Docker install/upgrade scripts are covered by syntax,
  unit/integration and bundle gates; a customer-host Ubuntu rehearsal remains a
  delivery-day acceptance step because this Mac is not an Ubuntu Docker host.

## 6. Operating commands

```bash
# Full local release gate
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh

# Start local only (preserves real data and existing Super Admin password)
bash start_studiosaas_local.sh

# Start invitation tunnel on demand
bash START_STUDIOSAAS_ONLINE.command

# Clean committed dual bundle gate
bash deploy/aws/verify_release_bundles.sh
```
