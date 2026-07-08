-- A2: refunds record money leaving as a NEGATIVE fee so revenue sums net
-- out automatically (LetsPaintCMS v5.3). The original CHECK required
-- fee_aud_cents >= 0; replace it with a symmetric sanity bound.

ALTER TABLE credit_transactions
    DROP CONSTRAINT IF EXISTS credit_transactions_fee_aud_cents_check;

ALTER TABLE credit_transactions
    ADD CONSTRAINT credit_transactions_fee_aud_cents_check
    CHECK (fee_aud_cents BETWEEN -100000000 AND 100000000);
