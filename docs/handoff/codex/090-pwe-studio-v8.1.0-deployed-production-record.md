# PWE Studio v8.1.0 — Deployed production record

Current version: **8.1.0** (`VERSION`, `backend/server.py` `APP_VERSION`,
`deploy/aws/lightsail.env.example`)
Working branch: `codex/v8.0.1-aws-production`
Baseline: tag `v8.0.0`, commit `abc01ce6e4f281056c3c22fa665e42d7811e0688`
Prior release branch: `codex/v8.0.1-product-home-brand-release`
Post-release corrective branch: `codex/super-admin-tunnel-chain-fix`

**Section order is newest first for §10, then the 2026-07-29/30 record in
§0–§9.** §0 is the production truth and stays the first thing an operator reads
after §10.

## 10. Post-launch P0 fixes and the 8.1.0 version bump (2026-07-31)

Everything below shipped after `pwestudio.online` went live (§0). The version
moved 8.0.1 → **8.1.0** because the release now contains a production
deployment, a customer-visible defect fix and a commercial quota change — not a
patch-level correction.

**Read §7.5 with this section.** §7.5 records the v8.1.0 deploy itself and the
two defects that deploy exposed (an image tag naming the wrong version; the
renamed release-notes URL 404ing). This section records the version bump, the
product fixes it carries and the documentation sweep that made the repository's
prose match the deployed reality. §7.5 is the current runtime truth; §0 is the
2026-07-30 measurement it superseded in part.

### 10.1 Version bump — the four files that define it

| File | Change |
|---|---|
| `VERSION` | `8.0.1` → `8.1.0` |
| `backend/server.py` `APP_VERSION` | `8.0.1` → `8.1.0` (this is what deep health reports) |
| `deploy/aws/lightsail.env.example` | `STUDIOSAAS_VERSION=8.1.0` |
| `README.md` | `Current release: **v8.1.0**` |

Version assertions that had to move with it, all now green:
`backend/tests/test_health.py:14`, `backend/tests/test_tunnel_parity.py:14,25,44`,
`backend/tests/test_product_home_brand.py:57`,
`backend/tests/test_standalone_mode.py:113`.

The customer release-evidence pages were renamed with `git mv`, so history
follows:

```
customer-resources/Release_Notes_v8.0.1.html -> Release_Notes_v8.1.0.html
docs/customer/Release_Notes_v8.0.1.md        -> Release_Notes_v8.1.0.md
```

Seven referencing sites were updated: `product-home.html:393`,
`backend/server.py:991` (the served allow-list), `customer-resources/FAQ.html:127`,
`customer-resources/Privacy_Policy.html:190,191,200`,
`customer-resources/Terms_of_Service.html:44,45,153`,
`backend/frontend/assets/customer-resources.css:5`, `docs/customer/README.md:11`,
plus the three test files above and
`backend/tests/test_customer_resources_brand.py:7,60,225`.

§8.1 below still names the old filename. That is deliberate: it is a historical
statement about what the file was called at the time, not a live pointer.

### 10.2 The registration success card was invisible on seven themes

`tenant-template/index.html:270` (and the six generated tenant workspaces) read:

```css
.result-card{ background:var(--ink); color:#EFE9DD; }
```

`--ink` is the tenant theme's `text_color`. Under a light theme-mode that pairs
a fixed cream on a dark surface — 13.69:1, fine. Under the **seven dark
theme-modes `--ink` is itself the light text colour**, so the same fixed cream
sat on a near-identical surface at **1.06:1**. The 56px `✓` measured 1.21:1 and
the "back to home" control at `:543` had the same fault.

This is the confirmation a parent sees immediately after submitting a
registration — the single highest-consequence surface in the funnel, and it was
blank on nearly half the palettes a studio can choose.

Fix: `color:var(--bg)` against `background:var(--ink)`. That exact pair is the
`('body / page', 'text_color', 'background_color', 4.5)` row of `CHECKS` in
`docs/design/palette_gen.py:221`, so the generator already refuses to emit a
theme where it falls below 4.5:1 — the card can no longer fail silently for any
of the 15 theme-modes, including ones added later.

`tenant-template/index.html:263` — the degraded-content band was a fixed
`#FDF3D5` / `#6b4f00` pair, i.e. a light warm strip pinned across the top of
every dark theme. It now carries `brand-status` with `data-tone="warning"` and
takes the theme's own warning semantic (`brand-system.css:98`).
`:447` dropped a hard-coded `#9d9484` eyebrow for `var(--muted)`.

### 10.3 Every studio's CMS looked the same

Two independent causes, both in `legacy-root/index.html`:

1. `:62` mapped **10 of the 21 theme tokens**. `border_strong_color`, the accent
   hover/pressed states, `focus_ring_color`, the disabled pair and `scrim_color`
   were simply not applied, so a studio that picked one of the eight palettes
   got a CMS that was only partly theirs.
2. `:334` was `body { background:#f1f5f9 !important }` — Tailwind slate-100, a
   cold blue-grey that outranked any tenant theme by `!important`.

Both fixed. The map at `:62` is now the same declarative table the registration
page uses at `tenant-template/register.html:365`, covering all 21 fields, and
the body background is `var(--bg, #f1f5f9)` — the old value survives only as a
fallback until `/brand` answers.

### 10.4 Focus and control boundaries on the product gateway

| Surface | Before | After |
|---|---|---|
| `product-home.html:56` focus ring on light surfaces | Family Amber `#F5B335` on Warm Paper — **1.70:1** | accessible amber `--family-amber-text` — **4.52:1** |
| `product-home.html:62` focus ring on navy sections | — | Family Amber retained — **9.70:1** |
| `product-home.html:171` dark-section form border | `rgba(255,255,255,.28)` → composites to `#576173` — **2.51:1** | `.42` — **3.90:1** |

WCAG 1.4.11 asks 3:1 of a non-text indicator, so the old focus ring failed by a
wide margin on exactly the surface a keyboard user needs it.

### 10.5 What the new test file guards

`backend/tests/test_portal_theme_contract.py` — 12 tests, new:

- no colour declaration on a themed surface may name a literal hex, checked
  across `tenant-template/` and every generated workspace (scrim rules are the
  one documented exception);
- the success card must pair `--ink` with `--bg`, not with a chosen colour;
- **the generator still asserts that pair** — if someone deletes the
  `body / page` row from `palette_gen.py` `CHECKS`, the card's guarantee
  evaporates silently, so the test guards the assumption and not only the code;
- the degraded band must use the theme's warning semantic;
- `portal-theme.css` remains the single place fallback literals may live;
- each of portal, registration and CMS must map **every** theme field, and the
  three must agree field for field;
- the CMS base background must follow the tenant theme;
- the second CMS dark system is asserted to still be *recorded as open*, so the
  known gap cannot quietly fade out of the plan document.

### 10.6 Deliberately NOT done in this round

| Item | Where it is tracked |
|---|---|
| Uptime monitoring, backup-failure alerting, on-call ownership, contractual SLA | §0 "Not yet done"; disclosed on the FAQ and release-evidence pages |
| MFA for privileged accounts | §0; disclosed as an open gap **on a live service** |
| Off-instance copy of database and media backups | §0; backups exist and restore, but live on the same instance |
| Managed AWS services (RDS, S3, SES) | §0 |
| CMS's two dark systems not merged | `docs/design/UI_UX_Upgrade_Plan_2026-07-30.md` **item 29**, `legacy-root/index.html:151-238` |
| 128 `text-gray-400` occurrences below AA (2.31:1 at worst) | same document **item 8**, `legacy-root/src/cms-app.jsx` |
| 8 Tailwind semantic-colour steps not on the semantic scale | same document **item 7** |

Items 7, 8 and 29 are CMS-internal: they affect staff-facing screens, not the
parent- or student-facing surfaces fixed in §10.2.

Migration 0021 **is** applied to production — §9.2 describes it as pending, but
the v8.1.0 deploy in §7.5 carried it in. The instance reports 21 migrations and
`starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`.

## 0. AWS production is LIVE (2026-07-30)

`https://pwestudio.online` serves v8.0.1 from AWS Lightsail. **The Cloudflare
Tunnel is no longer the production path** and must not be reintroduced for this
hostname: the tunnel existed because the runtime had no public IP. With a static
Lightsail IP and Route 53 delegation, a tunnel would add a third-party hop, a
second credential to rotate, and would compete with certbot HTTP-01 for the
same hostname.

| Item | Truth |
|---|---|
| Instance | Lightsail `PWESTUDIO`, Ubuntu 24.04 x86_64, 2 vCPU / 1.9 GB / 58 GB, Sydney Zone A |
| Static IP | `13.237.190.58` |
| DNS | Route 53; `pwestudio.online` and `www.pwestudio.online` both A → the static IP |
| Edge | host nginx terminates TLS; app listens on `127.0.0.1:8899` only; 80 → 443; HSTS `max-age=31536000; includeSubDomains` |
| Certificate | Let's Encrypt, SAN = apex + www, lineage `pwestudio.online`, expires 2026-10-28, `certbot.timer` active |
| Runtime | Compose project `pwestudio`: `studiosaas:8.0.1` (commit `cdd204e`) + `postgres:16-alpine`, both healthy |
| Database | 6 tenants / 15 users / 65 students / 37 registrations / 81 media assets / 4276 audit rows; 20 migrations |
| Least privilege | migrations use the owner role inside entrypoint only; runtime uses `studiosaas_app` |
| Backups | `/etc/cron.d/pwestudio-backup` 03:15 UTC → logical dump + volume tarball; restore rehearsal passes |
| Release layout | `/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.0.1-cdd204e`, `current` symlink, env at `/opt/pwestudio/shared/production.env` (600) |
| Canonical host | `www` 301s to the apex over TLS; one origin, no duplicate content |
| Operator entry | `ssh pwestudio` (see §0.2) and `bash deploy/aws/pwestudio_remote.sh <cmd>` |
| Not yet done | RDS, S3, SES, MFA for privileged accounts, off-box backup copy, uptime monitoring |

**Superseded in part by §7.5.** The version, commit, migration count and release
path in this table are what was measured on 2026-07-30. The v8.1.0 deploy has
since landed: the instance runs `studiosaas:8.1.0`, commit `30da029`+, with 21
migrations applied and the revised plan quotas live. Everything else in this
table — instance, IP, DNS, edge, certificate, least privilege, backups,
canonical host, operator entry and the "not yet done" row — is unchanged and
still current. This section is left as the 2026-07-30 measurement rather than
rewritten, so the two deploys stay separately auditable; §7.5 is the current
runtime truth.

### 0.1 "Not Secure" in Chrome was a client-side cache, not a server fault

Measured from outside on 2026-07-30 after the edge went up:

```
http://pwestudio.online/   -> 301 -> https://pwestudio.online/   (1 redirect)
ssl_verify_result = 0      certificate chain = 4 certs, Verification: OK
homepage absolute http:// references = 0   (CSP is default-src 'self', so
                                            mixed content is structurally
                                            impossible, not merely absent)
```

Chrome had cached the HTTP 200 from before TLS existed and kept loading over
HTTP without re-following the new 301. Visiting `https://` once takes the HSTS
header, after which the browser refuses HTTP for a year. Nothing to fix
server-side. If it recurs on a device: hard-reload, or clear the site's data.

Optional permanent hardening not done: submitting the domain to the HSTS
preload list would make browsers refuse HTTP even before a first visit. It is a
one-way door — the domain must then always serve HTTPS — so it is a decision to
take deliberately, not a side effect of a deployment round.

### 0.2 Operating the instance

Access is an `ssh_config` alias; the key is **not** in the repository or in
iCloud. The private key was moved out of the synced project folder — iCloud
cannot hold mode 600, and a synced private key is a copy you do not control:

```
~/.ssh/pwestudio-lightsail.pem        mode 600   (byte-identical to the
                                                  Lightsail default key)
~/.ssh/config      Host pwestudio -> 13.237.190.58, user ubuntu
```

`deploy/aws/pwestudio_remote.sh` is the laptop-side half. It holds no
credentials and delegates everything that touches production data to
`lightsail_ctl.sh` on the instance, so a laptop is never the source of truth
for a production procedure:

```bash
bash deploy/aws/pwestudio_remote.sh status     # containers + deep health
bash deploy/aws/pwestudio_remote.sh health     # public HTTPS, DNS, cert, redirect
bash deploy/aws/pwestudio_remote.sh backups    # what is on disk, and the cron log
bash deploy/aws/pwestudio_remote.sh backup     # dump + volume tarball, now
bash deploy/aws/pwestudio_remote.sh drill      # rehearse a restore (safe)
bash deploy/aws/pwestudio_remote.sh certs      # expiry + renew timer
bash deploy/aws/pwestudio_remote.sh deploy dist/PWE-StudioSaaS-aws-<ver>.tar.gz
bash deploy/aws/pwestudio_remote.sh ssh
```

`deploy` refuses a `mode=standalone` tarball before uploading it, backs up
first, and **rolls the `current` symlink back automatically if deep health
fails**. Commands that remove a volume, drop a database, or perform a real
restore are deliberately absent — those live on the instance where the operator
reads the confirmation prompt in context.

### 0.3 Edge hardening (2026-07-30, second pass)

- **One shared TLS snippet** (`deploy/aws/nginx/pwestudio-tls.conf`, installed to
  `/etc/nginx/snippets/`) included by both 443 blocks. A hardened apex beside a
  default-configured `www` block is a downgrade path hiding in plain sight.
  TLS 1.2 is limited to forward-secret AEAD suites; no CBC, no RSA key exchange,
  no 3DES. Session cache on, tickets off.
- **OCSP stapling is deliberately OFF.** Every hardening guide says to enable it;
  it is now dead configuration for Let's Encrypt. The certificate's AIA carries
  only `CA Issuers - URI:http://ye1.i.lencr.org/` and no OCSP responder URL, so
  nginx accepts `ssl_stapling on` and then logs `"ssl_stapling" ignored` on
  every reload — a permanent warning that trains an operator to stop reading
  reload output, which is where real errors appear. Re-check after any renewal:
  `openssl s_client ... | openssl x509 -noout -ocsp_uri` should print nothing.
- **No duplicate security headers.** `backend/server.py:777-796` already sends a
  complete CSP, X-Frame-Options, Permissions-Policy, Referrer-Policy and
  X-Content-Type-Options. nginx was repeating two of them. HSTS stays at the
  edge on purpose: it must also cover responses the application never produced,
  and nginx's 502 while the container restarts is exactly when a downgrade must
  not be on offer.
- **Branded maintenance page** for 502/503/504 (`/var/www/pwestudio/__maintenance.html`,
  `internal`, no-store, `Retry-After: 30`). An upgrade restarts the container for
  a few seconds; nginx's stock "502 Bad Gateway" reads like the studio's website
  is broken rather than briefly updating.
- **nginx 1.24 constraint**: HTTP/2 is a `listen` parameter on Ubuntu 24.04. The
  1.25+ `http2 on;` directive fails `nginx -t` — caught by the config test
  before reload, so the live site was never affected.

Nine contract tests in `backend/tests/test_lightsail_deployment.py` hold all of
the above, including that the operator script carries no credentials and cannot
destroy anything.

### Four defects this deployment round found and fixed

All four looked fine from the outside and would have surfaced only during an
incident:

1. **Daily backups had never once succeeded.** `lightsail_ctl.sh` invoked
   `scripts/backup_postgres.py`, but the script is at `backend/scripts/` inside
   the image (WORKDIR `/app`). Nothing read the cron output.
2. **Even with the right path, the dump could not be written.** The bind-mounted
   backup directory was `ubuntu:ubuntu 0755` while the container runs as uid
   10001 → `Permission denied`. Now owner uid 10001, group the operator, mode
   2750, asserted on every run so a human can also list backups without sudo.
3. **The restore rehearsal could never pass.** The image installed an unpinned
   `postgresql-client`, resolving to 17, against a PostgreSQL 16 server; a 17
   `pg_restore` emits `SET transaction_timeout = 0`, a PG17-only GUC, which
   PG16 rejects. The client is now pinned to `postgresql-client-16` from PGDG.
   Dumps produced by the 17 client were deleted — a 16 client cannot read them,
   so keeping them would hand an operator an unusable backup mid-incident.
4. **The media volume was empty.** The database referenced 81 media assets and
   160 derivatives; the volume held only Linux's stock `/media/{cdrom,floppy,usb}`
   from the image layer. Every brand logo returned 404. The 2032-file media tree
   was extracted with uid 10001 ownership, and `backfill_media_variants.py` was
   fixed to verify that a derivative's **file** exists rather than only its row
   — it previously reported "Generated variants: 0" while 126 files were missing.

## 1. Historical delivery boundary (pre-2026-07-30)

v8.0.1 was first shipped as a verified local release and customer-demonstration
package, before the AWS deployment above.

| Area | Truth at the time |
|---|---|
| SaaS runtime | Local Waitress + PostgreSQL behind the controlled `studiosaas-v8-controlled` Cloudflare Tunnel |
| Public product URL | `https://studiosaas.cc.cd` reported v8.0.1 from the same runtime as `http://127.0.0.1:8901` |
| Role entry contract | `/platform-admin` = platform control plane; `/studio-admin` = neutral tenant-admin login; `/cms` = neutral tenant-operations login |
| AWS/RDS/S3/SES | Not purchased or deployed *(Lightsail now deployed; RDS/S3/SES still not)* |
| Production backups/restore/monitoring/SLA | Deferred *(backups + restore rehearsal now live; monitoring/SLA still deferred)* |
| Online payment, provider SMS/email, custom domains | Deferred |
| Multi-campus | One campus = one tenant/subscription; future organisation aggregation is deferred |

Do not describe local testing, a source bundle or Cloudflare invitation access
as production acceptance. Production acceptance is `https://pwestudio.online`
answering deep health with `appVersion=8.0.1`, `mode=saas`, `db=ok` — see §0.

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
  - keep four staff roles on the configured stable local/Pilot password and
    rotate the separate student code on every reset;
  - write credentials to `.runtime/credentials/showcase-credentials.txt` as
    mode `0600`, never to stdout.
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

The post-release tunnel correction was also accepted in the in-app browser
against the public hostname. `/platform-admin` remained on the direct
application login, `/studio-admin` required an explicit slug without browser
storage fallback, `/cms` exposed an explicit tenant selector, and
`/lets-paint-showcase/studio-admin` locked the correct slug. The showcase CMS
rendered the Let's Paint Studio login and no tested page had horizontal
overflow.

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

## 5. Cloudflare operating truth (LOCAL DEVELOPMENT ONLY as of 2026-07-30)

> **The tunnel is no longer the production path.** `https://pwestudio.online`
> serves production from Lightsail with nginx terminating TLS (§0). Everything
> below now describes the *local* runtime and the `studiosaas.cc.cd` demo
> hostname only. Do not point production DNS at a tunnel, and do not treat
> tunnel parity as production acceptance.
>
> Why no tunnel in production: the tunnel existed because the runtime lived on a
> home Mac with no public IP. A Lightsail static IP plus Route 53 removes that
> constraint, so a tunnel would add a third-party hop and a second credential to
> rotate in front of production, for nothing.


`START_STUDIOSAAS_ONLINE.command` now:

- pins `STUDIOSAAS_MODE=saas`;
- defaults the application runtime to port `8901`;
- reads the expected application version from `VERSION`;
- supports an explicit public base domain;
- resolves environment, logs, CMS data, PID files and Tunnel credentials from
  the project-local, Git-ignored `.runtime/` directory;
- never reads `~/.studiosaas`, `~/.cloudflared` or `/private/tmp` for runtime
  files and never resets application passwords during startup;
- uses the explicit project-local Tunnel credential JSON and configured Tunnel
  name instead of selecting an arbitrary credential;
- waits for local and public health;
- runs `backend/scripts/verify_tunnel_parity.py` against deep health;
- refuses to call the tunnel accepted when version, mode, database or release
  identity differs.

Current observation on 2026-07-29:

- local and public deep health agree on
  `appVersion=8.0.1`, `mode=saas`, `db=ok`;
- DNS for `studiosaas.cc.cd` points to the controlled
  `studiosaas-v8-controlled` tunnel, whose ingress targets
  `http://localhost:8901`;
- the public platform-admin API returned all six local tenants;
- `lets-paint-showcase` owner authentication, tenant API and brand workspace
  all returned the exact showcase tenant;
- `/super-admin` remains a Cloudflare Access-protected compatibility alias;
  `/platform-admin` is the direct application-login route;
- the old tunnel was left intact but is no longer the hostname route, preserving
  rollback without allowing two runtimes to answer the same hostname.
- moving a runtime-complete copy to a path containing spaces and starting from
  that new location passed local health, public health and release parity; the
  15-user password-hash fingerprint was unchanged across restart.

The previous split-brain state is therefore resolved. Do not change the DNS
route back to the historical tunnel or start a second connector with a
different ingress for this hostname.

## 6. Packages and release closure

The clean-commit package gate passed for both delivery modes:

```bash
bash deploy/aws/verify_release_bundles.sh
```

Verified outputs:

- `dist/PWE-StudioSaaS-aws-8.0.1.tar.gz`
- `dist/PWE-Studio-Edition-8.0.1.tar.gz`
- matching `.sha256` sidecars.

The SaaS package includes the product gateway, customer resources,
professional showcase workspace/assets and guarded reset. The Edition package
excludes the showcase workspace and reset command while retaining the shared
runtime and customer/operator documentation. Both archives passed SHA-256,
entrypoint, forbidden-content and `BUILD_INFO` checks. The `.sha256` sidecars
generated from the final tagged commit are the authoritative hashes.

## 7. Operator commands

Production commands are in §0.2. The list below is the **local development**
set; running the tunnel parity check against production is meaningless because
production does not use a tunnel.

```bash
