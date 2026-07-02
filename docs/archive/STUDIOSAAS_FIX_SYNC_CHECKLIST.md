# StudioSaaS Fix and Sync Checklist

Last updated: 2026-07-02

## Executed Fixes

- 2026-07-02 tenant slug CMS routing and brand header repair:
  - Unified `/<tenant_slug>/` and `/<tenant_slug>/cms` so both routes serve the same `legacy-root/index.html` CMS shell for every tenant.
  - Updated the legacy CMS shell slug parser so both `/<tenant_slug>/` and `/<tenant_slug>/cms` resolve the same active tenant slug.
  - Verified `lets-play-piano`, `lets-paint-studio`, and `lets-play-game` return identical HTML for `/<slug>/` and `/<slug>/cms`.
  - Changed the CMS mobile top bar and desktop sidebar header to read logo and studio name from tenant brand data (`logo_url` / `name`) instead of hard-coded `/logo-light.png` and `Studio`.
  - Updated `TENANT_ROUTING_AND_STRUCTURE.md` so the documented route contract matches the backend.
- 2026-07-02 Super Admin password and CMS blank-page repair:
  - Changed local startup to run `backend/scripts/seed_super_admin.py --reset-password`, so `admin@studiosaas.local` is reset to the documented local password `admin123456` whenever `start_studiosaas_local.sh` runs.
  - Added a localhost-only login repair path for `admin@studiosaas.local` / `admin123456`: if the local DB has an old or mismatched password hash, `POST /v1/auth/login` resets that account and restores `super_admin` memberships.
  - Updated Super Admin session handling so a tenant owner session is logged out and sent back to the login panel instead of displaying `Super-admin privileges required` over a partially visible dashboard.
  - Detected a stale Python process still listening on port `8899`. Codex could not stop it because `kill` returned `operation not permitted`; stop it from the normal Terminal or rerun `START_STUDIOSAAS_LOCAL.command` so the local startup script can clear the old server.
  - Fixed `legacy-root/index.html` by defining `tenantSlug` inside the React/Babel script scope. The CMS login/session check no longer depends on a variable hidden inside the earlier bootstrap script, which was the likely cause of the blank `/lets-paint-studio/cms` page.
  - Verified current code returns `200` for `/super-admin`, `/lets-paint-studio/cms`, and `/lets-paint-studio/register` through the Flask test client.
  - Verified shell syntax and Python compilation for `start_studiosaas_local.sh`, `backend/server.py`, `backend/studiosaas/api_v1.py`, `backend/studiosaas/auth.py`, `backend/scripts/seed_super_admin.py`, and `backend/scripts/seed_random_demo_data.py`.
  - Live database login verification could not complete inside Codex because PostgreSQL on `localhost:5432` returned `no response` / `Operation not permitted` from this sandbox. Run `START_STUDIOSAAS_LOCAL.command` in the normal Terminal to perform the actual password reset and server start.
- 2026-07-02 Studio Admin credential sync:
  - Added per-tenant Studio Admin login management to Super Admin tenant create/edit flows.
  - Added backend synchronization from tenant payload to `users` and `memberships` with `owner` role.
  - Stored `studio_admin_user_id`, `studio_admin_email`, and `studio_admin_name` in `tenants.settings`.
  - Added default demo owner logins in `backend/scripts/seed_random_demo_data.py`.
  - Added Studio Admin login, logout, and change-password UI.
  - Updated `/<tenant_slug>/studio-admin` to serve the shared Studio Admin page and auto-fill the tenant slug from the URL.
  - Changed Studio Admin data calls to tenant-scoped `/s/<tenant_slug>/v1/...` routes where tenant membership is enforced.
  - Changed Studio CMS login to use the same Studio Admin email and password through `/s/<tenant_slug>/v1/auth/legacy-login`.
  - Changed Studio CMS password update to use `/v1/auth/change-password`.
  - Added `STUDIO_ADMIN_CREDENTIALS_AND_LOGIN.md`.
- 2026-07-02 Super Admin login repair:
  - Added a visible Super Admin login panel to `super-admin.html`.
  - Added session check, logout, and Change Password controls to the Super Admin header.
  - Updated Super Admin API calls to send cookies with `credentials: 'include'`.
  - Added `POST /v1/auth/change-password` for the v1 role-based auth flow.
  - Updated `backend/scripts/seed_super_admin.py` so it can run from the repo root, ensures `super_admin` membership for all tenants, and supports explicit `--reset-password`.
  - Updated `start_studiosaas_local.sh` to ensure the local Super Admin login exists after demo data seeding.
  - Added `SUPER_ADMIN_LOGIN_AND_PASSWORD.md` with browser login, API login, password change, logout, and password reset instructions.
- 2026-07-01 industry preset system:
  - Added tenant industry presets for `art`, `music`, `math`, `dance`, `language`, `sports`, `game`, and `general`.
  - Stored industry-specific configuration in `tenants.settings`: `category`, `category_label`, `slogan`, `registration_profile`, and `copy_pack`.
  - Extended `GET /v1/tenant`, `PATCH /v1/tenant`, `GET /v1/tenant/brand`, and `GET /v1/public/<tenant_slug>/brand` so branding and industry copy come from the same tenant contract.
  - Added Super Admin category and slogan controls for creating/editing tenants.
  - Added Studio Admin category, slogan, portal label, register intro, and registration preference field controls so tenants can adjust industry-specific wording themselves.
  - Replaced hard-coded Register `Art Preferences` with tenant-configurable registration fields.
  - Replaced legacy CMS new-student, edit-student, and pending-registration preference panels with the same tenant-configurable registration profile while preserving legacy preference keys for old data.
  - Replaced hard-coded Register slogan with tenant brand slogan.
  - Updated legacy CMS login surfaces and growth-report output to use tenant slogan/studio name.
  - Refreshed existing tenant wrappers from `tenant-template/` so CMS/Register wrappers display tenant slogan.
  - Updated local import/random seed scripts so rebuilt demo tenants receive industry presets.
- 2026-07-01 priority repair pass:
  - Fixed invalid escaped template literals in `backend/frontend/studio-admin.html` that stopped the Studio Admin script from parsing and left the page stuck loading.
  - Moved auth error-handler initialization before Flask blueprint registration so a fresh server process can import/start without the "blueprint already registered" assertion.
  - Added a default credit-account helper and schema index for `credit_accounts.course_id IS NULL` so tenant-wide balances do not create duplicate default accounts.
  - Restricted default balance reads to `course_id IS NULL` in student lists, student detail, dashboard low-balance count, public balance query, and legacy CMS data generation.
  - Fixed PostgreSQL dict-row `RETURNING id` reads in student creation, credit transaction creation, and portfolio item creation.
  - Updated student balance/credit-hours edits so the default credit account is updated when Studio Admin changes those fields.
  - Fixed `backend/test_tenant_isolation.py` so HTTP error bodies are read once, JSON parse failures are explicit, and default tenant slugs match the local demo tenants.
  - Added `.gitignore` rules for local repair backups so `.bak`, `.bak.*`, and `.backup` files do not pollute future status checks.
- Kept `backend/` as the canonical runtime structure and preserved `legacy-root/` as the active bridge for the old CMS/Register shells.
- Unified Studio Admin settings writes through `PATCH /v1/tenant`; the legacy `/v1/tenant/settings` endpoint now delegates to the same path.
- Added CMS/Register presentation fields: `cms_layout` and `show_welcome`.
- Added public brand output for `cms_layout` and `show_welcome` so wrappers can render Studio Admin changes.
- Added welcome message display to tenant CMS and Register wrappers.
- Refreshed existing tenant folders from the updated templates:
  - `tenants/lets-paint-studio/`
  - `tenants/lets-play-piano/`
  - `tenants/lets-play-game/`
- Added logo upload size and file-signature validation before saving uploaded files.
- Removed duplicate base registration for `/v1/tenant/logo`; the decorated route remains active.
- Added Studio Admin controls for CMS layout and welcome visibility.
- Added Studio Admin color contrast warning before saving low-readability themes.
- Improved Studio Admin and Super Admin mobile layout so tables scroll inside their own containers instead of stretching the full page.
- Added local vendor placeholder files under `backend/vendor/` to stop missing-file errors while preserving CDN fallback behavior.
- Updated legacy CMS/Register bridge pages to set document titles from tenant brand data when available.
- Updated the legacy CMS registration link card to copy `/<tenant_slug>/register` from the active tenant context instead of hard-coding `/register`.
- Added tenant brand application inside the legacy CMS iframe so Studio Admin logo and theme color changes also affect old CMS content, not only the outer wrapper.
- Added tenant brand application inside the legacy Register iframe so its header, footer, logo, tabs, buttons, and indigo/purple accents follow public brand data.
- Changed tenant Register wrappers to resize the legacy register iframe to its content height, avoiding the desktop view where only the iframe header/top tabs were visible.
- Fixed tenant template JavaScript fallback names so studio names containing apostrophes, such as `Let's Paint Studio`, no longer break generated CMS/Register wrapper scripts.

## Current Verification Targets

- `backend/test_cms.py` should pass without regressions.
- `PATCH /v1/tenant` should update direct tenant fields and JSON presentation settings together.
- `GET /v1/public/<tenant_slug>/brand` should include:
  - `logo_url`
  - `cms_layout`
  - `show_welcome`
  - `category`
  - `slogan`
  - `registration_profile`
  - `copy_pack`
  - `welcome_message`
  - public contact fields
- `/<tenant_slug>` and `/<tenant_slug>/register` should render tenant logo, contact strip, slogan, welcome message, industry-specific registration fields, and layout from public brand data.
- `/v1/tenant/logo` should reject fake image uploads even when the filename extension is allowed.

## Verification Completed

- 2026-07-02 Studio Admin credential sync verification:
  - Python compile checks passed for backend server, v1 API, auth module, and scripts.
  - Plain JavaScript syntax checks passed for Super Admin and Studio Admin pages.
  - Lightweight Flask checks confirmed protected routes still reject unauthenticated requests and page routes render:
    - `POST /v1/admin/tenants` without login -> `401`
    - `POST /v1/auth/change-password` without login -> `401`
    - `GET /studio-admin` -> `200`
    - `GET /lets-paint-studio/studio-admin` -> `200`
    - `GET /lets-paint-studio/cms` -> `200`
  - Tenant payload normalization confirmed `studioAdminEmail`, `studioAdminName`, and `studioAdminPassword` are accepted and normalized.
  - Live DB seed/login verification could not run inside the Codex sandbox because local PostgreSQL connections to `localhost:5432` were denied with `Operation not permitted`.
- 2026-07-02 Super Admin login verification:
  - Local startup now runs `scripts/seed_super_admin.py --reset-password`, so `admin@studiosaas.local` always returns to the documented local password `admin123456` after restart.
  - Fixed CMS blank page risk in `legacy-root/index.html` by defining `tenantSlug` inside the React/Babel scope instead of relying on a variable from the earlier bootstrap script.
  - Shell syntax and Python compile checks passed for the startup script, backend API, server, and scripts.
  - Super Admin inline JavaScript syntax check passed.
  - Flask route map contains one registered route each for `/v1/auth/login`, `/v1/auth/logout`, `/v1/auth/me`, and `/v1/auth/change-password`.
  - Lightweight Flask checks returned expected unauthenticated responses:
    - `POST /v1/auth/login` with missing fields -> `400`
    - `POST /v1/auth/change-password` without login -> `401`
    - `GET /v1/auth/me` without login -> `401`
    - `GET /super-admin` -> `200`
  - Live database seed/login verification could not run inside the current Codex sandbox because local PostgreSQL connections to `localhost:5432` were denied with `Operation not permitted`; the user's Terminal environment showed PostgreSQL accepting connections, so the startup script should run the seed there.
- 2026-07-01 industry preset verification:
  - Python syntax check passed for backend API, scripts, and tests.
  - Plain JavaScript syntax checks passed for Studio Admin, Super Admin, legacy Register, tenant templates, and generated tenant CMS/Register wrappers.
  - Flask test-client checks against current code returned:
    - `PATCH /s/lets-paint-studio/v1/tenant` without login -> `401`
    - `GET /studio-admin` -> `200`
    - `GET /lets-paint-studio/cms` -> `200`
    - `GET /lets-paint-studio/register` -> `200`
    - `GET /register` -> `404`
  - Follow-up scan found no remaining hard-coded `Art Preferences`, `艺术偏好`, `喜欢的画风`, `喜欢的画家`, or `绘画经验` labels in the active CMS/Register surfaces.
  - A public brand read using `localhost:5432` could not complete in this sandbox because local PostgreSQL connections were denied with `Operation not permitted`; this is an environment permission block, not an HTTP route failure.
- 2026-07-01 priority repair verification:
  - Python syntax check passed for `backend/server.py`, `backend/studiosaas/*.py`, `backend/scripts/*.py`, `backend/test_cms.py`, and `backend/test_tenant_isolation.py`.
  - Studio Admin inline script check passed with `node --check` after removing invalid escaped template literals.
  - Residual scan found no remaining `fetchone()[0]`, escaped template literal fragments, or `old_credit` dead variable in the repaired core files.
  - Flask test-client checks against current code returned:
    - `PATCH /s/lets-paint-studio/v1/tenant` without login -> `401`
    - `POST /s/lets-paint-studio/v1/students` without login -> `401`
    - `GET /studio-admin` -> `200`
    - `GET /lets-paint-studio/register` -> `200`
    - `GET /register` -> `404`
  - Full `backend/test_cms.py` could not complete in this sandbox because binding a temporary local server was denied with `Operation not permitted`.
  - Live `backend/test_tenant_isolation.py` still targets the already-running old 8899 process until that process is restarted with the repaired code.
- Python syntax check passed for `backend/server.py`, `backend/studiosaas/*.py`, and `backend/scripts/*.py`.
- Legacy smoke test passed: 73 checks passing, 0 failing.
- Targeted Studio Admin sync check passed:
  - `PATCH /v1/tenant`
  - compatibility `PATCH /v1/tenant/settings`
  - `GET /v1/public/lets-paint-studio/brand`
  - fake logo upload rejection
  - local vendor resource status checks
- Page resource checks passed for:
  - `/`
  - `/studio-admin`
  - `/lets-paint-studio/studio-admin`
  - `/lets-paint-studio`
  - `/lets-paint-studio/register`
- Static page output checks confirmed the new Studio Admin controls, contrast warning, responsive grid class, tenant welcome containers, and layout classes are present.
- Follow-up sync checks passed for the reported issues:
  - legacy CMS registration link now uses the active tenant slug URL.
  - legacy CMS and legacy Register include the tenant brand applier.
  - tenant Register wrappers include the iframe content-height resizer.
  - Studio Admin-style logo/color patch reads back through `/v1/public/lets-paint-studio/brand`.
- Follow-up page-open fix completed:
  - regenerated tenant CMS/Register wrappers from the safe template.
  - inline plain JavaScript syntax checks pass for Studio Admin, legacy Register, tenant templates, and all generated tenant CMS/Register wrappers.
  - the generated `lets-paint-studio` pages no longer contain broken JS string fallbacks from apostrophes in the studio name.
- Real Chrome screenshot/layout automation could not complete in the current sandbox because the system Chrome process was blocked during headless automation. Keep this as the next manual or browser-enabled verification step.

## Remaining Improvements

1. Replace `backend/vendor/*.js` placeholders with real pinned vendor bundles for fully offline operation.
2. Add automated browser tests for mobile overflow on Super Admin, Studio Admin, CMS wrapper, and Register wrapper.
3. Add an API contract test that patches Studio Admin settings and immediately reads `/v1/public/<slug>/brand`.
4. Add a migration/backfill step for existing tenants that lack `cms_layout`, `show_welcome`, `category`, `slogan`, `registration_profile`, or `copy_pack` in `tenants.settings`.
5. Add server-side color contrast validation if tenant branding becomes externally writable beyond Studio Admin.
6. Add upload cleanup for replaced tenant logos so old public assets do not accumulate indefinitely.

## Core Files To Recheck After Future Changes

- `backend/studiosaas/api_v1.py`
- `backend/frontend/studio-admin.html`
- `super-admin.html`
- `tenant-template/index.html`
- `tenant-template/register.html`
- `legacy-root/index.html`
- `legacy-root/register.html`
- `TENANT_ROUTING_AND_STRUCTURE.md`
