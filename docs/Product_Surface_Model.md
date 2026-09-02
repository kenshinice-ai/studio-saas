# StudioSaaS Product Surface Model

Status: canonical product-language and responsibility reference.

Current release baseline: v10.13.0 (2026-08-23).

## Product hierarchy

StudioSaaS is one commercial platform with two tenant workspaces and four linked public surfaces. Quick Registration is an alternate acquisition entry, not a separate product.

| Surface | Canonical route | Primary user | Owns | Must not own |
|---|---|---|---|---|
| Super Admin | `/platform-admin` (direct app login); `/super-admin` (Access-protected alias) | StudioSaaS operator | Tenant lifecycle, plans, subscriptions, recurring revenue, usage, risk, support and audit | Routine student operations |
| Studio Admin | `/<slug>/studio-admin` | Tenant owner | Brand, bilingual public copy, portal sections, registration fields, preview, draft, publication and rollback | Students, schedules, attendance, payments or portfolio operations |
| Studio CMS | `/<slug>/cms` | Owner, manager, teacher, front desk | Students, schedules, rosters, attendance, credits, payments/refunds, registration follow-up, portfolio, logs and reporting | Platform billing or public-site design |
| Studio Portal | `/<slug>` | Prospects, families and students | Bilingual studio introduction, courses, work gallery, primary registration CTA and optional student area | Administrative operations |
| Quick Registration | `/<slug>/register` | QR, campaign and direct-link visitors | Focused alternate registration form using the same schema and API as the portal | A second portal or a separate registration database |
| Public Timetable | `/<slug>/timetable` | Prospects and families | Published upcoming classes and optional booking requests | A confirmed seat before CMS review |
| Showcase | `/<slug>/showcase` | Prospects and families | Published studio/student work, categories and plan-bounded pagination | Private, draft, archived or unconsented work |

Root `/register` remains closed. All public registration is tenant scoped.
Root `/studio-admin` is a neutral tenant-admin login requiring an explicit
tenant slug. It does not redirect to `/platform-admin` and does not reuse a
previous tenant from browser storage.
Root `/cms` is the neutral tenant-operations entry. It requires an explicit
tenant slug in SaaS mode and redirects only in Edition mode, where exactly one
active tenant is a startup invariant.

## Canonical end-to-end flows

### Commercial lifecycle

`lead → trial → onboarding → active → past_due → paused → cancelled → archived`

Super Admin owns every commercial transition, plan entitlement and subscription date. Tenant owners can view but cannot change their own plan.

### Brand publication

`Studio Admin draft → preview → publish → public brand API → Portal / Quick Registration / CMS shell`

Drafts are private. Every publication creates a version. Restoring a version creates a draft and requires a deliberate publish action before public pages change.

### Registration conversion

`Portal or Quick Registration → pending lead → CMS contact/trial/follow-up → approve/convert → student record`

Both public entry points use `/v1/public/<slug>/registrations`. Source, language and UTM campaign metadata remain attached to the registration.

### Daily operations

All post-conversion work stays in Studio CMS. Studio Admin may show a read-only operational snapshot and a link to CMS, but it must not contain hidden or duplicate CRUD modules.

## Role baseline

| Role | Platform | Studio Admin | Studio CMS |
|---|---|---|---|
| `super_admin` | Full platform control | Exact-tenant audited support session only | Exact-tenant audited support session only |
| `owner` | None | Full tenant brand/publication control | Full tenant operations |
| `manager` | None | None | Broad CMS operations, exports and team coordination, including refund and share-link authority (`credits:refund` / `portfolio:share`) |
| `teacher` | None | None | Student lookup, schedule read, attendance, portfolio and progress-report authoring; own-pay view only |
| `front_desk` | None | None | Registration/booking review, student records, credits, invoicing/payment intake, scheduling and attendance; no refunds, payroll or publication |
| `staff` | None | None | Assistant role: strict subset of Teacher; roster, attendance, portfolio and read-only progress context |
| `parent` | None | None | No admin UI; public student-area access only |

Manager, teacher, front-desk and assistant permissions are explicit backend bundles. Brand publication remains owner-only; leave/payroll policy requires `scheduling:policy:write` (Owner/Manager), and booking-family details require `class_bookings:review` (Owner/Manager/Front Desk). CMS screens must progressively hide actions that the active bundle cannot perform.

## Release invariants

- Super Admin is the commercial control plane and cannot expose tenant student data without an audited support session.
- Studio Admin cannot change plan, subscription or operational records.
- CMS is the single source of truth for tenant operations.
- Portal registration is the primary conversion path; Quick Registration is an alternate entry.
- Both registration paths share validation, consent, rate limiting, duplicate detection, source tracking and CMS review.
- Public pages consume only published brand data.
- All tenant-owned data is resolved from the server-side tenant context.
