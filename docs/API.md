# StudioSaaS API Reference

Version: v2.0
Date: 2026-07-02
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

## 8. Credits

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/students/{student_id}/credits` | Tenant admin | Student balance |
| POST | `/v1/students/{student_id}/credit-transactions` | Tenant admin | Record transaction |

Transaction types: `purchase`, `consume`, `adjustment`, `refund`, `expire`, `migration`.

---

## 9. Portfolio

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/students/{student_id}/portfolio` | Tenant admin | List portfolio items |
| POST | `/v1/students/{student_id}/portfolio` | Tenant admin | Create portfolio item |
| PATCH | `/v1/portfolio/{portfolio_item_id}` | Tenant admin | Update portfolio item |
| DELETE | `/v1/portfolio/{portfolio_item_id}` | Tenant admin | Delete portfolio item |

### 9.1 Future: Media Upload

```
POST /s/<slug>/v1/media/upload
```

Requirements: Auth required, tenant quota enforced, MIME/magic-byte validated, server-side storage key, tenant-scoped retrieval.

---

## 10. Public Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/public/{tenant_slug}/brand` | None | Public brand payload |
| POST | `/v1/public/{tenant_slug}/registrations` | None | Submit registration |
| POST | `/v1/public/{tenant_slug}/balance-query` | None | Parent balance lookup |
| GET | `/v1/public/portfolio/{token}` | None | Shared portfolio view |

### 10.1 Balance Query (Public)

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{"name":"Amy Wang","phone":"0412 345 678"}' \
  http://localhost:8899/v1/public/lets-paint-studio/balance-query
```

**Risk:** Currently public, not rate-limited in v1. Needs IP rate limiting and duplicate submission control.

---

## 11. Legacy CMS Bridge

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/s/<slug>/v1/legacy-cms/data` | Tenant session (legacy) | Legacy data bridge |
| POST | `/s/<slug>/v1/legacy-cms/save` | Tenant session (legacy) | Legacy save bridge |

The legacy CMS shell intercepts old `/api/data` and `/api/save` calls and rewrites them to these tenant-scoped endpoints. This keeps the old UI usable during the transition.

---

## 12. Route Protection Summary

| Category | Protected? | Auth Required |
|---|---|---|
| `/v1/health` | No | None |
| `/v1/public/*` | No | None |
| `/v1/auth/*` | Login/logout: No; change-password: Yes | Session |
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
| 429 | Rate limited (public endpoints) |
| 500 | Internal server error |
