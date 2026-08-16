# PWE Studio v8.1.1 — Deployed production record

## v8.1.1 release acceptance (2026-08-01)

**Historical truth:** repair commit `282e384` was packaged and deployed to
Lightsail. Internal and public deep health reported `appVersion=8.1.1`,
`db=ok`, `mode=saas`; the public CMS asset matched the local SHA-256. The later
v8.2.0 section above supersedes this release for current work.

### Completed in the v8.1.1 candidate

- **ICS end to end:** canonical revision-bound preview/download, deterministic
  filenames, all-day semantics, 409 refresh/reconfirmation, explicit private
  daily-roster warning, `data:export` enforcement and modal keyboard handling.
  Weekly schedule ICS contains no identities; daily roster ICS may contain
  student names and never guardian names.
- **PIN decision:** removed the reversible Base64/localStorage PIN. It was not
  authentication and had an unsafe mobile recovery path. CMS now relies on the
  server session and provides an explicit server logout.
- **One CMS visual system:** all Tailwind colour families resolve by role to
  the tenant's 21 semantic tokens; OS dark preference is only a pre-brand
  fallback. Once `/brand` resolves, `data-brand-scheme` is the sole theme owner.
- **Golden-ratio core:** shared 61.8/38.2 hierarchy and
  `5/8/13/21/34/55/89` spacing remain canonical. Shared interaction tokens now
  include 44px touch targets, 46px controls, 8px gaps and 8/13/21px radii.
- **CMS/mobile accessibility:** 36/40px target classes removed, primary modals
  trap and restore focus, portfolio thumbnails are keyboard actions, image alt
  text is present, and nested portfolio dialogs no longer compete.
- **Registration:** required identity/contact/privacy fields stay visible;
  optional details, message and publication consent use progressive disclosure.
  Mobile gets a compact header, safe-area sticky submit and touch-sized labels.
- **Deployment rollback:** controller captures and validates the previous
  version before mutation, treats internal/public health separately, restores
  both symlink and version, and fails explicitly if rollback restart or health
  verification fails.
- **Legal/support:** public Support Policy added and linked from Terms/FAQ;
  privacy text now distinguishes weekly schedule and daily roster ICS. Internal
  product/legal consistency review is complete in
  `docs/customer/Legal_Review_2026-08-01.md`; Australian lawyer sign-off and the
  listed commercial particulars remain mandatory before first signature.

### Deliberately deferred

- Main-site acquisition automation: unchanged. Actions continue to open the
  user's own Mail or Messages client; no delivery claim is made.
- Off-instance/local backup copy: deferred by owner decision. Lightsail's daily
  same-instance backup and restore evidence remain; do not call that disaster
  recovery.
- MFA, monitoring, backup-failure alerting, on-call ownership and contractual
  SLA remain disclosed live-service gaps.

### Verification completed so far

```text
Focused legal/UI/deployment suite: 124 passed, 1 skipped
Post-document UI contract suite:   91 passed
Legacy smoke:                      73 passed
Tenant isolation/privacy:          225 passed
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
```

