# Customer Onboarding Checklist

This checklist separates platform setup, studio operations and customer acceptance. An owner is assigned to every step; no step silently becomes “done”.

## Phase 0 — Commercial fit

- [ ] Confirm the customer legal entity, ABN, authorised signer and billing contact.
- [ ] Confirm plan, campus/tenant count, user limits and storage allowance.
- [ ] Confirm included implementation work and separately quoted work.
- [ ] Review deferred items: online payments, automated messaging, custom domain and organisation-level multi-campus reporting.
- [ ] Complete and legally review the order form and service agreement.
- [ ] Assign PWE Studio implementation owner and customer owner.

Exit evidence: signed commercial documents and named owners.

## Phase 1 — Data and privacy discovery

- [ ] Record the customer’s source systems and data owner.
- [ ] Confirm authority to supply student/family data and media.
- [ ] Download the PWE Studio CSV/Excel template.
- [ ] Map source fields to Students, Courses and Packages.
- [ ] Identify duplicates, missing IDs, invalid dates, inconsistent balances and ambiguous status values.
- [ ] Agree what will not be imported.
- [ ] Record publication-consent source and evidence separately.
- [ ] Agree migration cut-off, rehearsal, reconciliation and rollback.

Exit evidence: approved mapping report and exceptions list.

## Phase 2 — Tenant and identity

- [ ] Create one tenant per campus.
- [ ] Confirm studio name, timezone, phone, email and address.
- [ ] Add owner account first; use individual staff accounts thereafter.
- [ ] Assign owner, manager, teacher and front-desk roles by least privilege.
- [ ] Confirm staff departure/role-change process.
- [ ] Configure and verify privileged MFA before production.

Exit evidence: tenant identity sheet, role roster and MFA check.

## Phase 3 — Website and brand in Studio Admin

- [ ] Select the closest industry template.
- [ ] Add tenant logo, colours and public contact details.
- [ ] Review bilingual hero, studio story, course language and FAQs.
- [ ] Configure registration questions and privacy notice.
- [ ] Review publication consent wording.
- [ ] Preview desktop and mobile layouts.
- [ ] Publish and verify Website, Quick Registration and CMS links.

Exit evidence: signed website/brand preview.

## Phase 4 — Daily operations in CMS

- [ ] Add courses, packages and opening credit rules.
- [ ] Create realistic recurring schedules and group rosters.
- [ ] Export and open the ICS calendar.
- [ ] Test registration → follow-up → conversion.
- [ ] Test teacher mobile flow: today → check-in → artwork upload.
- [ ] Generate and securely send one student access code.
- [ ] Verify family view: balance, next class, attendance and portfolio.
- [ ] Verify Mail/Messages handoff on a real iPhone/Android device.

Exit evidence: completed end-to-end operational walkthrough.

## Phase 5 — Migration and reconciliation

- [ ] Back up/checkpoint the target.
- [ ] Import the approved rehearsal dataset.
- [ ] Compare counts and sample records by stable external ID.
- [ ] Reconcile opening balances and financial totals.
- [ ] Validate tenant isolation and rejected rows.
- [ ] Obtain customer sign-off.
- [ ] Repeat the controlled process for final cut-over.

Exit evidence: reconciliation report, exception resolution and acceptance.

## Phase 6 — Production readiness

- [ ] AWS account, billing, region and operational owners confirmed.
- [ ] Domain/TLS route agreed.
- [ ] Database and media backup configured.
- [ ] Database and media restore demonstrated.
- [ ] RPO/RTO recorded.
- [ ] Monitoring, alerts and incident contacts assigned.
- [ ] Production health/version/build parity verified.
- [ ] Customer support contacts and escalation process tested.

Exit evidence: production acceptance record. Until this phase passes, the service remains pre-production.
