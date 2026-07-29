# PWE Studio v8.0.1 — Release Notes and Acceptance Evidence

Release status: candidate until the repository, package and Git release gates
recorded in `docs/HANDOFF_LATEST.md` are complete. AWS production acceptance
remains explicitly deferred.

## Customer outcomes

- Product homepage aligned to the canonical PWE Navy, Amber and Warm Paper
  brand language, with the retired forest/sage/coral palette removed.
- Sales story aligned to “administration behind the scenes, creativity in
  front,” backed by Let’s Paint Studio and supported by clearer demonstration,
  recommended-plan and setup-fee calls to action.
- Product homepage with role-based entrances, plans, migration downloads and support/feedback actions.
- Isolated professional Let’s Paint Studio showcase tenant with one-click guarded reset.
- Fictional professional records and original synthetic artwork; no customer media.
- Stable switching between Studio Admin website/brand responsibilities and CMS daily operations.
- Customer onboarding checklist, FAQ and migration templates.
- Family/student view connects balance, next class, attendance, portfolio and device-native contact actions.
- Recurring schedule ICS download with Australia/Melbourne wall time and no roster/student data.
- Teacher phone flow reduces today’s work to roster, student search and artwork upload.
- Transparent pricing, service agreement draft, security/compliance disclosure and support policy.
- Industry template and integration boundaries documented as operational behaviour, not colour-only marketing.
- One-campus/one-tenant policy confirmed for v8.0.1.

## Explicitly not delivered

- AWS production hosting, production backup or production SLA;
- privileged MFA/SSO;
- automated messaging provider;
- online payments/accounting integrations;
- custom domains;
- organisation-level multi-campus aggregation.

## Acceptance matrix

| Gate | Required evidence | Status |
|---|---|---|
| Source baseline | v8.0.0 ancestry, clean release branch | Recorded in handoff |
| Unit/backend | full local PostgreSQL verification gate | Complete: 182 pytest + 73 smoke + 216 isolation checks |
| Calendar privacy | ICS structure/timezone and no student data | Complete: 3 browser-downloaded recurring events |
| Demo reset | guard refusal plus successful isolated reset | Complete: two idempotent runs; customer tenant unchanged |
| Frontend build | CMS source compiled to deployed bundle | Complete |
| Responsive UI | 375, 768, 1024 and 1440 px browser checks | Complete: no overflow/page errors/5xx |
| Accessibility | keyboard focus, labels, contrast, reduced motion | Complete for release surfaces |
| Templates | CSV + 5-sheet XLSX, all sheets rendered and inspected | Complete |
| Packages | SaaS + Edition bundle build and content inspection | Pending final clean-commit run |
| Git | v8.0.1 commit, main update, tag and push | Pending final release closure |
| Production | AWS deploy, backup/restore, monitor and public acceptance | Deferred |

## Customer acceptance

Customer representative: `[ ]`
Demonstrated version/hash: `[ ]`
Demonstration date: `[ ]`
Accepted scope: `[ ]`
Open exceptions: `[ ]`
Signature: `[ ]`
