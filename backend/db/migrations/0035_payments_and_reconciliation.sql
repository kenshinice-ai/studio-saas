-- v10.0.0 — money in, and the arithmetic that must never drift.
--
-- The platform does not process payments. Each tenant connects their own
-- merchant account and the payer completes the transaction on the provider's
-- hosted page, so a card number never reaches this database and never reaches
-- the tenant's server. That keeps PCI scope at the lightest tier and keeps us
-- out of the funds flow entirely — we are not a payment facilitator, we are a
-- system that records that a payment happened.
--
-- Two things in here are triggers rather than application code, for the same
-- reason the invoice immutability trigger is: they are arithmetic that has to
-- hold no matter which code path, script or console session touched the rows.
--
--   * a payment can never be allocated to more than it was worth;
--   * an invoice's paid total is always exactly the sum of its allocations,
--     and its status always agrees with its balance.

-- ── connected merchant accounts ──────────────────────────────────────────
--
-- Credentials are stored encrypted by the application; the column name says so
-- to stop a future reader treating it as readable text. Stripe first, Square
-- second, both behind the same shape.

CREATE TABLE IF NOT EXISTS payment_providers (
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider            text NOT NULL CHECK (provider IN ('stripe', 'square')),
    display_name        text NOT NULL DEFAULT '',
    mode                text NOT NULL DEFAULT 'test' CHECK (mode IN ('test', 'live')),
    account_ref         text NOT NULL DEFAULT '',
    secret_encrypted    text NOT NULL DEFAULT '',
    webhook_secret_encrypted text NOT NULL DEFAULT '',
    surcharge_bp        integer NOT NULL DEFAULT 0
                            CHECK (surcharge_bp >= 0 AND surcharge_bp <= 10000),
    is_active           boolean NOT NULL DEFAULT false,
    connected_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    connected_at        timestamptz,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, provider)
);

-- ── payments ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS payments (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    billing_account_id uuid NOT NULL,
    method             text NOT NULL
                           CHECK (method IN ('card', 'direct_debit', 'bank_transfer',
                                             'cash', 'other')),
    provider           text CHECK (provider IS NULL OR provider IN ('stripe', 'square')),
    provider_ref       text NOT NULL DEFAULT '',
    amount_cents       integer NOT NULL CHECK (amount_cents > 0),
    fee_cents          integer NOT NULL DEFAULT 0 CHECK (fee_cents >= 0),
    surcharge_cents    integer NOT NULL DEFAULT 0 CHECK (surcharge_cents >= 0),
    refunded_cents     integer NOT NULL DEFAULT 0 CHECK (refunded_cents >= 0),
    status             text NOT NULL DEFAULT 'succeeded'
                           CHECK (status IN ('pending', 'succeeded', 'failed', 'refunded')),
    received_at        timestamptz NOT NULL DEFAULT now(),
    -- Set by whichever surface created the payment. Unique per tenant so a
    -- retried request, a replayed webhook and a double-clicked button all
    -- resolve to the same single row.
    idempotency_key    text,
    note               text NOT NULL DEFAULT '',
    recorded_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT payments_account_tenant_fkey
        FOREIGN KEY (tenant_id, billing_account_id)
        REFERENCES billing_accounts (tenant_id, id) ON DELETE RESTRICT,
    CHECK (refunded_cents <= amount_cents),
    UNIQUE (tenant_id, idempotency_key),
    UNIQUE (tenant_id, id)
);

CREATE INDEX IF NOT EXISTS idx_payments_account
    ON payments (tenant_id, billing_account_id, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_payments_provider_ref
    ON payments (tenant_id, provider, provider_ref)
    WHERE provider IS NOT NULL;

CREATE TABLE IF NOT EXISTS payment_allocations (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    payment_id   uuid NOT NULL,
    invoice_id   uuid NOT NULL,
    amount_cents integer NOT NULL CHECK (amount_cents > 0),
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT payment_allocations_payment_tenant_fkey
        FOREIGN KEY (tenant_id, payment_id)
        REFERENCES payments (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT payment_allocations_invoice_tenant_fkey
        FOREIGN KEY (tenant_id, invoice_id)
        REFERENCES invoices (tenant_id, id) ON DELETE RESTRICT,
    UNIQUE (payment_id, invoice_id)
);

CREATE INDEX IF NOT EXISTS idx_payment_allocations_invoice
    ON payment_allocations (invoice_id);

CREATE TABLE IF NOT EXISTS refunds (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    payment_id     uuid NOT NULL,
    credit_note_id uuid,
    amount_cents   integer NOT NULL CHECK (amount_cents > 0),
    provider_ref   text NOT NULL DEFAULT '',
    status         text NOT NULL DEFAULT 'succeeded'
                       CHECK (status IN ('pending', 'succeeded', 'failed')),
    reason         text NOT NULL DEFAULT '',
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT refunds_payment_tenant_fkey
        FOREIGN KEY (tenant_id, payment_id)
        REFERENCES payments (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT refunds_credit_note_tenant_fkey
        FOREIGN KEY (tenant_id, credit_note_id)
        REFERENCES credit_notes (tenant_id, id) ON DELETE SET NULL
);

-- ── webhook intake ───────────────────────────────────────────────────────
--
-- Providers retry, and they are right to: a delivery that timed out looks
-- identical to one that was never sent. The unique key on (provider, event_id)
-- is what makes a replay free — the second delivery of the same event conflicts
-- and is acknowledged without posting anything a second time.

CREATE TABLE IF NOT EXISTS payment_provider_events (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider     text NOT NULL CHECK (provider IN ('stripe', 'square')),
    event_id     text NOT NULL,
    tenant_id    uuid REFERENCES tenants(id) ON DELETE CASCADE,
    event_type   text NOT NULL DEFAULT '',
    payload      jsonb NOT NULL DEFAULT '{}'::jsonb,
    received_at  timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    error_message text NOT NULL DEFAULT '',
    UNIQUE (provider, event_id)
);

CREATE INDEX IF NOT EXISTS idx_payment_provider_events_unprocessed
    ON payment_provider_events (received_at)
    WHERE processed_at IS NULL;

-- ── bank statement matching ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bank_statement_lines (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    occurred_on       date NOT NULL,
    description       text NOT NULL DEFAULT '',
    reference         text NOT NULL DEFAULT '',
    amount_cents      integer NOT NULL,
    matched_payment_id uuid,
    import_batch      text NOT NULL DEFAULT '',
    imported_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT bank_statement_lines_payment_tenant_fkey
        FOREIGN KEY (tenant_id, matched_payment_id)
        REFERENCES payments (tenant_id, id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_bank_statement_lines_unmatched
    ON bank_statement_lines (tenant_id, occurred_on DESC)
    WHERE matched_payment_id IS NULL;

-- ── the arithmetic, enforced ─────────────────────────────────────────────

CREATE OR REPLACE FUNCTION assert_allocation_within_payment()
RETURNS trigger AS $$
DECLARE
    payment_amount integer;
    payment_refunded integer;
    allocated integer;
BEGIN
    SELECT amount_cents, refunded_cents INTO payment_amount, payment_refunded
    FROM payments WHERE id = NEW.payment_id;

    SELECT COALESCE(SUM(amount_cents), 0) INTO allocated
    FROM payment_allocations
    WHERE payment_id = NEW.payment_id AND id <> NEW.id;

    IF allocated + NEW.amount_cents > payment_amount - payment_refunded THEN
        RAISE EXCEPTION
            'Allocating % cents would exceed payment % (worth %, refunded %, already allocated %).',
            NEW.amount_cents, NEW.payment_id, payment_amount, payment_refunded, allocated
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_allocation_within_payment ON payment_allocations;
CREATE TRIGGER trg_allocation_within_payment
    BEFORE INSERT OR UPDATE ON payment_allocations
    FOR EACH ROW EXECUTE FUNCTION assert_allocation_within_payment();

-- An invoice's paid figure is never written by hand. It is recomputed from the
-- allocations that exist, every time they change, and the status is derived
-- from the resulting balance. Nothing can leave the two disagreeing.
CREATE OR REPLACE FUNCTION sync_invoice_payment_totals()
RETURNS trigger AS $$
DECLARE
    target_invoice uuid;
    paid integer;
BEGIN
    target_invoice := COALESCE(NEW.invoice_id, OLD.invoice_id);

    SELECT COALESCE(SUM(amount_cents), 0) INTO paid
    FROM payment_allocations WHERE invoice_id = target_invoice;

    UPDATE invoices
       SET amount_paid_cents = paid,
           status = CASE
               WHEN status IN ('draft', 'void') THEN status
               WHEN paid + amount_credited_cents >= total_cents THEN 'paid'
               WHEN paid > 0 THEN 'part_paid'
               ELSE 'issued'
           END,
           updated_at = now()
     WHERE id = target_invoice;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_invoice_payment_totals ON payment_allocations;
CREATE TRIGGER trg_sync_invoice_payment_totals
    AFTER INSERT OR UPDATE OR DELETE ON payment_allocations
    FOR EACH ROW EXECUTE FUNCTION sync_invoice_payment_totals();
