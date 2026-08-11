-- v9.8.3: restore the published-work entitlements for the built-in plans.
--
-- Showcase records are JSON owned by each tenant.  Their publication state is
-- normalised in api_v1.py (legacy records with no state remain active), so no
-- destructive backfill is needed here.  This migration only repairs the
-- commercial defaults that were flattened to 15 when the old Super Admin
-- form omitted showcase_limit from plan edits.

UPDATE plans
SET showcase_limit = CASE code
    WHEN 'starter' THEN 15
    WHEN 'studio' THEN 60
    WHEN 'growth' THEN 150
    ELSE showcase_limit
END
WHERE code IN ('starter', 'studio', 'growth')
  AND showcase_limit IS DISTINCT FROM CASE code
    WHEN 'starter' THEN 15
    WHEN 'studio' THEN 60
    WHEN 'growth' THEN 150
    ELSE showcase_limit
  END;
