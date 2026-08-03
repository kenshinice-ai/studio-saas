-- v8.2.20 — a plan row is not automatically an offer.
--
-- The public home page now renders its pricing cards from this table, and
-- `/v1/public/plans` has served it since v8.2.19. Until this migration every
-- row in `plans` was therefore published: create a plan from the platform
-- console, or seed one from a test fixture, and it appeared on the marketing
-- page at whatever price it carried. That is not hypothetical — the local
-- test database seeds `isolation-no-portfolio` at A$1, and rendering the page
-- against it put a one-dollar plan on the public pricing grid beside the real
-- three. Production happened to be clean; nothing was keeping it that way.
--
--   is_public       — DEFAULT false, on purpose. A plan created tomorrow is
--                     invisible until somebody decides to sell it. Publishing
--                     is the deliberate act; existing behaviour was the
--                     accident.
--   is_recommended  — which card wears the badge. It was previously inferred
--                     from position (the median price), which meant one stray
--                     row could move it onto the wrong plan silently.
--
-- The backfill states what is actually sold today. It is written as an
-- explicit list rather than "everything that exists" because the reason this
-- migration exists is that those two sets had already diverged.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and UPDATEs to fixed values scoped by
-- plan code. Re-running changes nothing.

ALTER TABLE plans ADD COLUMN IF NOT EXISTS is_public boolean NOT NULL DEFAULT false;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS is_recommended boolean NOT NULL DEFAULT false;

UPDATE plans
   SET is_public = true
 WHERE code IN ('starter', 'studio', 'growth')
   AND is_public IS DISTINCT FROM true;

UPDATE plans
   SET is_recommended = true
 WHERE code = 'studio'
   AND is_recommended IS DISTINCT FROM true;

-- The badge means "this is the one we recommend", so there can only be one.
-- Enforced in the database rather than in the page, because the page is not
-- the only thing that reads these rows.
CREATE UNIQUE INDEX IF NOT EXISTS plans_one_recommended
    ON plans ((is_recommended)) WHERE is_recommended;
