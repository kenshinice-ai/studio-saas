# StudioSaaS Product Surface Model

Status: canonical product-language and responsibility reference.

## Product hierarchy

StudioSaaS is one commercial platform with two tenant workspaces and one public acquisition experience. The standalone registration page is an alternate entry, not a separate product.

| Surface | Canonical route | Primary user | Owns | Must not own |
|---|---|---|---|---|
| Super Admin | `/super-admin` | StudioSaaS operator | Tenant lifecycle, plans, subscriptions, recurring revenue, usage, risk, support and audit | Routine student operations |
| Studio Admin | `/<slug>/studio-admin` | Tenant owner | Brand, bilingual public copy, portal sections, registration fields, preview, draft, publication and rollback | Students, schedules, attendance, payments or portfolio operations |
| Studio CMS | `/<slug>/cms` | Owner, manager, teacher, front desk | Students, schedules, rosters, attendance, credits, payments/refunds, registration follow-up, portfolio, logs and reporting | Platform billing or public-site design |
| Studio Portal | `/<slug>` | Prospects, families and students | Bilingual studio introduction, courses, work gallery, primary registration CTA and optional student area | Administrative operations |
| Quick Registration | `/<slug>/register` | QR, campaign and direct-link visitors | Focused alternate registration form using the same schema and API as the portal | A second portal or a separate registration database |

Root `/register` remains closed. All public registration is tenant scoped.

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
| `super_admin` | Full platform control | Audited support access | Audited support access |
| `owner` | None | Full tenant brand/publication control | Full tenant operations |
| `manager` | None | None | Broad CMS operations, exports and team coordination |
| `teacher` | None | None | Student lookup, attendance and portfolio work |
| `front_desk` | None | None | Registration follow-up, student records and credits |
| `staff` | None | None | Legacy general staff bundle retained for compatibility |
| `parent` | None | None | No admin UI; public student-area access only |

Manager, teacher and front-desk permissions are explicit backend bundles. Brand publication remains owner-only; CMS screens must progressively hide actions that the active bundle cannot perform.

## Release invariants

- Super Admin is the commercial control plane and cannot expose tenant student data without an audited support session.
- Studio Admin cannot change plan, subscription or operational records.
- CMS is the single source of truth for tenant operations.
- Portal registration is the primary conversion path; Quick Registration is an alternate entry.
- Both registration paths share validation, consent, rate limiting, duplicate detection, source tracking and CMS review.
- Public pages consume only published brand data.
- All tenant-owned data is resolved from the server-side tenant context.
