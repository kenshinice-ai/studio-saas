# StudioSaaS Product Blueprint v2

Version: v2.0
Date: 2026-07-02
Purpose: Single source of truth for product vision, positioning, user roles, business model, and market strategy.

---

## 1. Product Overview

**Product Name:** StudioSaaS

**Positioning:** A cloud-based management system for small creative education studios, supporting student management, course/clock-hour tracking, portfolio display, parent registration, brand customization, and multi-device access.

**One-line Description:**

> StudioSaaS helps small creative education studios run daily operations, convert registrations, publish bilingual studio websites, and give families lightweight self-service access.

**Origin:** This product is a multi-tenant SaaS refactor of the existing Let's Paint CMS, which was built from real studio usage. The product logic is grounded in actual operational needs, not hypothetical assumptions.

**Commercial Model:** Semi-service SaaS = one-time setup fee (AUD 299–999) + monthly subscription.

---

## 2. Target Market

### 2.1 Primary Customers

1. Children's art studios
2. Small music/dance/language training centers
3. Clay, craft, photography creative course studios
4. Private tutors or small course brands

### 2.2 Customer Profile (MVP)

| Dimension | Range |
|---|---|
| Admins/teachers | 1–5 |
| Students | 20–500 |
| Locations | 1–3 |
| Monthly image uploads | Hundreds |

**Out of scope for MVP:** Large chain institutions, complex scheduling, full accounting, automatic online payments, App Store native apps, multi-campus enterprise permissions.

### 2.3 Buyer Personas

| Role | Needs | Concerns |
|---|---|---|
| Studio owner | Manage students, courses, clock hours, revenue | Simple, stable, fair pricing |
| Teacher | Quick student lookup, upload works, record classes | Mobile/iPad usability |
| Front desk/admin | Registration, clock hours, contact parents | Clear data, fewer errors |
| Parent | View works, balance, course info | Convenient, reassuring, professional |

---

## 3. Product Portals

### 3.1 Super Admin (Platform Operator)

For the StudioSaaS owner/operator. Manages:
- Tenant accounts (create, pause, resume, delete)
- Subscription plans and status
- Billing periods and limits
- Usage statistics (storage, student count, user count)
- System audit logs
- Global configuration

**Limitation:** Super Admin does not directly view client-sensitive student data unless entering support mode (logged in audit trail).

### 3.2 Studio Admin (Studio Owner/Manager)

For each studio owner. Manages the public experience only:
- Brand identity, logo, colours and contact details
- Bilingual Studio Portal copy and section visibility
- Registration questions and public consent copy
- Private drafts, preview, publication versions and rollback
- Links to the public website, Quick Registration and Studio CMS

Daily operations do not live in Studio Admin. Students, schedules, attendance, credits, payments/refunds, registration follow-up and portfolio work belong to Studio CMS.

### 3.3 Studio Portal and Student Area (Public)

The Studio Portal is the tenant's bilingual public website and primary acquisition path:
- Studio introduction, courses, teaching team, work gallery, FAQ and contact
- Primary in-page registration CTA
- Optional Student Area for balance and portfolio lookup
- Shared portfolio view via token

`/<slug>/register` is Quick Registration: an alternate focused form for campaigns, QR codes and direct links. It is not a second portal.

---

## 4. Page Wireframes

### 4.1 Super Admin

```
┌──────────────────────────────────────────────────────────┐
│ StudioSaaS Super Admin                                   │
├──────────────┬───────────────────────────────────────────┤
│ Workspaces   │ [Create Studio]                           │
│ Plans        │                                           │
│ Billing      │ Studio Name | Status | Plan | Students    │
│ Usage        │ Let's Paint | active | Studio | 143        │
│ Audit Logs   │ Clay Lab    | trial  | Starter| 38         │
└──────────────┴───────────────────────────────────────────┘
```

Core actions: Create studio, pause/resume tenant, view plans, view usage, view audit logs.

### 4.2 Studio Admin

```
┌──────────────────────────────────────────────────────────┐
│ StudioSaaS / Current Studio                              │
├──────────────┬───────────────────────────────────────────┤
│ Brand        │ Logo | colours | identity | contact         │
│ Website      │ Hero | sections | bilingual copy | FAQ      │
│ Registration │ Questions | consent | Quick Register        │
│ Preview      │ Desktop | mobile | portal | registration     │
│ Publish      │ Draft | publish | versions | restore         │
│ CMS Handoff  │ Read-only snapshot | Open Studio CMS        │
└──────────────┴───────────────────────────────────────────┘
```

Core actions: Save a private draft, preview the public experience, publish a version, restore a previous version, and open Studio CMS for operations.

### 4.3 Studio Portal

- Studio public homepage (branded)
- Primary in-page registration
- Optional Student Area for balance and portfolio lookup
- Quick Registration alternate route (`/<slug>/register`)
- Shared portfolio (token-based)

---

## 5. Database Schema Overview

Database: PostgreSQL with multi-tenant `tenant_id` isolation.

All business data must include `tenant_id`. All business queries must bind tenant context. Delete strategy: soft delete or deactivate by default, no un-audited hard deletes.

### Core Tables

| Table | Purpose |
|---|---|
| `tenants` | Studio tenant, slug, status, brand config |
| `plans` | Plan definitions (starter, studio, growth) |
| `subscriptions` | Tenant subscription status |
| `users` | Platform users |
| `memberships` | User-tenant-role relationships |
| `students` | Student profiles |
| `courses` | Course definitions |
| `packages` | Course package definitions |
| `credit_accounts` | Student balance accounts |
| `credit_transactions` | Purchase, consume, adjust, refund logs |
| `attendance_sessions` | Class/check-in records |
| `registrations` | Public registration applications |
| `media_assets` | Uploaded file metadata |
| `portfolio_items` | Student portfolio entries |
| `share_tokens` | Parent portal security tokens |
| `email_templates` | Per-tenant email templates |
| `notification_logs` | Email/notification send records |
| `audit_logs` | Key operation audit trail |
| `tenant_usage` | Storage, student count, user count stats |

Full schema: `backend/db/schema_v1.sql`

---

## 6. Pricing Plans

| Plan | Monthly Fee | Limits | Suitable For |
|---|---:|---|---|
| Starter | AUD 49 | 100 students, 2 users, 5GB storage | Solo teacher or startup studio |
| Studio | AUD 99 | 500 students, 8 users, 30GB storage | MVP flagship studio |
| Growth | AUD 199 | 1500 students, 20 users, 100GB storage | Multi-location or growing studio |

Optional one-time setup fee: AUD 299–799 (brand setup, data migration, training).

---

## 7. Pilot Interview List

1. **Scribble Cat Studios** — Multi-location, small team, course registration, children/teen art management.
2. **Fizz Kidz** — Multi-location children's creative activities, holiday programs, birthday parties.
3. **Victorian Artists Society Art School** — Adult/teen courses, membership, art works, course management.

Interview focus:
- How they currently manage student profiles, clock-hour balances, and artwork images.
- What parents ask most frequently.
- What actions teachers need most on mobile/iPad.
- Willingness to pay monthly fee + setup fee.
- Acceptance of data migration, privacy, photo storage, and branding pages.

---

## 8. MVP Acceptance Criteria

MVP is considered complete when:

1. At least 3 independent studios can be created.
2. Each studio can upload its own logo and configure course units.
3. Each studio can manage its own students.
4. Each student can record clock-hour balances and transaction history.
5. Each studio can upload student artwork.
6. Parents can register through public tenant pages.
7. Parents can only view their own child's data.
8. Platform admin can view studio status.
9. Database has automated backup.
10. Key operations have audit logs.
11. All APIs enforce tenant isolation.
12. System can deploy to cloud and run stably.

---

## 9. Strategic Recommendations

```
Do not simply copy and sell the existing CMS.
Do not build a full iOS App as the first step.

Build a Web SaaS multi-tenant platform first,
keep portfolio and clock-hour management as the core differentiator.
After the Web SaaS stabilizes, build a teacher-side iOS App.
```

**Commercialization path:** Semi-service SaaS = setup fee + monthly subscription = easier early sales and better customer onboarding.

**Product boundary:** Allow logo, colors, courses, fields, copy configuration. Do not write custom code per customer.

This makes the system sellable, maintainable, and scalable.

---

## 10. Target Architecture Reference

A v2 architecture overview (2026-07) defines the long-term technical north star: layered portals (CMS / Register / Parent / Teacher / Studio Admin / Super Admin), service modules (Auth, Tenant, User, Student, Course, Package, Attendance, Payment, Credit, Portfolio, CRM, Notification, Report, AI, File), shared infrastructure (Redis, S3, message queue, scheduler), and an extended data layer (read replicas, Elasticsearch, ClickHouse).

Canonical Mermaid rendition and the phase-by-phase adoption policy: `docs/Architecture.md` §7. Summary of the policy:

- **Now (pilot):** Flask modular monolith organised along the target module boundaries; local PostgreSQL; local media with S3-ready schema.
- **Phase 3:** Docker/Nginx/CI, S3 media, payment and notification services.
- **Phase 5:** heavy data infrastructure (Redis, replicas, search, analytics) — only if pilot scale demands it.

The poster's simplified ER diagram is illustrative; `backend/db/schema_v1.sql` remains the schema source of truth.
