# PWE Studio — Current Handoff

Date: 2026-07-29

Authoritative release baseline: `VERSION` + Git tag `v7.8.1`

Current working branch: `codex/pwe-feather-star-brand-rollout`

Current delivery boundary: local SaaS service + on-demand Cloudflare invitation
testing + buildable PWE Studio Edition customer package.

Explicitly deferred: AWS deployment; automated media-volume backup.

## 1. Current product truth

One codebase supports two deliberate operating modes:

| Mode | Contract |
|---|---|
| SaaS delivery | Multi-tenant platform control plane, Super Admin, support sessions, local pilot and invitation-only Cloudflare path |
| Standalone Edition | Customer-owned, exactly one active tenant total, no platform membership, no platform control-plane routes |

The v7.8.1 SaaS release baseline reports:

```json
{
  "appVersion": "7.8.1",
  "db": "ok",
  "mode": "saas",
  "ok": true,
  "service": "PWE Studio SaaS API",
  "showProducerCredit": true,
  "version": "v1"
}
```

Local: `http://localhost:8899`

Invitation URL: `https://studiosaas.cc.cd`

The public URL is online only while `START_STUDIOSAAS_ONLINE.command` is
running. It is not an AWS deployment.

## 2. v7.8.1 completed scope

### Golden-ratio UI/UX system

- Added shared phi, 61.8/38.2 track, Fibonacci spacing, modular type, readable
  measure and 144/233ms motion tokens without changing tenant colour themes.
- Rebalanced Portal hero, about/principal and family-action sections around a
  clear primary/secondary hierarchy.
- Rebalanced Quick Registration as a 38.2% explanation and 61.8% form on
  desktop, with a single-column mobile flow and no sticky copy on mobile.
- Rebalanced Studio Admin editing/preview and preview hero hierarchy.
- Applied the same spacing rhythm to Super Admin cards and operational
  primary/secondary content.
- Reworked the CMS dashboard lead into a 61.8% Today Command Centre and 38.2%
  KPI rail on wide screens; dense tables and peer controls stay equal-width.
- Rebuilt `cms-app.js` and regenerated all five tenant workspaces from their
  canonical sources.

### Brand assets and governance

- Preserved every supplied Paradise Production source asset and added a
  deterministic, validated project asset library under `01 BRAND ASSETS/`.
- Added the brand architecture, asset manifest, design tokens, usage README,
  raster-export builder and asset validator.
- Added deployable PWE Studio SVG/PNG/PWA marks in dark/light, mark-only and
  horizontal lockup variants.
- Replaced the historical Crafted-P with the approved Feather Star and a
  two-line `PWE STUDIO` authored wordmark.
- Locked the mark story: the four-point star is the starting point of
  creativity; the three feather blades represent growth, ascent and
  possibility. Their source lengths follow `136 : 84 : 52`.
- The Paradise wing remains the parent/producer mark and is not merged into
  or substituted for the PWE Studio logo.
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
  - SaaS and Edition default: text-only `Powered by Paradise Production`.
  - paid removal: `STUDIOSAAS_SHOW_PRODUCER_CREDIT=0`.
  - invalid values raise an explicit runtime error; there is no silent fallback.
- Studio Admin, Portal, Register and CMS now keep tenant Logo/name as their
  primary identity. No PWE or Paradise logo is used as a tenant fallback.
- Health now exposes `mode` and `showProducerCredit` in addition to the
  independent API-contract version and app release.
- Edition install/compose defaults and customer/runbook documentation are
  synchronized to v7.8.1.

### Sales and documentation

- Reworked the 13-slide sales deck around the Feather Star story and canonical
  family palette.
- PWE Studio remains primary. Paradise Production appears as text-only producer
  attribution, never as a competing product logo.
- Removed the unresolved email placeholder without inventing contact details.
- Updated the talk track, README, API/Admin/Deployment/Design System/Brand
  Identity documents and every role guide to the v7.8.1 release boundary.

## 3. Verification evidence

- Brand assets: **76 files validated**, including **15 exact raster dimensions**.
- Python compile, shell parse, inline-script compile, CMS source/build
  consistency, UI escaping and terminology checks: passed.
- Pytest suite in the PostgreSQL-required release gate: passed.
- Legacy CMS smoke: **73 passed, 0 failed**.
- PostgreSQL tenant isolation/privacy and Edition gates:
  **216 passed, 0 failed**.
- `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`:
  **all checks passed** outside the filesystem/port sandbox.
- Local deep health: `appVersion=7.8.1`, `mode=saas`, `db=ok`,
  `showProducerCredit=true`.
- The Feather Star and golden-ratio UX rollout is accepted locally against
  Portal, CMS, Studio Admin, Register and Super Admin entry points.
- Browser acceptance:
  - 375px Register and 812×375 landscape: no horizontal overflow; the language
    toggle, return link, privacy link and submit action all expose at least a
    44px touch target.
  - 768px `/studio-admin`: the intentional legacy redirect reaches Super Admin
    without horizontal overflow.
  - 768px CMS: no horizontal overflow; controls and language actions meet the
    44px touch-target floor.
  - 1024px Portal: the 61.8/38.2 hero split renders without horizontal
    overflow.
  - 1440px Super Admin: no horizontal overflow; login fields, language actions
    and the primary action meet the 44px touch-target floor.
  - Local application log: no browser-request 5xx or traceback detected.
- Sales deck:
  - all 13 slides reviewed at full size;
  - template fidelity: **0 issues**;
  - overflow test: passed;
  - unresolved placeholder audit: empty.

## 4. Cloudflare connector reconciliation

During v7.8.0 public acceptance, Cloudflare initially returned the old health
shape even though the local process was v7.8.0. Tunnel inspection found two active
connectors for the same tunnel. The obsolete connector
`9a148978-0fcb-441b-98db-55ba785867ec` was explicitly cleaned up and the public
response immediately converged to v7.8.0.

The old connector later re-advertised itself, which proves that an external or
otherwise unmanaged Cloudflare process still holds the same tunnel credentials.
Only the current launcher-owned process was visible in the local process and
launchd audit, so the unknown source was not killed by guesswork. v7.8.1 is
committed and packaged in this scope but is not deployed to the invitation
URL; no v7.8.1 public-health claim is made.

This is an operational residue, not a v7.8.1 code failure. Before moving from
invitation testing to a persistent public environment, locate the other host or
rotate the tunnel credential so exactly one managed connector remains. Do not
run a second unmanaged connector for the same tunnel.

## 5. Packaging and delivery

The clean committed release gate builds two archives:

- `PWE-StudioSaaS-aws-7.8.1.tar.gz` — SaaS source/deployment package.
- `PWE-Studio-Edition-7.8.1.tar.gz` — customer-owned Edition package.

Each archive has a sibling `.sha256`. `BUILD_INFO` must match the release
version, mode and clean Git commit. Internal handoffs, audits, prompts, CI
metadata and sales-source files must remain excluded from customer archives.
The `.sha256` sidecars generated from the final tag commit are authoritative.

## 6. Honest limitations and deferred work

- PostgreSQL backup/restore is automated and verified. Media files are
  persistent and transfer bundles verify their integrity, but v7.8.1 does not
  automate media-volume backup or an offsite media copy.
- No AWS/RDS/S3/SES resource was changed or deployed in this release.
- The pilot rate limiter is process-local, suitable only for the accepted
  single-process local/Cloudflare invitation runtime.
- Edition scripts pass syntax, integration and clean-package gates. A real
  customer Ubuntu host still requires the delivery-day install/upgrade/restore
  rehearsal in `standalone-edition/RUNBOOK.md`.
- `cloudflared` 2026.6.1 passed its DNS/QUIC/HTTP2/API prechecks but reports an
  available 2026.7.3 update. Updating it is maintenance, not a v7.8.1 blocker.
- The named tunnel still advertises one unmanaged historical connector in
  addition to the launcher-owned connector. Persistent public operation
  requires credential/process reconciliation and a separate v7.8.1 deployment.

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
