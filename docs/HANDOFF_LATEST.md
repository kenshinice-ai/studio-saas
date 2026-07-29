# PWE Studio v8.0.1 — Current Handoff

Date: 2026-07-29
Baseline: tag `v8.0.0`, commit `abc01ce6e4f281056c3c22fa665e42d7811e0688`
Release branch: `codex/v8.0.1-product-home-brand-release`
Release source of truth: `VERSION`, final `main` commit and annotated tag `v8.0.1`

## 1. Delivery boundary

v8.0.1 is a verified local release and customer-demonstration package. It is
not an AWS production deployment.

| Area | Current truth |
|---|---|
| SaaS runtime | Local Waitress + PostgreSQL; Cloudflare invitation workflow supported |
| Public product URL | `https://studiosaas.cc.cd` currently reports v7.8.1 from an unmanaged/historical connector |
| v8 acceptance runtime | `http://127.0.0.1:8901`, deep health passed as v8.0.1 |
| AWS/RDS/S3/SES | Not purchased or deployed |
| Production backups/restore/monitoring/SLA | Deferred until AWS resources exist and a production rehearsal passes |
| Online payment, provider SMS/email, custom domains | Deferred |
| Multi-campus | One campus = one tenant/subscription; future organisation aggregation is deferred |

Do not describe local testing, a source bundle or Cloudflare invitation access
as production acceptance.

## 2. What v8.0.1 delivers

### P0 — customer-safe demonstration and commercial readiness

- SaaS `/` is a bilingual product gateway with a clear product story, five
  role entrances, sales journey, plans, migration downloads and support CTA.
- v8.0.1 brings that gateway onto the canonical PWE family palette: Family
  Navy `#0E1729`, Family Amber `#F5B335`, accessible amber text `#A16207` and
  Warm Paper `#F7F5F2`. Retired forest, sage and coral values are rejected by
  a dedicated regression test.
- The gateway now follows the approved sales story—administration behind the
  scenes, creativity in front—uses Let’s Paint Studio as the demonstration
  proof, identifies Studio at AUD 99/month as the recommended plan and
  discloses the AUD 299–999 setup range.
- `lets-paint-showcase` is the only professional demonstration tenant. It uses
  fictional people/contact records and synthetic artwork.
- `RESET_DEMO_TENANT.command` and
  `backend/scripts/reset_professional_demo.py`:
  - refuse standalone mode;
  - require the exact phrase `RESET-LETS-PAINT-SHOWCASE`;
  - can only touch the permanently marked `lets-paint-showcase` tenant;
  - rotate four role passwords and one student code on every run;
  - write credentials to `~/.studiosaas/showcase-credentials.txt` as mode
    `0600`, never to stdout.
- `docs/customer/` contains a customer-readable delivery index, pricing and
  package boundaries, service agreement draft, onboarding checklist, FAQ,
  migration guide, support policy, integration boundary, multi-campus policy,
  security/privacy/compliance disclosure, demonstration runbook and release
  evidence.
- Security/compliance material explicitly discloses the pre-production state,
  privileged MFA gap, backup gate and incident-response boundary.

### P1 — connected operating experience

- Studio Admin remains the website/brand workspace and CMS remains daily
  operations; both now provide stable reciprocal navigation.
- Onboarding is documented from commercial discovery through tenant creation,
  brand publishing, operational rehearsal, migration and acceptance.
- Reviewed CSV and five-sheet XLSX templates define the supported migration
  shape. Arbitrary historic spreadsheets require assessment and may require
  separately quoted clean-up.
- Family private access shows balance, next class, attendance and portfolio,
  then opens tenant-addressed device Messages/Mail actions for schedule or
  absence enquiries.
- Active recurring schedules download as a tenant-timezone ICS file with stable
  UIDs and weekly recurrence. The export contains no roster/student data.
- Teacher mobile mode prioritises three steps: today's roster, student lookup
  and artwork upload. Non-financial roles see attendance KPIs, not revenue
  labels with zeroed values.
- Product-home Support & Feedback opens the device Mail/Messages application;
  there is no claim of automated delivery, delivery log or retry.

### P2 — sales story and deliberate extension points

- The demonstration runbook follows Let’s Paint Studio from enquiry → trial →
  enrolment → recurring schedule → attendance/credit → artwork → family view →
  owner report.
- Eight industry presets now include three bilingual starter courses,
  registration focus, report focus and a demonstration story in addition to
  industry terminology and visual themes.
- v8.0.1 supports CSV/XLSX export/import templates, ICS and device-native
  messaging. Stripe, Xero, Google/Outlook APIs, provider SMS/email and webhooks
  remain explicit extension points.
- Organisation-level multi-campus aggregation is not modelled prematurely;
  campus tenants remain isolated for permissions, billing and operations.

## 3. Demonstration data evidence

The guarded reset was run twice successfully.

| Tenant | Students | Courses | Packages | Schedules | Memberships | Credit balance |
|---|---:|---:|---:|---:|---:|---:|
| `lets-paint-showcase` | 12 | 3 | 3 | 3 | 4 | 78 |
| `lets-paint-studio` | 43 | 3 | 5 | 0 | 1 | 165 |

`lets-paint-studio` retained its pre-reset counts and balance. The showcase
also contains five enquiry states, three private portfolio works and six
metadata-sanitised display/thumbnail variants.

## 4. Verification evidence

### Repository and database gates

- `backend/tests`: **182 passed, 2 skipped**.
- Legacy CMS smoke: **73 passed, 0 failed**.
- PostgreSQL tenant isolation/privacy/Edition suite: **216 passed, 0 failed**.
- Migration check: current.
- Media derivative check: current.
- Python compile, inline scripts, shared JS, CMS source/build consistency, UI
  escaping, terminology and release/Edition shell syntax: passed.
- `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`: passed.

### Browser acceptance

Real Chrome, no page errors and no HTTP 5xx:

| Surface | Viewport | Result |
|---|---:|---|
| Product home | 375×812 | no overflow; 44px actions; skip link; language switch; reduced motion; 125% text |
| Product home | 812×375 | no overflow |
| Product home | 768×1024 | no overflow |
| Product home | 1024×768 | no overflow |
| Product home | 1440×900 | no overflow |
| Studio Admin | 1024×900 | 8 industry cards + 8 operational starter-course summaries |
| Owner CMS | 768×1024 | no overflow; authenticated ICS download |
| Teacher CMS | 375×812 | three-step flow; no financial label; no schedule mutation |
| Family private area | 375×812 | balance 8, four attendance rows, one private work, native contact actions |

Product-home display images are 760×760 WebP with intrinsic dimensions and
total **229,582 bytes** in the browser. Five role entrances render at every
tested viewport; local page load during the acceptance run was approximately
0.56 seconds.

The v8.0.1 product-home pass also verified the computed Navy hero, Warm Paper
canvas, accessible amber text, bilingual sales copy, every visible 44px target,
125% text and reduced-motion behavior. Measured contrast includes 17.90:1 for
white on Navy and 4.52:1 for amber text on Warm Paper.

The ICS response contains three recurring events, `TZID=Australia/Melbourne`,
stable weekly recurrence and no tested student name, mobile or family email.

### Migration artifacts

- `customer-resources/PWE_Studio_Data_Import_Template.csv`
- `customer-resources/PWE_Studio_Data_Import_Template.xlsx`

The XLSX contains Instructions, Students, Courses, Packages and Field Guide
sheets. All five sheets were rendered and visually inspected; ZIP integrity
and spreadsheet error-token scans passed.

## 5. Cloudflare operating truth

`START_STUDIOSAAS_ONLINE.command` now:

- pins `STUDIOSAAS_MODE=saas`;
- reads the expected application version from `VERSION`;
- supports an explicit public base domain;
- waits for local and public health;
- runs `backend/scripts/verify_tunnel_parity.py` against deep health;
- refuses to call the tunnel accepted when version, mode, database or release
  identity differs.

Current observation on 2026-07-29:

- v8 acceptance deep health:
  `appVersion=8.0.1`, `mode=saas`, `db=ok`;
- the public URL still returns `appVersion=7.8.1`;
- port 8899 is occupied by a separate `python -m http.server`, not the v8 app;
- no launcher-owned local `cloudflared` process was identified.

Therefore no v8.0.1 public Cloudflare claim is made. Resolve or rotate the
unmanaged connector before starting another connector for the same tunnel.
The launcher now fails parity instead of silently accepting this split-brain
state.

## 6. Packages and release closure

Required final clean-commit package gate:

```bash
bash deploy/aws/verify_release_bundles.sh
```

Expected outputs:

- `dist/PWE-StudioSaaS-aws-8.0.1.tar.gz`
- `dist/PWE-Studio-Edition-8.0.1.tar.gz`
- matching `.sha256` sidecars.

The SaaS package must include the product gateway, customer resources,
professional showcase workspace/assets and guarded reset. The Edition package
must exclude the showcase workspace and reset command while retaining the
shared runtime and customer/operator documentation. Both archives must pass
SHA-256, entrypoint, forbidden-content and `BUILD_INFO` checks. The `.sha256`
sidecars generated from the final tagged commit are the authoritative hashes.

## 7. Operator commands

```bash
# Local service
bash START_STUDIOSAAS_LOCAL.command

# Guarded professional showcase reset
./RESET_DEMO_TENANT.command

# PostgreSQL-required release gate
STUDIOSAAS_REQUIRE_POSTGRES=1 \
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
bash backend/scripts/verify_local.sh

# Tunnel split-brain/version parity
.venv/bin/python backend/scripts/verify_tunnel_parity.py \
  --local-base-url http://localhost:8899 \
  --public-base-url https://studiosaas.cc.cd \
  --expected-app-version 8.0.1 \
  --expected-mode saas

# Clean-commit SaaS + Edition bundles
bash deploy/aws/verify_release_bundles.sh
```

Presenter credentials are intentionally excluded from Git, bundles, docs and
this handoff. Read the protected local file only when presenting.
