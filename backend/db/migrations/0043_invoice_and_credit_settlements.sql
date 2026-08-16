-- v10.7.0 — freeze the identity of issued documents and give the credit and
-- money ledgers one explicit, tenant-scoped bridge.
--
-- Students remain the subjects of a service.  Billing accounts remain the
-- payers.  This migration does not merge the two ledgers; it makes the legal
-- relationship between them durable and makes retries safe to reason about.

-- ── payer kinds ─────────────────────────────────────────────────────────

ALTER TABLE billing_accounts DROP CONSTRAINT IF EXISTS billing_accounts_kind_check;
ALTER TABLE billing_accounts
    ADD CONSTRAINT billing_accounts_kind_check
    CHECK (kind IN ('person', 'family', 'organisation'));

-- ── issued-document identity snapshots ─────────────────────────────────
--
-- Drafts intentionally keep an empty snapshot and may show live preview data.
-- At issue time services fill both snapshots in the same transaction that
-- allocates the number and changes status.  Existing issued documents are
-- backfilled from the identity/account that was authoritative at migration
-- time, so they never silently fall back to a future live edit.

ALTER TABLE invoices
    ADD COLUMN IF NOT EXISTS supplier_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS recipient_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS snapshot_schema_version integer NOT NULL DEFAULT 1
        CHECK (snapshot_schema_version >= 1);

ALTER TABLE credit_notes
    ADD COLUMN IF NOT EXISTS supplier_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS recipient_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS snapshot_schema_version integer NOT NULL DEFAULT 1
        CHECK (snapshot_schema_version >= 1);

UPDATE invoices AS i
   SET supplier_snapshot = jsonb_build_object(
           'schemaVersion', 1,
           'configured', (bi.tenant_id IS NOT NULL),
           'legalName', COALESCE(bi.legal_name, ''),
           'tradingName', COALESCE(bi.trading_name, ''),
           'abn', COALESCE(bi.abn, ''),
           'gstRegistered', COALESCE(bi.gst_registered, false),
           'address', jsonb_build_object(
               'line1', COALESCE(bi.address_line1, ''),
               'line2', COALESCE(bi.address_line2, ''),
               'suburb', COALESCE(bi.suburb, ''),
               'state', COALESCE(bi.state, ''),
               'postcode', COALESCE(bi.postcode, ''),
               'country', COALESCE(bi.country, 'Australia')
           ),
           'contactEmail', COALESCE(bi.contact_email, ''),
           'contactPhone', COALESCE(bi.contact_phone, ''),
           'website', COALESCE(bi.website, ''),
           'bank', jsonb_build_object(
               'accountName', COALESCE(bi.bank_account_name, ''),
               'bsb', COALESCE(bi.bank_bsb, ''),
               'accountNo', COALESCE(bi.bank_account_no, '')
           ),
           'paymentNote', COALESCE(bi.payment_note, '')
       ),
       recipient_snapshot = jsonb_build_object(
           'schemaVersion', 1,
           'displayName', a.name,
           'kind', a.kind,
           'contactName', a.contact_name,
           'companyName', a.company_name,
           'abn', a.abn,
           'email', a.email,
           'mobile', a.mobile,
           'billingAddress', a.billing_address,
           'paymentTermsDays', a.payment_terms_days,
           'purchaseOrderRef', a.purchase_order_ref,
           'language', a.language
       )
  FROM billing_accounts AS a
  LEFT JOIN tenant_billing_identity AS bi
    ON bi.tenant_id = a.tenant_id
 WHERE i.tenant_id = a.tenant_id
   AND i.billing_account_id = a.id
   AND i.status <> 'draft'
   AND (i.supplier_snapshot = '{}'::jsonb OR i.recipient_snapshot = '{}'::jsonb);

UPDATE credit_notes AS n
   SET supplier_snapshot = jsonb_build_object(
           'schemaVersion', 1,
           'configured', (bi.tenant_id IS NOT NULL),
           'legalName', COALESCE(bi.legal_name, ''),
           'tradingName', COALESCE(bi.trading_name, ''),
           'abn', COALESCE(bi.abn, ''),
           'gstRegistered', COALESCE(bi.gst_registered, false),
           'address', jsonb_build_object(
               'line1', COALESCE(bi.address_line1, ''),
               'line2', COALESCE(bi.address_line2, ''),
               'suburb', COALESCE(bi.suburb, ''),
               'state', COALESCE(bi.state, ''),
               'postcode', COALESCE(bi.postcode, ''),
               'country', COALESCE(bi.country, 'Australia')
           ),
           'contactEmail', COALESCE(bi.contact_email, ''),
           'contactPhone', COALESCE(bi.contact_phone, ''),
           'website', COALESCE(bi.website, ''),
           'bank', jsonb_build_object(
               'accountName', COALESCE(bi.bank_account_name, ''),
               'bsb', COALESCE(bi.bank_bsb, ''),
               'accountNo', COALESCE(bi.bank_account_no, '')
           ),
           'paymentNote', COALESCE(bi.payment_note, '')
       ),
       recipient_snapshot = jsonb_build_object(
           'schemaVersion', 1,
           'displayName', a.name,
           'kind', a.kind,
           'contactName', a.contact_name,
           'companyName', a.company_name,
           'abn', a.abn,
           'email', a.email,
           'mobile', a.mobile,
           'billingAddress', a.billing_address,
           'paymentTermsDays', a.payment_terms_days,
           'purchaseOrderRef', a.purchase_order_ref,
           'language', a.language
       )
  FROM billing_accounts AS a
  LEFT JOIN tenant_billing_identity AS bi
    ON bi.tenant_id = a.tenant_id
 WHERE n.tenant_id = a.tenant_id
   AND n.billing_account_id = a.id
   AND n.status <> 'draft'
   AND (n.supplier_snapshot = '{}'::jsonb OR n.recipient_snapshot = '{}'::jsonb);

ALTER TABLE invoices
    ADD CONSTRAINT invoices_issued_snapshots_check
    CHECK (
        status = 'draft'
        OR (
            supplier_snapshot <> '{}'::jsonb
            AND recipient_snapshot <> '{}'::jsonb
            AND snapshot_schema_version >= 1
        )
    );

ALTER TABLE credit_notes
    ADD CONSTRAINT credit_notes_issued_snapshots_check
    CHECK (
        status = 'draft'
        OR (
            supplier_snapshot <> '{}'::jsonb
            AND recipient_snapshot <> '{}'::jsonb
            AND snapshot_schema_version >= 1
        )
    );

-- The bridge and operation records use tenant-scoped composite foreign keys.
-- These unique indexes are additive and also make the intended invariant
-- explicit for existing tables that previously had only a global UUID key.
CREATE UNIQUE INDEX IF NOT EXISTS credit_transactions_tenant_id_key
    ON credit_transactions (tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS invoice_lines_tenant_id_key
    ON invoice_lines (tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS refunds_tenant_id_key
    ON refunds (tenant_id, id);

-- Replace the v10.0 trigger with the v10.7 version that freezes snapshots too.
CREATE OR REPLACE FUNCTION assert_issued_invoice_is_immutable()
RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'draft' THEN
        RETURN NEW;
    END IF;
    IF NEW.number IS DISTINCT FROM OLD.number
       OR NEW.issue_date IS DISTINCT FROM OLD.issue_date
       OR NEW.subtotal_cents IS DISTINCT FROM OLD.subtotal_cents
       OR NEW.tax_cents IS DISTINCT FROM OLD.tax_cents
       OR NEW.total_cents IS DISTINCT FROM OLD.total_cents
       OR NEW.billing_account_id IS DISTINCT FROM OLD.billing_account_id
       OR NEW.currency IS DISTINCT FROM OLD.currency
       OR NEW.supplier_snapshot IS DISTINCT FROM OLD.supplier_snapshot
       OR NEW.recipient_snapshot IS DISTINCT FROM OLD.recipient_snapshot
       OR NEW.snapshot_schema_version IS DISTINCT FROM OLD.snapshot_schema_version THEN
        RAISE EXCEPTION
            'Invoice % has been issued; its figures and identity snapshot are immutable. Reverse it with a credit note.',
            COALESCE(OLD.number, OLD.id::text)
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_invoices_immutable ON invoices;
CREATE TRIGGER trg_invoices_immutable
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION assert_issued_invoice_is_immutable();

CREATE OR REPLACE FUNCTION assert_issued_credit_note_is_immutable()
RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'draft' THEN
        RETURN NEW;
    END IF;
    IF NEW.number IS DISTINCT FROM OLD.number
       OR NEW.issue_date IS DISTINCT FROM OLD.issue_date
       OR NEW.subtotal_cents IS DISTINCT FROM OLD.subtotal_cents
       OR NEW.tax_cents IS DISTINCT FROM OLD.tax_cents
       OR NEW.total_cents IS DISTINCT FROM OLD.total_cents
       OR NEW.billing_account_id IS DISTINCT FROM OLD.billing_account_id
       OR NEW.invoice_id IS DISTINCT FROM OLD.invoice_id
       OR NEW.supplier_snapshot IS DISTINCT FROM OLD.supplier_snapshot
       OR NEW.recipient_snapshot IS DISTINCT FROM OLD.recipient_snapshot
       OR NEW.snapshot_schema_version IS DISTINCT FROM OLD.snapshot_schema_version THEN
        RAISE EXCEPTION
            'Credit note % has been issued; its figures and identity snapshot are immutable.',
            COALESCE(OLD.number, OLD.id::text)
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_credit_notes_immutable ON credit_notes;
CREATE TRIGGER trg_credit_notes_immutable
    BEFORE UPDATE ON credit_notes
    FOR EACH ROW EXECUTE FUNCTION assert_issued_credit_note_is_immutable();

-- ── cross-ledger bridge ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS credit_financial_links (
    id                             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    credit_transaction_id          uuid NOT NULL,
    related_credit_transaction_id  uuid,
    invoice_id                     uuid NOT NULL,
    invoice_line_id                uuid NOT NULL,
    payment_id                     uuid,
    credit_note_id                 uuid,
    refund_id                      uuid,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT credit_financial_links_credit_tx_tenant_fkey
        FOREIGN KEY (tenant_id, credit_transaction_id)
        REFERENCES credit_transactions (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT credit_financial_links_related_credit_tx_tenant_fkey
        FOREIGN KEY (tenant_id, related_credit_transaction_id)
        REFERENCES credit_transactions (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT credit_financial_links_invoice_tenant_fkey
        FOREIGN KEY (tenant_id, invoice_id)
        REFERENCES invoices (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT credit_financial_links_invoice_line_tenant_fkey
        FOREIGN KEY (tenant_id, invoice_line_id)
        REFERENCES invoice_lines (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT credit_financial_links_payment_tenant_fkey
        FOREIGN KEY (tenant_id, payment_id)
        REFERENCES payments (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT credit_financial_links_credit_note_tenant_fkey
        FOREIGN KEY (tenant_id, credit_note_id)
        REFERENCES credit_notes (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT credit_financial_links_refund_tenant_fkey
        FOREIGN KEY (tenant_id, refund_id)
        REFERENCES refunds (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT credit_financial_links_credit_tx_uniq
        UNIQUE (tenant_id, credit_transaction_id),
    CONSTRAINT credit_financial_links_tenant_id_uniq
        UNIQUE (tenant_id, id),
    CONSTRAINT credit_financial_links_not_self_related
        CHECK (related_credit_transaction_id IS NULL
               OR related_credit_transaction_id <> credit_transaction_id),
    CONSTRAINT credit_financial_links_legal_shape
        CHECK (
            (
                related_credit_transaction_id IS NULL
                AND invoice_id IS NOT NULL
                AND invoice_line_id IS NOT NULL
                AND credit_note_id IS NULL
                AND refund_id IS NULL
            )
            OR
            (
                related_credit_transaction_id IS NOT NULL
                AND invoice_id IS NOT NULL
                AND invoice_line_id IS NOT NULL
                AND payment_id IS NOT NULL
                AND credit_note_id IS NOT NULL
                AND refund_id IS NOT NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_credit_financial_links_invoice
    ON credit_financial_links (tenant_id, invoice_id);
CREATE INDEX IF NOT EXISTS idx_credit_financial_links_related_credit
    ON credit_financial_links (tenant_id, related_credit_transaction_id)
    WHERE related_credit_transaction_id IS NOT NULL;

CREATE OR REPLACE FUNCTION assert_credit_financial_link_is_legal()
RETURNS trigger AS $$
DECLARE
    current_type text;
    related_type text;
    line_invoice_id uuid;
    note_invoice_id uuid;
    refund_payment_id uuid;
    refund_note_id uuid;
BEGIN
    SELECT transaction_type INTO current_type
      FROM credit_transactions
     WHERE tenant_id = NEW.tenant_id AND id = NEW.credit_transaction_id;
    IF current_type IS NULL THEN
        RAISE EXCEPTION 'Credit transaction does not belong to this tenant.'
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    SELECT invoice_id INTO line_invoice_id
      FROM invoice_lines
     WHERE tenant_id = NEW.tenant_id AND id = NEW.invoice_line_id;
    IF line_invoice_id IS DISTINCT FROM NEW.invoice_id THEN
        RAISE EXCEPTION 'Credit financial link line does not belong to its invoice.'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.related_credit_transaction_id IS NULL THEN
        IF current_type <> 'purchase' THEN
            RAISE EXCEPTION 'A purchase bridge must point to a purchase credit transaction.'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        SELECT transaction_type INTO related_type
          FROM credit_transactions
         WHERE tenant_id = NEW.tenant_id AND id = NEW.related_credit_transaction_id;
        IF current_type <> 'refund' OR related_type <> 'purchase' THEN
            RAISE EXCEPTION 'A refund bridge must point from refund to purchase.'
                USING ERRCODE = 'check_violation';
        END IF;

        SELECT invoice_id INTO note_invoice_id
          FROM credit_notes
         WHERE tenant_id = NEW.tenant_id AND id = NEW.credit_note_id;
        IF note_invoice_id IS DISTINCT FROM NEW.invoice_id THEN
            RAISE EXCEPTION 'Credit note does not reference the bridged invoice.'
                USING ERRCODE = 'check_violation';
        END IF;

        SELECT payment_id, credit_note_id
          INTO refund_payment_id, refund_note_id
          FROM refunds
         WHERE tenant_id = NEW.tenant_id AND id = NEW.refund_id;
        IF refund_payment_id IS DISTINCT FROM NEW.payment_id
           OR refund_note_id IS DISTINCT FROM NEW.credit_note_id THEN
            RAISE EXCEPTION 'Refund does not reference the bridged payment and credit note.'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF NEW.payment_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM payment_allocations
            WHERE tenant_id = NEW.tenant_id
              AND payment_id = NEW.payment_id
              AND invoice_id = NEW.invoice_id
       ) THEN
        RAISE EXCEPTION 'A financial link payment must be allocated to the bridged invoice.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_credit_financial_links_legal ON credit_financial_links;
CREATE TRIGGER trg_credit_financial_links_legal
    BEFORE INSERT OR UPDATE ON credit_financial_links
    FOR EACH ROW EXECUTE FUNCTION assert_credit_financial_link_is_legal();

-- ── operation idempotency ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS financial_operation_requests (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    request_id            text NOT NULL CHECK (btrim(request_id) <> ''),
    operation_kind        text NOT NULL CHECK (btrim(operation_kind) <> ''),
    payload_hash          text NOT NULL CHECK (btrim(payload_hash) <> ''),
    status                text NOT NULL DEFAULT 'in_progress'
                              CHECK (status IN ('in_progress', 'succeeded', 'failed')),
    result                jsonb NOT NULL DEFAULT '{}'::jsonb,
    credit_transaction_id  uuid,
    invoice_id             uuid,
    payment_id             uuid,
    credit_note_id         uuid,
    refund_id              uuid,
    error_code             text NOT NULL DEFAULT '',
    error_message          text NOT NULL DEFAULT '',
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    completed_at           timestamptz,
    CONSTRAINT financial_operation_requests_key
        UNIQUE (tenant_id, request_id, operation_kind),
    CONSTRAINT financial_operation_requests_tenant_id_uniq
        UNIQUE (tenant_id, id),
    CONSTRAINT financial_operation_requests_credit_tx_tenant_fkey
        FOREIGN KEY (tenant_id, credit_transaction_id)
        REFERENCES credit_transactions (tenant_id, id) ON DELETE SET NULL,
    CONSTRAINT financial_operation_requests_invoice_tenant_fkey
        FOREIGN KEY (tenant_id, invoice_id)
        REFERENCES invoices (tenant_id, id) ON DELETE SET NULL,
    CONSTRAINT financial_operation_requests_payment_tenant_fkey
        FOREIGN KEY (tenant_id, payment_id)
        REFERENCES payments (tenant_id, id) ON DELETE SET NULL,
    CONSTRAINT financial_operation_requests_credit_note_tenant_fkey
        FOREIGN KEY (tenant_id, credit_note_id)
        REFERENCES credit_notes (tenant_id, id) ON DELETE SET NULL,
    CONSTRAINT financial_operation_requests_refund_tenant_fkey
        FOREIGN KEY (tenant_id, refund_id)
        REFERENCES refunds (tenant_id, id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_financial_operation_requests_status
    ON financial_operation_requests (tenant_id, status, created_at);

CREATE OR REPLACE FUNCTION assert_financial_operation_payload_is_immutable()
RETURNS trigger AS $$
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.operation_kind IS DISTINCT FROM OLD.operation_kind
       OR NEW.payload_hash IS DISTINCT FROM OLD.payload_hash THEN
        RAISE EXCEPTION 'An idempotency request key cannot be reused with a different payload.'
            USING ERRCODE = 'unique_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_financial_operation_payload_immutable
    ON financial_operation_requests;
CREATE TRIGGER trg_financial_operation_payload_immutable
    BEFORE UPDATE ON financial_operation_requests
    FOR EACH ROW EXECUTE FUNCTION assert_financial_operation_payload_is_immutable();

-- New tenant-owned tables must fail closed exactly like the rest of the money
-- layer.  The platform flag is the existing, explicit super-admin escape hatch.
ALTER TABLE credit_financial_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_financial_links FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON credit_financial_links;
CREATE POLICY tenant_isolation ON credit_financial_links
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');

ALTER TABLE financial_operation_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_operation_requests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON financial_operation_requests;
CREATE POLICY tenant_isolation ON financial_operation_requests
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');

GRANT SELECT, INSERT, UPDATE, DELETE
    ON credit_financial_links, financial_operation_requests TO studiosaas_app;
