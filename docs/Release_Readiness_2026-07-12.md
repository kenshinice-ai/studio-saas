# StudioSaaS Release Readiness — 2026-07-12

Scope: local/Stage 1 release candidate only. AWS Stage 2 is intentionally excluded.

## Priority acceptance checklist

1. **P0 — Database migration evidence: PASS**
   - PostgreSQL backup created at `backups/postgres/studiosaas_studiosaas_local_test_20260712T045252Z.dump` with a companion manifest.
   - `0012_product_lifecycle_and_brand_versions.sql`, `0013_tenant_role_bundles.sql`, and
     `0014_registration_privacy_consent.sql` are applied to the local acceptance database.
   - A second migration dry run reported: `Database is up to date. Nothing to apply.`

2. **P0 — Tenant isolation and product-loop E2E: PASS**
   - `backend/test_tenant_isolation.py` completed against migrated PostgreSQL: **156 passed, 0 failed**.
   - Evidence covers cross-tenant denial, owner-only brand publication, draft/restore, tenant-owner plan
     immutability, registration source/consent/follow-up, plan limits, media isolation, and role projections.
   - A tenant-scoped legacy `super_admin` is explicitly denied the platform control plane and other tenants;
     only an active `tenant_id IS NULL` membership grants platform administrator authority.

3. **P0 — Product surface ownership: PASS (static/unit)**
   - Super Admin is the tenant lifecycle, plan, subscription, risk, onboarding, MRR, and acquisition cockpit.
   - Studio Admin contains brand/public-page publication only; operational HTML sections are absent.
   - CMS remains the daily student, schedule, attendance, credits, registration, and portfolio workspace.
   - Studio Portal owns the primary bilingual CTA and in-page registration.
   - `/<slug>/register` remains a lightweight alternate Quick Registration route; root `/register` is closed.

4. **P0 — Authorization model: PASS**
   - Owner alone controls brand publication and team mutations.
   - Manager operates the CMS and can view the team.
   - Teacher receives attendance/portfolio data but not registration, package, or financial history.
   - Front Desk receives registration/student/credit workflows but not private portfolio records.
   - API read and write routes enforce explicit permissions; UI navigation mirrors those permissions.

5. **P1 — Brand publication safety: PASS**
   - Save Draft, Publish, version history, and Restore-to-Draft are separate actions.
   - Logo upload creates a draft asset only and cannot bypass explicit Publish.
   - Chinese and English hero, CTA, and registration copy are explicit fields.
   - Tenant owners cannot change commercial plans from Studio Admin.

6. **P1 — Registration and commercial loop: PASS**
   - Portal and alternate registration use the same public registration API and record source/language/UTM.
   - CMS supports contacted, trial booked, waiting, conversion/closure, and next follow-up date.
   - Super Admin shows 30-day acquisition counts and lifecycle/commercial attention states.
   - Student/user limits are enforced server-side from plan entitlements.

7. **P1 — Privacy and notification controls: PASS (code), live SMTP excluded**
   - Registration requires privacy consent in both public entry points and the API stores consent time/version.
   - Public portfolio requires recorded consent; private works are excluded from public APIs.
   - Registration lifecycle notifications use the existing console/SMTP provider and are audit logged.

8. **P1 — Automated verification: PASS**
   - Python compile: pass.
   - Pytest: 65 passed.
   - UI escaping: pass.
   - Inline HTML scripts and compiled CMS JavaScript: pass.
   - `git diff --check`: pass.
   - Production-engine legacy CMS test: 72 passed, 0 failed.
   - Migrated PostgreSQL isolation and product-loop test: 156 passed, 0 failed.
   - The complete `backend/scripts/verify_local.sh` gate passes when run with local service permissions.

9. **P1 — Browser acceptance: PASS**
   - The migrated Waitress service was exercised on port 8899 across Super Admin, Studio Admin, CMS, Portal,
     and Quick Registration using the current rotated administrator credential.
   - Portal language switching, CTA-to-form flow, standalone submission success, consent evidence, stored source
     metadata, and CMS queue visibility were verified. The synthetic registration and audit row were removed.
   - All five surfaces fit a 390×844 viewport without page-level horizontal overflow. No browser errors were
     recorded. The locally hosted Tailwind runtime emits one non-blocking recommendation to precompile CSS.

10. **P2 — Release artifact and source control: READY**
    - Items 1–9 are complete; the candidate is ready for a clean Git commit and release packaging.
    - Build `PWE-StudioSaaS-<version>.tar.gz`, verify SHA-256, and inspect it for credentials/database/media.
    - Push the reviewed branch to `kenshinice-ai/studio-saas`; do not deploy to AWS.

## Current decision

**GO for commit, release packaging, and source push.** Local database, API, authorization, browser, and responsive
acceptance evidence is complete. AWS deployment remains intentionally deferred and is not authorised by this run.
