-- v10.1.1 — who is issuing the invoice.
--
-- v10.0.0 built the whole money layer and never asked the studio who it is.
-- `billing_accounts` carries an ABN and an address, but that is the *payer* —
-- the family or the school being invoiced. The seller's identity was nowhere,
-- which means the documents this product issues could not legally be tax
-- invoices in the country it is sold in.
--
-- In Australia a tax invoice must show the supplier's identity and their ABN.
-- Without the ABN the customer cannot claim the GST credit, so an invoice that
-- charges GST and omits it is worse than useless to them — it is a document
-- they have to come back and ask you to reissue.
--
-- Columns, not a settings blob. A misspelt key in jsonb resolves to NULL and
-- the invoice goes out without an ABN; nothing raises, and nobody notices until
-- an accountant does. The same argument as `scheduling_policies` in 0033.

CREATE TABLE IF NOT EXISTS tenant_billing_identity (
    tenant_id      uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,

    -- The entity that is legally issuing the document. Often differs from the
    -- studio's trading name, and it is the legal one that belongs on the
    -- invoice: "Paradise Production Pty Ltd trading as Let's Paint Studio".
    legal_name     text NOT NULL DEFAULT '',
    trading_name   text NOT NULL DEFAULT '',
    abn            text NOT NULL DEFAULT '',

    -- Registration is a fact about the business, not a formatting preference.
    -- An unregistered studio must not issue a document headed "Tax invoice"
    -- and must not put a GST line on it; a registered one must show its ABN.
    gst_registered boolean NOT NULL DEFAULT false,

    address_line1  text NOT NULL DEFAULT '',
    address_line2  text NOT NULL DEFAULT '',
    suburb         text NOT NULL DEFAULT '',
    state          text NOT NULL DEFAULT '',
    postcode       text NOT NULL DEFAULT '',
    country        text NOT NULL DEFAULT 'Australia',

    contact_email  text NOT NULL DEFAULT '',
    contact_phone  text NOT NULL DEFAULT '',
    website        text NOT NULL DEFAULT '',

    -- How the family is meant to pay. Printed on the invoice, so it lives with
    -- the rest of the document's fixed text rather than in a template someone
    -- edits per invoice and eventually gets wrong.
    bank_account_name text NOT NULL DEFAULT '',
    bank_bsb          text NOT NULL DEFAULT '',
    bank_account_no   text NOT NULL DEFAULT '',
    payment_note      text NOT NULL DEFAULT '',

    updated_at     timestamptz NOT NULL DEFAULT now(),

    -- The one rule the database can enforce on its own: if you tell us you are
    -- registered for GST, you have given us the ABN that makes the GST on the
    -- document claimable. Everything else here is presentation and may be blank
    -- while a studio is still setting up.
    CONSTRAINT billing_identity_gst_requires_abn
        CHECK (gst_registered = false OR length(btrim(abn)) > 0)
);

-- Existing tenants keep the row absent rather than getting a fabricated one.
-- A blank identity and no identity are different states: the first says "we
-- asked and they left it empty", the second says "we never asked". The service
-- layer treats a missing row as "not configured yet" and says so.
