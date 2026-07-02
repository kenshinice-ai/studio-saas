# Studio Admin Credentials and Login Guide

Last updated: 2026-07-02

## Goal

Studio Admin and Studio CMS now use the same tenant-specific login account.

The account is managed by Super Admin per tenant:

- Studio Admin Email
- Studio Admin Name
- Studio Admin Password reset

The same email and password are used for:

- `http://localhost:8899/studio-admin`
- `http://localhost:8899/<tenant_slug>/cms`

## Default Demo Logins

The local demo seed creates one Studio Admin owner account per demo tenant.

| Tenant | Studio Admin Email | Default Password |
| --- | --- | --- |
| `lets-paint-studio` | `owner@lets-paint-studio.test` | `admin123456` |
| `lets-play-piano` | `owner@lets-play-piano.test` | `admin123456` |
| `lets-play-game` | `owner@lets-play-game.test` | `admin123456` |

Super Admin can change these per tenant.

## Super Admin Management

Open:

- `http://localhost:8899/super-admin`

Login with the Super Admin account, then edit or create a tenant.

Tenant fields:

- `Studio Admin Email`: login username for that tenant.
- `Studio Admin Name`: display name for the tenant admin user.
- `Reset Studio Admin Password`: optional. Leave blank to keep the existing password.

Behavior:

- Creating a tenant creates a tenant owner user and membership.
- Editing a tenant updates the same owner login.
- Password is changed only when the reset-password field is filled.
- If no password is provided when creating a tenant, local default is `admin123456`.

## Studio Admin Login

Open:

- `http://localhost:8899/studio-admin`
- or `http://localhost:8899/<tenant_slug>/studio-admin`

Steps:

1. Set tenant slug, for example `lets-paint-studio`. The `/<tenant_slug>/studio-admin` route fills this automatically.
2. Enter the tenant Studio Admin email.
3. Enter the tenant Studio Admin password.
4. The page checks that the logged-in user has `owner` or `super_admin` access to that tenant.

After login, Studio Admin calls tenant-scoped APIs under:

- `/s/<tenant_slug>/v1/...`

This prevents a Studio Admin account from using the wrong tenant slug.

## Studio CMS Login

Open:

- `http://localhost:8899/<tenant_slug>/cms`

Example:

- `http://localhost:8899/lets-paint-studio/cms`

Use the same Studio Admin email and password configured in Super Admin.

The CMS login calls:

- `POST /s/<tenant_slug>/v1/auth/legacy-login`

Payload:

```json
{
  "email": "owner@lets-paint-studio.test",
  "password": "admin123456"
}
```

The backend verifies that the user is an active `owner` or `super_admin` for that tenant.

## Change Studio Admin Password

From Studio Admin:

1. Log in.
2. Click `Change Password`.
3. Enter current password and new password.

From Studio CMS:

1. Log in with the same Studio Admin account.
2. Open settings.
3. Use the password-change fields.

Both paths call:

- `POST /v1/auth/change-password`

Payload:

```json
{
  "oldPassword": "admin123456",
  "newPassword": "NewPass2026"
}
```

Rules:

- New password must be at least 8 characters.
- New password must be different from old password.
- The request requires the current logged-in session.

## API Reference

Studio Admin login:

```bash
curl -i -c /tmp/studio.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/v1/auth/login \
  -d '{"email":"owner@lets-paint-studio.test","password":"admin123456"}'
```

Check session:

```bash
curl -i -b /tmp/studio.cookies \
  http://localhost:8899/v1/auth/me
```

Tenant CMS login:

```bash
curl -i -c /tmp/studio.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/s/lets-paint-studio/v1/auth/legacy-login \
  -d '{"email":"owner@lets-paint-studio.test","password":"admin123456"}'
```

Change password:

```bash
curl -i -b /tmp/studio.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/v1/auth/change-password \
  -d '{"oldPassword":"admin123456","newPassword":"NewPass2026"}'
```

Logout:

```bash
curl -i -b /tmp/studio.cookies \
  -X POST http://localhost:8899/v1/auth/logout
```

## Super Admin Tenant Payload Fields

When creating or updating a tenant through Super Admin:

```json
{
  "studioAdminEmail": "owner@lets-paint-studio.test",
  "studioAdminName": "Let's Paint Studio Owner",
  "studioAdminPassword": "admin123456"
}
```

For updates, omit `studioAdminPassword` or send it as an empty string to keep the existing password.
