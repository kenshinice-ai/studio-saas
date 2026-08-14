-- v10.1 — the plan rows learn what v10.0.0 added.
--
-- The entitlement resolver has been live since 0032 and the panels that read it
-- since v10.1, but nothing ever told the `plans` table that teacher payables,
-- SMS and management reports exist. The effect was quiet and total: the
-- resolver correctly answered "no" for every tenant on every tier, so the two
-- capabilities could not be reached by anybody, on any plan, ever — and no test
-- caught it because every test either runs standalone (all-on) or grants what
-- it needs directly.
--
-- The tiering follows the shape of the studio rather than the shape of the
-- feature list. The money chain — invoicing, payments, recurring lessons, the
-- family calendar feed, progress reports — is BASELINE_FEATURES in code and
-- deliberately not sold by tier at all: an entry-tier tenant is a single
-- teacher whose whole business is scheduling a lesson, invoicing it and being
-- paid for it, and selling one link of that separately makes a broken product
-- rather than a cheaper one.
--
-- What does divide by tier is scale and team:
--
--   Studio   adds teacher payables, because a single-user Starter tenant IS the
--            teacher and has nobody to pay, and SMS, because a studio with a
--            team has somebody to send it.
--   Growth   adds management reports, because reading numbers is a job that
--            appears when somebody stops teaching full time.
--
-- Xero is absent from every tier on purpose: it is a per-tenant add-on in
-- `tenant_addons`, available on any plan, and mixing the two storage shapes is
-- what turns "available on any tier" back into "change your plan".
--
-- Written as a merge rather than an overwrite so a plan whose features were
-- hand-tuned for a pilot keeps them.

UPDATE plans
   SET features = features || '{"teacher_payables": true, "sms_notifications": true}'::jsonb
 WHERE code IN ('studio', 'growth');

UPDATE plans
   SET features = features || '{"management_reports": true}'::jsonb
 WHERE code = 'growth';
