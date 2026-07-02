# Super Admin Login and Password Guide

Last updated: 2026-07-02

## Local Login

Open:

- `http://localhost:8899/`
- or `http://localhost:8899/super-admin`

Default local Super Admin account:

- Email: `admin@studiosaas.local`
- Password: `admin123456`

The local start script now runs `backend/scripts/seed_super_admin.py --reset-password` after demo tenant seeding. It ensures the Super Admin user exists, resets the local password to the documented default, and has `super_admin` membership for all existing tenants.

Important behavior:

- If the admin user already exists, local startup resets it to `admin123456`.
- If the admin user does not exist, startup creates it with the default password above.
- If you changed the password during a local session, restarting with `start_studiosaas_local.sh` will restore the local default again.
- If an old local database still contains a mismatched hash, `POST /v1/auth/login` also repairs `admin@studiosaas.local` when the request is made from `localhost` with the documented local password.
- If the browser is signed in as a tenant owner, Super Admin now clears that session and returns to the login panel instead of showing a broken dashboard.

## Browser Flow

1. Open `http://localhost:8899/super-admin`.
2. Enter the email and password.
3. The browser calls `POST /v1/auth/login`.
4. The server sets a Flask session cookie.
5. The Super Admin page then calls:
   - `GET /v1/auth/me`
   - `GET /v1/admin/usage`
   - `GET /v1/plans`
   - `GET /v1/admin/tenants`
   - `GET /v1/admin/audit-logs`

If the session expires or is missing, the page returns to the login panel instead of repeatedly showing data-load errors.

## Login API

Request:

```bash
curl -i -c /tmp/studiosaas.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/v1/auth/login \
  -d '{"email":"admin@studiosaas.local","password":"admin123456"}'
```

Expected success:

```json
{
  "ok": true,
  "userId": "...",
  "name": "System Administrator",
  "token": "..."
}
```

Check current session:

```bash
curl -i -b /tmp/studiosaas.cookies \
  http://localhost:8899/v1/auth/me
```

Logout:

```bash
curl -i -b /tmp/studiosaas.cookies \
  -X POST http://localhost:8899/v1/auth/logout
```

## Change Password

In the UI:

1. Log in to Super Admin.
2. Click `Change Password`.
3. Enter current password and new password.
4. New password must be at least 8 characters and different from the current password.

API:

```bash
curl -i -b /tmp/studiosaas.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/v1/auth/change-password \
  -d '{"oldPassword":"admin123456","newPassword":"NewPass2026"}'
```

Expected success:

```json
{"ok": true}
```

After changing the password, use the new password for future logins.

## Reset Forgotten Local Password

Use this only for local development:

```bash
cd /Users/llmacbookpro/Documents/studiosaas/backend
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_super_admin.py --reset-password \
  --email admin@studiosaas.local \
  --password admin123456
```

Then log in again with:

- Email: `admin@studiosaas.local`
- Password: `admin123456`

If `localhost:8899` is still serving old behavior, stop the old process first:

```bash
lsof -iTCP:8899 -sTCP:LISTEN -nP
kill -9 <PID>
```

Then start again with:

```bash
/Users/llmacbookpro/Documents/studiosaas/START_STUDIOSAAS_LOCAL.command
```

## Related Auth Endpoints

- `POST /v1/auth/login`
- `GET /v1/auth/me`
- `POST /v1/auth/change-password`
- `POST /v1/auth/logout`

Legacy CMS password endpoints still exist separately:

- `POST /api/login`
- `POST /api/change-password`

Use `/v1/auth/*` for Super Admin and StudioSaaS role-based admin access.
