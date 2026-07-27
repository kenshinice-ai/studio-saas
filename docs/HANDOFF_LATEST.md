# StudioSaaS v7.8.0 — Current Handoff

Date: 2026-07-27

Authoritative release marker: `VERSION` + Git tag `v7.8.0`

Current delivery boundary: local SaaS service + on-demand Cloudflare invitation
testing + buildable PWE Studio Edition customer package.

Explicitly deferred: AWS deployment; automated media-volume backup.

## 1. Current product truth

One codebase supports two deliberate operating modes:

| Mode | Contract |
|---|---|
| PWE Studio SaaS | Multi-tenant platform control plane, Super Admin, support sessions, local pilot and invitation-only Cloudflare path |
| PWE Studio Edition | Customer-owned, exactly one active tenant total, no platform membership, no platform control-plane routes |

The current local and public SaaS runtimes report:

```json
{
  "appVersion": "7.8.0",
  "db": "ok",
  "mode": "saas",
  "ok": true,
  "service": "PWE Studio SaaS API",
  "showProducerCredit": false,
  "version": "v1"
}
```

Local: `http://localhost:8899`

Invitation URL: `https://studiosaas.cc.cd`

The public URL is online only while `START_STUDIOSAAS_ONLINE.command` is
running. It is not an AWS deployment.

## 2. v7.8.0 completed scope

### Brand assets and governance

- Preserved every supplied Paradise Production source asset and added a
  deterministic, validated project asset library under `01 BRAND ASSETS/`.
- Added the brand architecture, asset manifest, design tokens, usage README,
  raster-export builder and asset validator.
- Added deployable PWE Studio SVG/PNG/PWA marks in dark/light, mark-only and
  horizontal lockup variants.
- Kept the PWE Crafted-P/geometric wordmark as the product identity. The
  Paradise wing remains the parent/producer mark and is not substituted for
  the PWE logo.
- Standardized the product family palette:
  - Navy `#0E1729`
  - Amber `#F5B335`
  - accessible amber text `#A16207`
  - Warm Paper `#F7F5F2`
- Documented the shared four-point spark motif, Lockup A/B/C rules, safe areas,
  tenant-brand priority and licensing/provenance boundary.

### SaaS and Edition system surfaces

- Updated Super Admin, Studio Admin, setup-password, shared UI tokens, PWA
  manifests/icons, service-worker cache and generated tenant workspaces.
- Added strict producer-credit configuration:
  - SaaS default: hidden, so tenant pages remain tenant-first.
  - Edition default: `A Paradise Production` shown.
  - paid removal: `STUDIOSAAS_SHOW_PRODUCER_CREDIT=0`.
  - invalid values raise an explicit runtime error; there is no silent fallback.
- Health now exposes `mode` and `showProducerCredit` in addition to the
  independent API-contract version and app release.
- Edition install/compose defaults and customer/runbook documentation are
  synchronized to v7.8.0.

### Sales and documentation

- Updated the 13-slide sales deck to the canonical family palette.
- PWE remains primary; authentic Paradise Lockup C appears only on the joint
  sales cover and closing slide.
- Removed the unresolved email placeholder without inventing contact details.
- Updated the talk track, README, API/Admin/Deployment/Design System/Brand
  Identity documents and every role guide to the v7.8.0 release boundary.

## 3. Verification evidence

- Brand assets: **68 files validated**, including **15 exact raster dimensions**.
- Python compile, shell parse, inline-script compile, CMS source/build
  consistency, UI escaping and terminology checks: passed.
- Pytest suite in the PostgreSQL-required release gate: passed.
- Legacy CMS smoke: **73 passed, 0 failed**.
- PostgreSQL tenant isolation/privacy and Edition gates:
  **216 passed, 0 failed**.
- `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`:
  **all checks passed** outside the filesystem/port sandbox.
- Local and public deep health: `appVersion=7.8.0`, `mode=saas`, `db=ok`,
  `showProducerCredit=false`.
- Local and public Portal, CMS, Studio Admin, Register and Super Admin entry
  points were exercised.
- Browser acceptance:
  - 375px Portal: no horizontal overflow; producer credit hidden.
  - 768px Studio Admin: no horizontal overflow or console warnings/errors.
  - 1440px Super Admin: no horizontal overflow or console warnings/errors.
- Sales deck:
  - all 13 slides reviewed at full size;
  - template fidelity: **0 issues**;
  - overflow test: passed;
  - unresolved placeholder audit: empty.

## 4. Cloudflare connector correction

During public acceptance, Cloudflare initially returned the old health shape
even though the local process was v7.8.0. Tunnel inspection found two active
connectors for the same tunnel. The obsolete connector
`9a148978-0fcb-441b-98db-55ba785867ec` was explicitly cleaned up; the current
connector `a32ec1ed-d5ed-4ecb-9038-0a244e8292c8` remained.

After cleanup, repeated cache-busting public requests consistently returned the
complete v7.8.0 health payload. Do not run a second unmanaged connector for the
same tunnel.

## 5. Packaging and delivery

The clean committed release gate builds two archives:

- `StudioSaaS-7.8.0.tar.gz` — SaaS source/deployment package.
- `PWE-Studio-Edition-7.8.0.tar.gz` — customer-owned Edition package.

Each archive has a sibling `.sha256`. `BUILD_INFO` must match the release
version, mode and clean Git commit. Internal handoffs, audits, prompts, CI
metadata and sales-source files must remain excluded from customer archives.
The `.sha256` sidecars generated from the final tag commit are authoritative.

## 6. Honest limitations and deferred work

- PostgreSQL backup/restore is automated and verified. Media files are
  persistent and transfer bundles verify their integrity, but v7.8.0 does not
  automate media-volume backup or an offsite media copy.
- No AWS/RDS/S3/SES resource was changed or deployed in this release.
- The pilot rate limiter is process-local, suitable only for the accepted
  single-process local/Cloudflare invitation runtime.
- Edition scripts pass syntax, integration and clean-package gates. A real
  customer Ubuntu host still requires the delivery-day install/upgrade/restore
  rehearsal in `standalone-edition/RUNBOOK.md`.
- `cloudflared` 2026.6.1 passed its DNS/QUIC/HTTP2/API prechecks but reports an
  available 2026.7.3 update. Updating it is maintenance, not a v7.8.0 blocker.

## 7. Operating commands

```bash
# Full PostgreSQL-required local release gate
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh

# Validate brand artifacts
.venv/bin/python "01 BRAND ASSETS/source/validate_assets.py"

# Start local only
bash START_STUDIOSAAS_LOCAL.command

# Start invitation tunnel on demand
bash START_STUDIOSAAS_ONLINE.command

# Build and verify clean SaaS + Edition bundles
bash deploy/aws/verify_release_bundles.sh
```
