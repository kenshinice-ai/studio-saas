# StudioSaaS API Reference

Version: v3.0
Date: 2026-07-03
Purpose: Complete API endpoint reference, authentication model, tenant resolution, and public endpoints.

---

## 1. API Overview

- **Base URL (local):** `http://localhost:8899`
- **API prefix:** `/v1`
- **Tenant-scoped prefix:** `/s/<tenant_slug>/v1`
- **Auth:** Session cookies (Flask) with `credentials: 'include'`
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
  -d '{"email":"admin@studiosaas.local","password":"admin123456"}'
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
  -d '{"email":"owner@lets-paint-studio.test","password":"admin123456"}'
```

Verifies user is an active `owner` or `super_admin` for the specified tenant.

### 3.3 Change Password

```bash
curl -i -b /tmp/studiosaas.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/v1/auth/change-password \
  -d '{"oldPassword":"admin123456","newPassword":"NewPass2026"}'
```

Rules: Minimum 8 characters, different from old password, requires active session.

---

## 4. Tenant Management

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/tenant` | Tenant admin | Get current tenant |
| PATCH | `/v1/tenant` | Tenant admin | Update tenant settings |
| GET | `/v1/tenant/brand` | Tenant admin | Get tenant brand payload |
| POST | `/v1/tenant/logo` | Tenant admin | Upload tenant logo |
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

---

## 5. Super Admin Routes

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/admin/tenants` | Super admin | List all tenants |
| POST | `/v1/admin/tenants` | Super admin | Create tenant |
| PATCH | `/v1/admin/tenants/{tenant_id}` | Super admin | Update tenant |
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
  "studioAdminPassword": "admin123456"
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
| POST | `/v1/public/{tenant_slug}/portfolio-token` | None | Issue short-lived portfolio token |
| GET | `/v1/public/{tenant_slug}/media/{media_asset_id}?token=...` | None/token | Serve logo or token-protected portfolio media |

### 10.1 Balance Query (Public)

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{"name":"Amy Wang","phone":"0412 345 678"}' \
  http://localhost:8899/v1/public/lets-paint-studio/balance-query
```

**Rate limiting (implemented, in-memory per process):** registrations 5/min/IP, balance-query 10/min/IP, registration media uploads 5/min/IP, portfolio-token 10/min/IP, and login 30/min/IP plus 5/min/IP+email — all return 429 when exceeded. Failed login attempts write `auth.login_failed` audit events. Limits reset on server restart (acceptable for pilot; Redis-backed limiter deferred to P3-04).

---

## 11. Legacy CMS Bridge

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/s/<slug>/v1/legacy-cms/data` | Tenant session (legacy) | Legacy data bridge |
| POST | `/s/<slug>/v1/legacy-cms/save` | Tenant session (legacy) | Legacy save bridge |

The legacy CMS shell intercepts old `/api/data` and `/api/save` calls and rewrites them to these tenant-scoped endpoints. This keeps the old UI usable during the transition.

---

## 12. Route Protection Summary

> **Audit result (2026-07-03, P0-06):** all 146 routes (68 mutating) were audited by decorator scan plus live curl probes. Mutations were already protected (decorators or inline `_auth_ok`/`_rate_ok` checks in the legacy layer). The audit found tenant-scoped **GET reads were unauthenticated** — students, registrations, credits, dashboard, and legacy-cms data were readable by anyone knowing a slug. All 12 such reads now carry `@auth_required` (any active membership in the resolved tenant, or platform super admin). Regression guard: `backend/tests/test_route_protection.py`.

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
