-- v7.4.1 stability pass (DB audit findings).
--
-- 1. portfolio_items had no (tenant_id, student_id) index — per-student
--    portfolio listing was the first hot path to degrade with volume.
-- 2. notification_logs had no tenant-leading index at all.
-- 3. credit_accounts carried two IDENTICAL unique partial indexes:
--    idx_credit_accounts_default_account (0001) and
--    credit_accounts_general_uniq (0007). Keep the 0001 name, drop the dupe
--    (every write pays for both; ON CONFLICT inference is unaffected).

CREATE INDEX IF NOT EXISTS idx_portfolio_items_tenant_student
    ON portfolio_items (tenant_id, student_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_logs_tenant_created
    ON notification_logs (tenant_id, created_at DESC);

DROP INDEX IF EXISTS credit_accounts_general_uniq;
