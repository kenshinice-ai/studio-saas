-- v10.0.0 — the money ledger, beside the credit ledger.
--
-- The product already keeps a careful account of *lessons*: `credit_accounts`
-- holds a balance, `credit_transactions` records every movement, and
-- `attendance_sessions` links a consumed credit back to the class that consumed
-- it. What it has never kept is an account of *money*.
--
-- These are two ledgers and they must stay two. Buying ten lessons for $600 is
-- one invoice, one payment and one credit top-up; teaching one lesson is one
-- credit consumption and one unit of revenue earned. At any moment a studio has
-- to be able to answer both "what does this family owe" and "how many lessons
-- do they have left", each with its own evidence chain. Studio systems that
-- fail almost always fail by collapsing those two numbers into one.
--
-- Three decisions here are load-bearing:
--
--   1. Money is integer cents. No column in this file is a float.
--   2. An issued invoice is immutable — enforced by a trigger, not by every
--      code path remembering. Corrections happen through credit notes.
--   3. "Overdue" is derived from `due_date`, never stored. A stored status
--      would need a nightly job to stay true, and would be wrong between runs.

-- ── tax codes ────────────────────────────────────────────────────────────
--
-- Rates are basis points, so 10% GST is 1000 and there is no rounding argument
-- with a decimal literal. Which code applies to tuition versus instrument hire
-- is a question for the studio's accountant; this table only stores the answer.

CREATE TABLE IF NOT EXISTS tax_codes (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        text NOT NULL,
    name        text NOT NULL DEFAULT '',
    rate_bp     integer NOT NULL DEFAULT 0 CHECK (rate_bp >= 0 AND rate_bp <= 10000),
    is_default  boolean NOT NULL DEFAULT false,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code),
    UNIQUE (tenant_id, id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tax_codes_one_default
    ON tax_codes (tenant_id) WHERE is_default;

-- ── who gets the invoice ─────────────────────────────────────────────────
--
-- Not the student. Three children in one family are one payer; a primary school
-- booking an incursion is one payer with no students attached at all. Everything
-- downstream — statements, payment allocation, the Xero contact — hangs here.

CREATE TABLE IF NOT EXISTS billing_accounts (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name               text NOT NULL,
    kind               text NOT NULL DEFAULT 'family'
                           CHECK (kind IN ('family', 'organisation')),
    contact_name       text NOT NULL DEFAULT '',
    email              text NOT NULL DEFAULT '',
    mobile             text NOT NULL DEFAULT '',
    company_name       text NOT NULL DEFAULT '',
    abn                text NOT NULL DEFAULT '',
    billing_address    text NOT NULL DEFAULT '',
    payment_terms_days integer NOT NULL DEFAULT 14 CHECK (payment_terms_days >= 0),
    purchase_order_ref text NOT NULL DEFAULT '',
    language           text NOT NULL DEFAULT '' CHECK (language IN ('', 'zh', 'en')),
    status             text NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active', 'archived')),
    note               text NOT NULL DEFAULT '',
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id)
);

CREATE INDEX IF NOT EXISTS idx_billing_accounts_tenant_name
    ON billing_accounts (tenant_id, lower(name));

CREATE TABLE IF NOT EXISTS billing_account_members (
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    billing_account_id uuid NOT NULL,
    student_id         uuid NOT NULL,
    added_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (billing_account_id, student_id),
    CONSTRAINT billing_account_members_account_tenant_fkey
        FOREIGN KEY (tenant_id, billing_account_id)
        REFERENCES billing_accounts (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT billing_account_members_student_tenant_fkey
        FOREIGN KEY (tenant_id, student_id)
        REFERENCES students (tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_billing_account_members_student
    ON billing_account_members (tenant_id, student_id);

-- ── gapless numbering ────────────────────────────────────────────────────
--
-- A Postgres sequence is the wrong tool: it keeps counting through a rolled-back
-- transaction, and an accountant asked to explain the missing invoice number
-- has no good answer. A counter row taken with `UPDATE ... RETURNING` inside the
-- issuing transaction serialises issuance per tenant and never skips.
-- Studio-scale volume makes that lock free in practice.

CREATE TABLE IF NOT EXISTS document_number_sequences (
    tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    kind       text NOT NULL CHECK (kind IN ('invoice', 'credit_note')),
    prefix     text NOT NULL DEFAULT '',
    next_value bigint NOT NULL DEFAULT 1 CHECK (next_value > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, kind)
);

-- ── invoices ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS invoices (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    billing_account_id    uuid NOT NULL,
    term_id               uuid REFERENCES terms(id) ON DELETE SET NULL,
    number                text,
    status                text NOT NULL DEFAULT 'draft'
                              CHECK (status IN ('draft', 'issued', 'part_paid', 'paid', 'void')),
    issue_date            date,
    due_date              date,
    currency              text NOT NULL DEFAULT 'AUD' CHECK (currency ~ '^[A-Z]{3}$'),
    subtotal_cents        integer NOT NULL DEFAULT 0,
    tax_cents             integer NOT NULL DEFAULT 0,
    total_cents           integer NOT NULL DEFAULT 0,
    amount_paid_cents     integer NOT NULL DEFAULT 0 CHECK (amount_paid_cents >= 0),
    amount_credited_cents integer NOT NULL DEFAULT 0 CHECK (amount_credited_cents >= 0),
    -- Derived by the database so it cannot drift from its inputs.
    balance_cents         integer GENERATED ALWAYS AS
                              (total_cents - amount_paid_cents - amount_credited_cents) STORED,
    note                  text NOT NULL DEFAULT '',
    purchase_order_ref    text NOT NULL DEFAULT '',
    issued_at             timestamptz,
    issued_by_user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
    voided_at             timestamptz,
    void_reason           text NOT NULL DEFAULT '',
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT invoices_account_tenant_fkey
        FOREIGN KEY (tenant_id, billing_account_id)
        REFERENCES billing_accounts (tenant_id, id) ON DELETE RESTRICT,
    -- A number exists exactly when the document has been issued.
    CONSTRAINT invoices_number_matches_status
        CHECK ((status = 'draft' AND number IS NULL)
               OR (status <> 'draft' AND number IS NOT NULL)),
    UNIQUE (tenant_id, number),
    UNIQUE (tenant_id, id)
);

CREATE INDEX IF NOT EXISTS idx_invoices_account
    ON invoices (tenant_id, billing_account_id, issue_date DESC);

-- The receivables query: everything still owed, oldest first. Partial because
-- paid, draft and void invoices are noise in every ageing report.
CREATE INDEX IF NOT EXISTS idx_invoices_outstanding
    ON invoices (tenant_id, due_date)
    WHERE status IN ('issued', 'part_paid');

CREATE TABLE IF NOT EXISTS invoice_lines (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id     uuid NOT NULL,
    sort_order     integer NOT NULL DEFAULT 0,
    description    text NOT NULL,
    quantity       numeric(10,2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price_cents integer NOT NULL DEFAULT 0,
    tax_code_id    uuid,
    tax_rate_bp    integer NOT NULL DEFAULT 0 CHECK (tax_rate_bp >= 0 AND tax_rate_bp <= 10000),
    tax_cents      integer NOT NULL DEFAULT 0,
    total_cents    integer NOT NULL DEFAULT 0,
    -- What produced this line, so a charge can be traced back to the lesson,
    -- package or hire it came from.
    source_kind    text NOT NULL DEFAULT 'manual'
                       CHECK (source_kind IN ('manual', 'tuition', 'package', 'lesson',
                                              'rental', 'goods', 'ticket', 'engagement',
                                              'opening_balance')),
    source_id      uuid,
    student_id     uuid,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT invoice_lines_invoice_tenant_fkey
        FOREIGN KEY (tenant_id, invoice_id)
        REFERENCES invoices (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT invoice_lines_tax_code_tenant_fkey
        FOREIGN KEY (tenant_id, tax_code_id)
        REFERENCES tax_codes (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT invoice_lines_student_tenant_fkey
        FOREIGN KEY (tenant_id, student_id)
        REFERENCES students (tenant_id, id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_invoice_lines_invoice
    ON invoice_lines (invoice_id, sort_order);

-- Append-only history of what happened to a document, for the audit trail an
-- accountant expects: issued, sent, viewed, reminded, paid, voided.
CREATE TABLE IF NOT EXISTS invoice_events (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id     uuid NOT NULL,
    event_type     text NOT NULL,
    actor_user_id  uuid REFERENCES users(id) ON DELETE SET NULL,
    detail         jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT invoice_events_invoice_tenant_fkey
        FOREIGN KEY (tenant_id, invoice_id)
        REFERENCES invoices (tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_invoice_events_invoice
    ON invoice_events (invoice_id, occurred_at DESC);

-- ── credit notes ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS credit_notes (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    billing_account_id uuid NOT NULL,
    invoice_id         uuid,
    number             text,
    status             text NOT NULL DEFAULT 'draft'
                           CHECK (status IN ('draft', 'issued', 'void')),
    issue_date         date,
    reason             text NOT NULL DEFAULT '',
    subtotal_cents     integer NOT NULL DEFAULT 0,
    tax_cents          integer NOT NULL DEFAULT 0,
    total_cents        integer NOT NULL DEFAULT 0,
    issued_at          timestamptz,
    issued_by_user_id  uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT credit_notes_account_tenant_fkey
        FOREIGN KEY (tenant_id, billing_account_id)
        REFERENCES billing_accounts (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT credit_notes_invoice_tenant_fkey
        FOREIGN KEY (tenant_id, invoice_id)
        REFERENCES invoices (tenant_id, id) ON DELETE SET NULL,
    UNIQUE (tenant_id, number),
    UNIQUE (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS credit_note_lines (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    credit_note_id   uuid NOT NULL,
    description      text NOT NULL,
    quantity         numeric(10,2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price_cents integer NOT NULL DEFAULT 0,
    tax_rate_bp      integer NOT NULL DEFAULT 0,
    tax_cents        integer NOT NULL DEFAULT 0,
    total_cents      integer NOT NULL DEFAULT 0,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT credit_note_lines_note_tenant_fkey
        FOREIGN KEY (tenant_id, credit_note_id)
        REFERENCES credit_notes (tenant_id, id) ON DELETE CASCADE
);

-- ── recurring billing ────────────────────────────────────────────────────
--
-- Generates *drafts*. A studio confirms and sends; the system never issues an
-- invoice nobody looked at. That middle position was a product decision before
-- this migration and it survives it.

CREATE TABLE IF NOT EXISTS billing_schedules (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    billing_account_id uuid NOT NULL,
    name               text NOT NULL DEFAULT '',
    cadence            text NOT NULL CHECK (cadence IN ('monthly', 'termly')),
    day_of_month       smallint CHECK (day_of_month IS NULL OR day_of_month BETWEEN 1 AND 28),
    source             text NOT NULL DEFAULT 'lesson_series'
                           CHECK (source IN ('lesson_series', 'fixed')),
    fixed_amount_cents integer CHECK (fixed_amount_cents IS NULL OR fixed_amount_cents >= 0),
    tax_code_id        uuid,
    is_active          boolean NOT NULL DEFAULT true,
    last_generated_on  date,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT billing_schedules_account_tenant_fkey
        FOREIGN KEY (tenant_id, billing_account_id)
        REFERENCES billing_accounts (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT billing_schedules_tax_code_tenant_fkey
        FOREIGN KEY (tenant_id, tax_code_id)
        REFERENCES tax_codes (tenant_id, id) ON DELETE SET NULL
);

-- ── immutability, enforced ───────────────────────────────────────────────
--
-- Application code is careful today. The trigger is for the day it is not: a
-- bulk update, a migration script, a well-meaning fix in a console. Once a
-- document carries a number that a customer and an accountant have both seen,
-- its figures stop being editable. Payment progress and voiding are the only
-- movements left, and they have their own columns.

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
       OR NEW.currency IS DISTINCT FROM OLD.currency THEN
        RAISE EXCEPTION
            'Invoice % has been issued; its figures are immutable. Reverse it with a credit note.',
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

-- Lines follow the header: once the header leaves draft, its lines are frozen.
CREATE OR REPLACE FUNCTION assert_issued_invoice_lines_are_immutable()
RETURNS trigger AS $$
DECLARE
    parent_status text;
    parent_id uuid;
BEGIN
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

DROP TRIGGER IF EXISTS trg_invoice_lines_immutable ON invoice_lines;
CREATE TRIGGER trg_invoice_lines_immutable
    BEFORE INSERT OR UPDATE OR DELETE ON invoice_lines
    FOR EACH ROW EXECUTE FUNCTION assert_issued_invoice_lines_are_immutable();
