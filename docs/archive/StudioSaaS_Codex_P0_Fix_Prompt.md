# StudioSaaS Codex P0 Fix Prompt

Copy this prompt into Codex for the next coding session.

---

You are working on the StudioSaaS project.

Goal: Fix the most dangerous P0 backend/runtime issues without redesigning the whole project.

Read these files first:

```text
StudioSaaS_Code_Review_Bug_Risk_Scan_v1.md
StudioSaaS_Codex_Executable_Tasks_v1.md
backend/studiosaas/api_v1.py
backend/studiosaas/auth.py
backend/db/schema_v1.sql
backend/test_cms.py
```

Rules:

1. Keep `backend/` as canonical runtime.
2. Keep `legacy-root/` bridge working.
3. Do not expose root `/register`.
4. Do not remove existing legacy smoke tests.
5. Do not add large dependencies without explaining why.
6. Every tenant mutation route must eventually require auth; for this session, prioritise auth login, route guards, credit bugs, and dict_row bugs.
7. Every changed behaviour needs a test.
8. Run syntax checks after changes.

Perform these fixes in order:

## Fix 1 — v1 auth login

- In `/v1/auth/login`, select `password_hash` from `users`.
- Ensure login does not crash.
- Add or update a local seed user for development.
- Add tests for wrong password, correct password, and `/v1/auth/me`.

## Fix 2 — route protection skeleton

- Implement `require_login`, `require_platform_admin`, and `require_tenant_role` using Flask session and `memberships`.
- Protect `/v1/admin/*`, plan mutations, tenant mutations, student mutations, course/package mutations, credit mutation, portfolio mutation, tenant logo upload, and `/legacy-cms/save`.
- Leave public brand, public registration, public balance, and health public.

## Fix 3 — credit transaction vocabulary

- Align transaction types with schema: `purchase`, `consume`, `adjustment`, `refund`, `expire`, `migration`.
- Remove use of `debit`, `adjustment_in`, `adjustment_out` as stored DB values.
- Add tests for purchase/consume/adjustment/refund.

## Fix 4 — dict_row bugs

Replace all `cur.fetchone()[0]` and `row[0]` usages in `api_v1.py` with dict-key access.
Known locations:

```text
api_v1.py:1623
api_v1.py:1737
api_v1.py:1762
api_v1.py:1834
```

## Fix 5 — credit account upsert

- Fix `ON CONFLICT (tenant_id, student_id)` mismatch.
- Either add a partial unique index for default account, or always use a default General Class course account.
- Prefer the General Class course account model if it fits existing bridge code.

## Fix 6 — by-slug portfolio DELETE mapping

Change by-slug mapping so DELETE calls `delete_portfolio_item`, not `update_portfolio_item`.

Tests to run:

```bash
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py backend/test_cms.py
cd backend && ../.venv/bin/python test_cms.py
cd .. && .venv/bin/python -m pytest backend/tests
```

If pytest structure does not exist yet, create minimal tests under `backend/tests/` for the fixed issues.

Final response format:

```text
Changed files:
Tests run:
Pass/fail result:
Remaining risks:
Recommended next task:
```
