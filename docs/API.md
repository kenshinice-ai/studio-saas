# StudioSaaS API Reference

Version: v3.3
Date: 2026-07-18
Purpose: Complete API endpoint reference, authentication model, tenant resolution, and public endpoints.

---

## 1. API Overview

- **Base URL (local):** `http://localhost:8899`
- **API prefix:** `/v1`
- **Tenant-scoped prefix:** `/s/<tenant_slug>/v1`
- **Auth:** Session cookies (Flask) with `credentials: 'include'`
- **CSRF:** cookie-authenticated **mutations** on `/v1/*` must send `X-Requested-With: StudioSaaS` (missing header → 403). Pages get this automatically via `/assets/ui-common.js`; curl examples with cookies need `-H 'X-Requested-With: StudioSaaS'`. Sessionless/public calls are exempt.
- **Format:** JSON

### 1.1 Tenant Resolution Order

1. Path: `/s/{tenant_slug}/...`
2. Header: `X-Tenant-Slug`
3. Subdomain: `{tenant_slug}.localhost:8899` (future)

**Rule:** If no tenant context is resolved, tenant-scoped endpoints return a clear error. Silent fallback to a default tenant is prohibited.

---

## 2. Health

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/health` | None | System health check |
| GET | `/v1/industry-presets` | None | Shared eight-industry copy, bilingual registration, and visual-theme presets |

```bash
curl -sS http://localhost:8899/v1/health
```

---

## 3. Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/v1/auth/login` | None | Login (returns session cookie) |
| GET | `/v1/auth/me` | Session | Current user + memberships |
| POST | `/v1/auth/logout` | Session | End session |
| POST | `/v1/auth/change-password` | Session | Change current password |

### 3.1 Login

```bash
curl -i -c /tmp/studiosaas.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/v1/auth/login \
  -d "{\"email\":\"admin@studiosaas.local\",\"password\":\"$SUPER_ADMIN_PASSWORD\"}"
```

Response:

```json
{"ok": true, "userId": "...", "name": "...", "token": "..."}
```

Password hashes are stored with PBKDF2-HMAC-SHA256. Legacy unsalted SHA-256
user hashes are accepted only on successful login and are upgraded immediately.

### 3.2 Legacy CMS Login (per tenant)

```bash
curl -i -c /tmp/studio.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/s/lets-paint-studio/v1/auth/legacy-login \
  -d "{\"email\":\"owner@lets-paint-studio.test\",\"password\":\"$STUDIO_ADMIN_PASSWORD\"}"
```

Verifies the user has an active operational membership (`owner`, `manager`,
`teacher`, `front_desk`, `staff`) or is the platform `super_admin`.

### 3.3 Change Password

```bash
curl -i -b /tmp/studiosaas.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/v1/auth/change-password \
  -d '{"oldPassword":"current-generated-password","newPassword":"new-generated-password"}'
```

Rules: Minimum 8 characters, different from old password, requires active session.

---

## 4. Tenant Management

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/tenant` | Tenant admin | Get current tenant |
| PATCH | `/v1/tenant` | Owner / Super admin | Publish tenant brand settings and create a version |
| GET | `/v1/tenant/brand` | Session | Get published tenant brand payload |
| GET | `/v1/tenant/brand-workspace` | Owner / Super admin | Get draft and publication history |
| PUT | `/v1/tenant/brand-draft` | Owner / Super admin | Save an unpublished brand draft |
| POST | `/v1/tenant/brand-versions/{version_id}/restore` | Owner / Super admin | Restore a publication into the draft |
| POST | `/v1/tenant/logo` | Owner / Super admin | Upload a draft logo asset without publishing it |
| POST | `/s/{tenant_slug}/v1/media/upload` | Tenant admin | Canonical tenant media upload |

### 4.1 Tenant Settings (via PATCH)

```json
{
  "name": "Studio Name",
  "primary_color": "#ff6600",
  "secondary_color": "#333333",
  "welcome_message": "Welcome to our studio",
  "cms_layout": "hero",
  "show_welcome": true,
  "category": "art",
  "slogan": "Creative learning for kids",
  "registration_profile": {...},
  "copy_pack": {...},
  "contact_phone": "0412 345 678",
  "contact_email": "hello@studio.test",
  "address": "123 Main St, Melbourne"
}
```

Compatibility alias: `PATCH /v1/tenant/settings` writes through the same path as `PATCH /v1/tenant`.

### 4.2 Tenant Team

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/s/{tenant_slug}/v1/team` | Owner / Manager / Super admin | List operational members |
| POST | `/s/{tenant_slug}/v1/team` | Owner / Super admin | Create a new tenant-only operational account |
| PATCH | `/s/{tenant_slug}/v1/team/{membership_id}` | Owner / Super admin | Change role or enable/disable membership |

Team creation enforces the plan `user_limit`. Tenant team management cannot
overwrite an existing global account or add cross-tenant access. Reactivating a
disabled member rechecks the same limit.

Role boundary: Manager handles broad daily operations; Teacher handles attendance
and portfolio; Front Desk handles registrations, students, and credits. Brand
publication remains Owner-only. Sensitive read routes use the same permission
matrix, and the aggregate CMS payload is projected by role.

---

## 5. Super Admin Routes

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/admin/tenants` | Super admin | List all tenants |
| POST | `/v1/admin/tenants` | Super admin | Create tenant |
| PATCH | `/v1/admin/tenants/{tenant_id}` | Super admin | Update tenant |
| PATCH | `/v1/admin/tenants/{tenant_id}/status` | Super admin | Perform a validated tenant/subscription lifecycle transition |
| GET | `/v1/admin/usage` | Super admin | View usage stats |
| GET | `/v1/admin/audit-logs` | Super admin | View audit trail |
| GET | `/v1/plans` | Super admin | List plans |
| POST/PATCH/DELETE | `/v1/plans` | Super admin | Manage plans |

### 5.1 Create Tenant Payload

```json
{
  "name": "New Studio",
  "slug": "new-studio",
  "plan_code": "studio",
  "status": "active",
  "billing_period": "monthly",
  "subscription_start": "2026-07-01",
  "subscription_end": "2026-08-01",
  "studioAdminEmail": "owner@new-studio.test",
  "studioAdminName": "Studio Owner",
  "studioAdminPassword": "generated-password-from-secure-channel"
}
```

Creates `tenants`, `subscriptions`, `tenant_usage` rows and generates `tenants/<slug>/` workspace.

---

## 6. Student Management

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/students` | Tenant admin | List students |
| POST | `/v1/students` | Tenant admin | Create student |
| GET | `/v1/students/{student_id}` | Tenant admin | Student detail |
| PATCH | `/v1/students/{student_id}` | Tenant admin | Update student |
| POST | `/v1/students/{student_id}/archive` | Tenant admin | Archive student |
| POST/DELETE | `/v1/students/{student_id}/access-code` | `students:write` | Issue once or revoke a hashed 6-digit private-portal access code |
| PUT/DELETE | `/v1/students/{student_id}/publication-consent` | `portfolio:write` | Append a publication confirmation or withdrawal event |

---

## 7. Courses and Packages

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/courses` | Tenant admin | List courses |
| POST | `/v1/courses` | Tenant admin | Create course |
| GET | `/v1/packages` | Tenant admin | List packages |
| POST | `/v1/packages` | Tenant admin | Create package |

---

## 8. Credits And Attendance

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/students/{student_id}/credits` | Tenant admin | Student balance |
| POST | `/v1/students/{student_id}/credit-transactions` | Tenant admin | Record transaction |
| GET | `/v1/attendance?date=YYYY-MM-DD` | Tenant admin | List attendance sessions |
| POST | `/v1/attendance/check-in` | Tenant admin | Check in one student and consume credits |
| POST | `/v1/attendance/{attendance_id}/void` | Tenant admin | Void a check-in and refund consumed credits |
| GET/POST | `/v1/daily-roster` | Session / `attendance:write` | Read or add date-level roster entries |
| GET | `/v1/daily-roster/preview?from=YYYY-MM-DD&days=7` | Session | Combine recurring schedules with explicit date-level entries |
| DELETE | `/v1/daily-roster/{entry_id}` | `attendance:write` | Reversibly cancel an explicit roster entry |
| POST | `/v1/daily-roster/{entry_id}/undo` | `attendance:write` | Restore the exact cancelled roster entry |

Transaction types: `purchase`, `consume`, `adjustment`, `refund`, `expire`, `migration`.
Attendance check-in blocks insufficient balances with `409 conflict`. Successful
check-ins write `attendance_sessions.credit_transaction_id` and a linked
`credit_transactions.consume` row. Void writes a `refund` row and stores
`reversal_credit_transaction_id`.

---

## 9. Portfolio

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/students/{student_id}/portfolio` | Tenant admin | List portfolio items |
| POST | `/v1/students/{student_id}/portfolio` | Tenant admin | Create portfolio item |
| PATCH | `/v1/portfolio/{portfolio_item_id}` | Tenant admin | Update portfolio item |
| DELETE | `/v1/portfolio/{portfolio_item_id}` | Tenant admin | Delete portfolio item |

### 9.1 Media Upload

```bash
curl -b /tmp/studio.cookies \
  -F kind=portfolio \
  -F studentId=<student_id> \
  -F file=@artwork.png \
  http://localhost:8899/s/lets-paint-studio/v1/media/upload
```

The canonical media service validates extension, MIME, magic bytes, size, path
traversal, student ownership, and tenant storage quota. Existing legacy CMS media,
portfolio upload, tenant logo, and public registration-media routes call the same
service. `storageProvider=local` is implemented; `s3` remains an extension point.

---

## 10. Public Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/public/{tenant_slug}/brand` | None | Public brand payload |
| POST | `/v1/public/{tenant_slug}/registrations` | None | Submit registration |
| POST | `/v1/public/{tenant_slug}/balance-query` | None | Parent balance lookup |
| POST | `/v1/public/{tenant_slug}/registration-media` | None | Upload registration photo |
| POST | `/v1/public/{tenant_slug}/student/unlock` | None | Verify name + mobile + access code and issue a one-hour HttpOnly student session |
| GET | `/v1/public/{tenant_slug}/student/private` | Student session | Return the bound student's balance, attendance and private portfolio |
| GET | `/v1/public/{tenant_slug}/student/media/{media_asset_id}` | Student session | Serve a sanitized display derivative owned by the bound student |
| POST | `/v1/public/{tenant_slug}/student/logout` | Student session | Revoke the current student session |
| POST | `/v1/public/{tenant_slug}/portfolio-token` | None | Retired; returns 410 in favour of student sessions |
| GET | `/v1/public/{tenant_slug}/media/{media_asset_id}` | None | Serve sanitized public logo/website media derivatives |
| POST | `/v1/public/{tenant_slug}/analytics` | None | Store an allowlisted, privacy-preserving anonymous portal event |
| GET | `/v1/tenant/analytics?days=7|30|90` | Tenant admin | Return aggregate-only portal funnel metrics |
| POST | `/v1/tenant/website-media` | Tenant owner | Upload an unpublished sanitized hero/principal website image |

### 10.1 Balance Query (Public)

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{"name":"Amy Wang","phone":"0412 345 678"}' \
  http://localhost:8899/v1/public/lets-paint-studio/balance-query
```

**Rate limiting (implemented, in-memory per process):** registrations 5/min/IP, balance-query 10/min/IP, registration media uploads 5/min/IP, student-area unlock attempts by tenant+student+IP, and login 30/min/IP plus 5/min/IP+email — all return 429 when exceeded. The retired `portfolio-token` endpoint returns 410 and never creates a token. Failed login attempts write `auth.login_failed` audit events. Limits reset on server restart (acceptable for pilot; shared-storage limiter remains mandatory before multi-instance release).

### Brand publication workspace

- `GET /s/<slug>/v1/tenant/brand-workspace` returns the private draft and the latest 20 publication versions.
- `PUT /s/<slug>/v1/tenant/brand-draft` saves a private draft and does not change public pages.
- `PATCH /s/<slug>/v1/tenant` validates and publishes the submitted brand payload, records a new immutable version, and clears the draft.
- `POST /s/<slug>/v1/tenant/brand-versions/<version_id>/restore` copies a previous publication into the private draft for review. It does not publish automatically.
- Tenant owners cannot change `plan_code` through Studio Admin; commercial plan changes belong to Super Admin.

### Registration acquisition and follow-up

`POST /v1/public/<slug>/registrations` accepts `source`, `sourcePath`, `language`, and `utm_*` fields. The Studio Portal sends `source=portal`; the focused `/<slug>/register` page sends `source=standalone_register`. Both paths share the same consent, rate limit, duplicate detection, storage, notification, and CMS review flow. An optional `publicationConsent` object records the consenting person, relationship, method and notice version; when the registration is converted, it becomes an append-only student publication-consent event rather than a mutable checkbox.

`privacyConsent=true` is required by the API, not only by the browser form. The
accepted notice version and server timestamp are stored on the registration for
audit/export purposes.

`PATCH /s/<slug>/v1/registrations/<id>` supports `contacted`, `trial_booked`, `waiting`, `approved`, `converted`, `rejected`, `lost`, and `archived`, plus `nextFollowUpAt` and `lossReason`.

---

## 10.2 Endpoints added in the A/B sprint (2026-07-03)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/v1/admin/tenants/{id}/password-setup-link` | Super admin | One-time studio-admin password link (24h, single use) |
| POST | `/v1/auth/setup-password` | None (token) | Complete a password-setup link |
| POST | `/v1/admin/tenants/{id}/support-session` | Super admin | Enter support mode (reason required, audited) |
| POST | `/v1/admin/support-session/end` | Session | Exit support mode |
| GET | `/s/<slug>/v1/export/{students,registrations,credit-ledger,revenue}.csv` | Owner / Manager / Super admin + plan feature | Audited CSV exports |
| GET/POST | `/s/<slug>/v1/students/{id}/share-links` | Tenant admin | List/create portfolio share links (1–90 days) |
| POST | `/s/<slug>/v1/share-links/{id}/revoke` | Tenant admin | Revoke a share link |
| GET | `/v1/public/portfolio/{token}` | None (token) | Shared portfolio JSON (viewer page: `/shared/portfolio`) |
| GET | `/v1/public/{slug}/programs` | None | Public course catalogue for the landing page |

Pages: `/setup-password`, `/shared/portfolio`, and `/<slug>` now serves the generated landing page (CMS at `/<slug>/cms`).

## 11. Legacy CMS Bridge

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/s/<slug>/v1/legacy-cms/data` | Tenant session (legacy) | Legacy data bridge |
| POST | `/s/<slug>/v1/legacy-cms/save` | Tenant session (legacy) | Legacy save bridge |

The legacy CMS shell intercepts old `/api/data` and `/api/save` calls and rewrites them to these tenant-scoped endpoints. This keeps the old UI usable during the transition.

---

## 12. Route Protection Summary

> **Audit result (updated 2026-07-12):** sessionless tenant reads remain blocked,
> and sensitive student, credit, attendance, registration, portfolio, export, and
> mutation routes now use explicit role permissions. The aggregate CMS response
> also removes acquisition/financial data for Teacher and private portfolio data
> for Front Desk. Regression guards live in `backend/tests/test_route_protection.py`
> and `backend/tests/test_health.py`; database-backed role/cross-tenant checks live
> in `backend/test_tenant_isolation.py`.

| Category | Protected? | Auth Required |
|---|---|---|
| `/v1/health` | No | None |
| `/v1/public/*` | No | None |
| `/v1/auth/*` | Login: public but rate-limited; logout/change-password/me: Yes | Session |
| `/v1/admin/*` | Yes | Super admin |
| `/v1/plans` writes | Yes | Super admin |
| `/v1/tenant` writes | Yes | Tenant admin |
| `/v1/students` writes | Yes | Tenant admin |
| `/v1/courses` writes | Yes | Tenant admin |
| `/v1/packages` writes | Yes | Tenant admin |
| `/v1/students/*` credits | Yes | Tenant admin |
| `/v1/portfolio` writes | Yes | Tenant admin |
| `/v1/legacy-cms/save` | Yes | Tenant session (legacy) |

---

## 13. Error Responses

| Status | Meaning |
|---|---|
| 400 | Bad request / validation error |
| 401 | Unauthorized — no valid session |
| 403 | Forbidden — wrong tenant or insufficient role |
| 404 | Not found |
| 429 | Rate limited |
| 500 | Internal server error |

All JSON API errors use:

```json
{"error": "machine_readable_code", "message": "Human readable message"}
```

In non-debug mode, `500` responses return a generic message and do not expose
internal exception text.
