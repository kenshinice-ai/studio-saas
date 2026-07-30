-- v8.1.0 commercial plan quota revision (2026-07-30, owner decision).
--
-- The three SaaS plan quotas are tightened to match the published pricing
-- page, the customer pricing document and the sales deck. Prices, plan codes,
-- plan names and the feature flags are deliberately untouched — only the
-- three quota columns move:
--
--   starter : user_limit 2 -> 1,   storage_limit_mb 5120  -> 2048   (2 GB)
--   studio  : user_limit 8 -> 5,   storage_limit_mb 30720 -> 10240  (10 GB)
--   growth  : student_limit 1500 -> 1000,
--             storage_limit_mb 102400 -> 51200 (50 GB)
--
-- growth.user_limit stays at 20: the owner did not revise it.
--
-- The baseline seed in backend/db/schema_v1.sql and 0001_schema_v1.sql now
-- carries the same numbers, so a fresh bootstrap is already correct and this
-- migration is a no-op there. It exists for databases seeded with the old
-- catalogue (including pwestudio.online production).
--
-- Idempotent: plain UPDATEs to fixed values, scoped by plan code. Re-running
-- changes nothing. Rows are only touched when a value actually differs, so a
-- correct database records zero row updates.
--
-- CAPACITY SAFETY. These are reductions. Enforcement in the application is
-- admission control only:
--   * api_v1._student_capacity + its two call sites reject a *new* student
--     with HTTP 403 when current >= student_limit;
--   * the team-member create/reactivate paths reject with HTTP 403 when
--     active non-parent memberships >= user_limit;
--   * services/media._assert_storage_quota raises MediaQuotaExceededError
--     before a *new* upload is stored.
-- Nothing deletes, archives or truncates existing rows, so a tenant already
-- above a lowered ceiling keeps all of its data and simply cannot add more
-- until the plan is upgraded. Verify headroom before applying:
--
--   SELECT t.slug, t.plan_code,
--          (SELECT count(*) FROM students s
--            WHERE s.tenant_id = t.id AND s.status <> 'archived') AS students,
--          (SELECT count(*) FROM memberships m
--            WHERE m.tenant_id = t.id AND m.status = 'active'
--              AND m.role <> 'parent') AS team_users,
--          u.storage_used_mb
--     FROM tenants t
--     LEFT JOIN tenant_usage u ON u.tenant_id = t.id
--    ORDER BY t.slug;

UPDATE plans
   SET user_limit = 1,
       storage_limit_mb = 2048
 WHERE code = 'starter'
   AND (user_limit <> 1 OR storage_limit_mb <> 2048);

UPDATE plans
   SET user_limit = 5,
       storage_limit_mb = 10240
 WHERE code = 'studio'
   AND (user_limit <> 5 OR storage_limit_mb <> 10240);

UPDATE plans
   SET student_limit = 1000,
       storage_limit_mb = 51200
 WHERE code = 'growth'
   AND (student_limit <> 1000 OR storage_limit_mb <> 51200);
