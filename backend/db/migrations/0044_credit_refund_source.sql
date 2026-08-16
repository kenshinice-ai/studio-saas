-- v10.7.1 — make the purchase source a first-class credit-ledger fact.
--
-- v10.7.0 stored the source only on credit_financial_links.  That was enough
-- for a document-adjusting refund, but it left a credits-only refund without a
-- tenant-scoped provenance field and forced every reader to infer the source
-- from a bridge that may not exist.  Unknown historical links remain NULL.

ALTER TABLE credit_transactions
    ADD COLUMN IF NOT EXISTS source_credit_transaction_id uuid;

ALTER TABLE credit_transactions
    DROP CONSTRAINT IF EXISTS credit_transactions_source_not_self_check,
    DROP CONSTRAINT IF EXISTS credit_transactions_source_same_tenant_fkey;

ALTER TABLE credit_transactions
    ADD CONSTRAINT credit_transactions_source_not_self_check
        CHECK (
            source_credit_transaction_id IS NULL
            OR source_credit_transaction_id <> id
        );

ALTER TABLE credit_transactions
    ADD CONSTRAINT credit_transactions_source_same_tenant_fkey
        FOREIGN KEY (tenant_id, source_credit_transaction_id)
        REFERENCES credit_transactions (tenant_id, id)
        ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS credit_transactions_source_credit_transaction_idx
    ON credit_transactions (tenant_id, source_credit_transaction_id)
    WHERE source_credit_transaction_id IS NOT NULL;

-- Backfill only from the durable v10.7.0 bridge.  Notes are operator prose,
-- not a source of truth, so an unresolved row is deliberately left NULL.
UPDATE credit_transactions AS refund
   SET source_credit_transaction_id = link.related_credit_transaction_id
  FROM credit_financial_links AS link
 WHERE link.tenant_id = refund.tenant_id
   AND link.credit_transaction_id = refund.id
   AND link.related_credit_transaction_id IS NOT NULL
   AND refund.transaction_type = 'refund'
   AND refund.source_credit_transaction_id IS NULL;

DO $$
DECLARE
    unresolved_count bigint;
BEGIN
    SELECT count(*)
      INTO unresolved_count
      FROM credit_transactions AS refund
     WHERE refund.transaction_type = 'refund'
       AND refund.source_credit_transaction_id IS NULL;
    RAISE NOTICE '0044 credit refund source backfill unresolved=%', unresolved_count;
END;
$$;

CREATE OR REPLACE FUNCTION assert_credit_transaction_source_is_legal()
RETURNS trigger AS $$
DECLARE
    source_type text;
    source_student_id uuid;
BEGIN
    IF NEW.source_credit_transaction_id IS NULL THEN
        RETURN NEW;
    END IF;

    IF NEW.transaction_type <> 'refund' THEN
        RAISE EXCEPTION 'Only refund credit transactions may name a source purchase.'
            USING ERRCODE = 'check_violation';
    END IF;

    SELECT transaction_type, student_id
      INTO source_type, source_student_id
      FROM credit_transactions
     WHERE tenant_id = NEW.tenant_id
       AND id = NEW.source_credit_transaction_id;
    -- The source transaction_type = 'purchase' in this tenant is the only
    -- legal origin; NULL is rejected by the same branch.
    IF source_type IS DISTINCT FROM 'purchase' THEN
        RAISE EXCEPTION 'A refund source must be a purchase in the same tenant.'
            USING ERRCODE = 'check_violation';
    END IF;
    IF source_student_id IS DISTINCT FROM NEW.student_id THEN
        RAISE EXCEPTION 'A refund source must belong to the same student.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_credit_transaction_source_legal ON credit_transactions;
CREATE TRIGGER trg_credit_transaction_source_legal
    BEFORE INSERT OR UPDATE OF tenant_id, student_id, transaction_type,
                               source_credit_transaction_id
    ON credit_transactions
    FOR EACH ROW EXECUTE FUNCTION assert_credit_transaction_source_is_legal();

-- Keep the bridge readable for old records while making the new ledger column
-- the canonical source used by all current refund queries.
CREATE INDEX IF NOT EXISTS idx_credit_financial_links_refund_source
    ON credit_financial_links (tenant_id, related_credit_transaction_id,
                               credit_transaction_id)
    WHERE related_credit_transaction_id IS NOT NULL;
