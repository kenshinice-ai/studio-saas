-- v8.7.0 — how many pieces of the studio's own work a plan publishes.
--
-- The Selected Work board (v8.6.0) shipped with a flat cap of 12 for every
-- tenant, hard-coded in three places. It becomes the fourth plan limit,
-- alongside student_limit / user_limit / storage_limit_mb.
--
-- A COLUMN rather than a key in `features`, following the convention already
-- in this table: numeric ceilings are columns with CHECK constraints, and
-- `features` holds booleans (portfolio, data_export, priority_support). A
-- limit in the jsonb would get no constraint, and a limit that can be saved
-- as 0 or -1 is a studio that can publish nothing.
--
--   starter 15 · studio 60 · growth 150
--
-- There is deliberately NO unlimited tier and no per-tenant override. An
-- "unlimited" plan is a promise about a storage bill that cannot be kept, and
-- every one of them eventually grows a hidden ceiling that surprises somebody.
-- A number that is written down is the honest version. It also removes a
-- sentinel value (NULL or -1 meaning infinite) and every `if limit is None`
-- branch that would have come with it.
--
-- 15 rather than 10 on the entry plan is a commercial choice: the board is the
-- part of this product that sells it, and a studio that cannot get a real
-- portfolio onto the page never finds the reason to upgrade.
--
-- IMPORTANT — this limit governs PUBLISHING, never storage. A tenant that
-- moves from growth (150) to starter (15) keeps all 150 works: they stay in
-- the record, stay editable, stay reorderable, and the portal renders the
-- first 15. Nothing is deleted for a billing event. See
-- docs/design/Showcase_Plan_Limits.md §3.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS plus UPDATEs scoped by plan code.

ALTER TABLE plans ADD COLUMN IF NOT EXISTS showcase_limit integer NOT NULL DEFAULT 15;

ALTER TABLE plans DROP CONSTRAINT IF EXISTS plans_showcase_limit_check;
ALTER TABLE plans ADD CONSTRAINT plans_showcase_limit_check CHECK (showcase_limit > 0);

UPDATE plans SET showcase_limit = 15  WHERE code = 'starter' AND showcase_limit IS DISTINCT FROM 15;
UPDATE plans SET showcase_limit = 60  WHERE code = 'studio'  AND showcase_limit IS DISTINCT FROM 60;
UPDATE plans SET showcase_limit = 150 WHERE code = 'growth'  AND showcase_limit IS DISTINCT FROM 150;
