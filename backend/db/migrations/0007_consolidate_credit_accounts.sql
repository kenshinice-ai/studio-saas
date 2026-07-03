-- A2: consolidate credit accounts onto the canonical "general" account
-- (course_id IS NULL) that every read path and v1 endpoint already uses.
--
-- Before this migration three writers disagreed: seeds and the legacy CMS
-- bridge wrote course-scoped account rows, while v1 check-in/transactions
-- and every balance read (CMS data, studio-admin lists) used the NULL-course
-- row — so real credits were invisible in the UI. Per-course balances remain
-- a possible future feature; today the general account is the single ledger.

-- 1) Sum every student's balances into their general account.
WITH totals AS (
    SELECT tenant_id, student_id, SUM(balance) AS total
    FROM credit_accounts
    GROUP BY tenant_id, student_id
)
UPDATE credit_accounts ca
SET balance = t.total,
    updated_at = now()
FROM totals t
WHERE ca.tenant_id = t.tenant_id
  AND ca.student_id = t.student_id
  AND ca.course_id IS NULL;

-- 2) Students that only had course-scoped accounts get a general row.
WITH totals AS (
    SELECT tenant_id, student_id, SUM(balance) AS total,
           MIN(low_balance_threshold) AS threshold
    FROM credit_accounts
    GROUP BY tenant_id, student_id
)
INSERT INTO credit_accounts (tenant_id, student_id, course_id, balance, low_balance_threshold)
SELECT t.tenant_id, t.student_id, NULL, t.total, COALESCE(t.threshold, 2)
FROM totals t
WHERE NOT EXISTS (
    SELECT 1 FROM credit_accounts ca
    WHERE ca.tenant_id = t.tenant_id
      AND ca.student_id = t.student_id
      AND ca.course_id IS NULL
);

-- 3) Retire the course-scoped rows (credit_transactions.account_id is
--    ON DELETE SET NULL, history is preserved).
DELETE FROM credit_accounts WHERE course_id IS NOT NULL;

-- 4) The composite UNIQUE treats NULLs as distinct — enforce one general
--    account per student explicitly.
CREATE UNIQUE INDEX IF NOT EXISTS credit_accounts_general_uniq
    ON credit_accounts (tenant_id, student_id)
    WHERE course_id IS NULL;
