-- v10.1.1 — a tenant with an issued invoice could not be deleted.
--
-- `trg_invoice_lines_immutable` refuses to delete a line belonging to an issued
-- invoice, which is right: correcting a document a family and an accountant
-- have both seen has to go through a credit note. But `DELETE FROM tenants`
-- cascades to invoices and on to their lines, and the trigger fires on that
-- cascade exactly as it would on somebody editing. So the whole permanent
-- deletion path — a deliberate, confirmed, legally significant operation —
-- failed for any tenant that had ever issued an invoice.
--
-- v10.0.0 shipped with this and its own release evidence says permanent delete
-- was verified. It was: against tenants that had never billed anybody. The
-- fixture had no invoices, so the trigger had nothing to object to.
--
-- The distinction the trigger was missing is not "who is deleting" but "what
-- kind of operation this is". Editing a live document and destroying the whole
-- record are different acts, and only the first is what immutability protects.
-- A transaction-scoped flag says which one is happening, out loud:
--
--     SET LOCAL studiosaas.purging = 'on';
--
-- `SET LOCAL` dies with the transaction, so it cannot leak into the next
-- statement on a pooled connection. `current_setting(..., true)` returns NULL
-- rather than raising when the flag was never set, which is the normal case —
-- so the default stays "immutability applies".
--
-- Deliberately not `session_replication_role = 'replica'`: that disables the
-- foreign-key triggers too, so the cascade this is trying to permit would stop
-- running. It also silences every other guard in the schema at once, which is a
-- much larger promise than this needs to make.

CREATE OR REPLACE FUNCTION assert_issued_invoice_lines_are_immutable()
RETURNS trigger AS $$
DECLARE
    parent_status text;
    parent_id uuid;
BEGIN
    IF current_setting('studiosaas.purging', true) = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    parent_id := COALESCE(NEW.invoice_id, OLD.invoice_id);
    SELECT status INTO parent_status FROM invoices WHERE id = parent_id;
    IF parent_status IS NOT NULL AND parent_status <> 'draft' THEN
        RAISE EXCEPTION
            'Invoice % has been issued; its lines are immutable. Reverse it with a credit note.',
            parent_id
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- The header guard has the same problem for the same reason: a cascade from
-- `tenants` updates nothing, but the showcase reset and any future data
-- migration that rewrites a tenant in place would hit it.
CREATE OR REPLACE FUNCTION assert_issued_invoice_is_immutable()
RETURNS trigger AS $$
BEGIN
    IF current_setting('studiosaas.purging', true) = 'on' THEN
        RETURN NEW;
    END IF;

    IF OLD.status = 'draft' THEN
        RETURN NEW;
    END IF;
    IF NEW.number IS DISTINCT FROM OLD.number
       OR NEW.issue_date IS DISTINCT FROM OLD.issue_date
       OR NEW.subtotal_cents IS DISTINCT FROM OLD.subtotal_cents
       OR NEW.tax_cents IS DISTINCT FROM OLD.tax_cents
       OR NEW.total_cents IS DISTINCT FROM OLD.total_cents
       OR NEW.billing_account_id IS DISTINCT FROM OLD.billing_account_id
       OR NEW.currency IS DISTINCT FROM OLD.currency THEN
        RAISE EXCEPTION
            'Invoice % has been issued; its figures are immutable. Reverse it with a credit note.',
            COALESCE(OLD.number, OLD.id::text)
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
