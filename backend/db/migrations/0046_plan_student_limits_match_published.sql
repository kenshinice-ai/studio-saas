-- v10.9.x — the three student ceilings catch up with what is actually sold.
--
-- pwestudio.online/pricing serves the plan table the product enforces, and it
-- reads 50 / 250 / 500 students. The repository still carried 100 / 500 / 1000:
-- production was revised through the platform console at some point and the
-- catalogue in git was never brought along. The sales deck was corrected from
-- the same measurement on 2026-08-18; this is the other half of that drift.
--
--   starter : student_limit 100  -> 50
--   studio  : student_limit 500  -> 250
--   growth  : student_limit 1000 -> 500
--
-- Why a migration and not just the baseline seed: 0021 sets growth.student_limit
-- to 1000 with a plain UPDATE, so it re-raises the value on every fresh
-- bootstrap no matter what schema_v1.sql seeds. Editing 0021 in place would
-- rewrite a migration other databases have already applied, so the correction
-- belongs here, after it. (The baseline seeds are updated in the same change so
-- a database that never runs 0021 is also correct.)
--
-- PRICES ARE DELIBERATELY UNTOUCHED, following 0021. growth is AUD 189 on the
-- pricing page and in production, and the baseline seed now says 189 — but a
-- price is money, an operator can set it from the platform console, and a
-- migration that rewrites it would overwrite that decision silently on every
-- deploy. An older database keeps whatever price its operator configured.
--
-- Idempotent: each UPDATE is scoped by plan code and only fires when the value
-- actually differs, so a correct database (production included) records zero
-- row updates and re-running changes nothing.
--
-- CAPACITY SAFETY. These are reductions, and enforcement is admission control
-- only: api_v1._student_capacity rejects a *new* student with HTTP 403 once
-- current >= student_limit. Nothing deletes, archives or truncates a row, so a
-- tenant already above a lowered ceiling keeps every student it has and simply
-- cannot add more until the plan is upgraded. Check headroom before applying:
--
--   SELECT t.slug, t.plan_code, p.student_limit,
--          (SELECT count(*) FROM students s
--            WHERE s.tenant_id = t.id AND s.status <> 'archived') AS students
--     FROM tenants t
--     JOIN plans p ON p.code = t.plan_code
--    ORDER BY students DESC;

UPDATE plans
   SET student_limit = 50
 WHERE code = 'starter'
   AND student_limit <> 50;

UPDATE plans
   SET student_limit = 250
 WHERE code = 'studio'
   AND student_limit <> 250;

UPDATE plans
   SET student_limit = 500
 WHERE code = 'growth'
   AND student_limit <> 500;
