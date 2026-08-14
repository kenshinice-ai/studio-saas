-- v10.0.0 — Xero, and the three switches that must never be one switch.
--
-- Products collapse "has bought it", "is connected to it" and "is pushing to it"
-- into a single toggle, and then three ordinary situations break each other:
--
--   * the add-on lapses            → must stop new pushes, keep the connection,
--                                    the id mappings, the error queue and the
--                                    exports. Nothing is deleted.
--   * the studio changes accountant → reconnect and re-confirm the mapping,
--                                    while the entitlement is untouched.
--   * year-end close                → pause pushing for a fortnight without
--                                    touching either of the other two.
--
-- So entitlement lives in `tenant_addons` (platform side, migration 0032),
-- the connection lives here, and pushing is a third state with its own row.
--
-- The pushing switch is a gate, not a checkbox. It cannot be turned on until
-- the account mapping exists, a full cycle has been run against a Xero demo
-- organisation, and the studio has answered the question that actually breaks
-- ledgers: is something else — a Square connector, most often — already
-- syncing the same receipts into the same Xero organisation? Two feeds writing
-- the same money produce two sets of records, in the live ledger, and the
-- cleanup costs more than the manual entry it replaced. The CHECK constraint
-- below makes that gate a property of the database rather than a promise in
-- a service module.

CREATE TABLE IF NOT EXISTS xero_connections (
    tenant_id                uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    org_id                   text NOT NULL DEFAULT '',
    org_name                 text NOT NULL DEFAULT '',
    -- Encrypted by the application before it ever reaches this column.
    refresh_token_encrypted  text NOT NULL DEFAULT '',
    access_token_encrypted   text NOT NULL DEFAULT '',
    access_token_expires_at  timestamptz,
    scopes                   text NOT NULL DEFAULT '',
    status                   text NOT NULL DEFAULT 'connected'
                                 CHECK (status IN ('connected', 'revoked', 'expired', 'error')),
    last_error               text NOT NULL DEFAULT '',
    connected_by_user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
    connected_at             timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);

-- Which revenue account and tax rate each kind of line belongs to. The studio's
-- accountant owns these values; the product only stores and applies them.
CREATE TABLE IF NOT EXISTS xero_account_mappings (
    tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    item_kind    text NOT NULL
                     CHECK (item_kind IN ('tuition', 'package', 'rental', 'goods',
                                          'ticket', 'engagement', 'opening_balance',
                                          'teacher_payable', 'bank', 'clearing')),
    account_code text NOT NULL DEFAULT '',
    tax_type     text NOT NULL DEFAULT '',
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, item_kind)
);

CREATE TABLE IF NOT EXISTS xero_sync_settings (
    tenant_id              uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    push_enabled           boolean NOT NULL DEFAULT false,
    mapping_confirmed_at   timestamptz,
    demo_run_completed_at  timestamptz,
    -- The single-entry question. 'ours_only' means the other connector was
    -- switched off; 'clearing_account' means both remain and our receipts are
    -- routed through a clearing account so they cannot double-count.
    single_entry_decision  text NOT NULL DEFAULT 'not_answered'
                               CHECK (single_entry_decision IN
                                      ('not_answered', 'ours_only', 'clearing_account')),
    clearing_account_code  text NOT NULL DEFAULT '',
    paused_reason          text NOT NULL DEFAULT '',
    last_pushed_at         timestamptz,
    updated_at             timestamptz NOT NULL DEFAULT now(),
    -- The gate itself. Pushing to a live ledger is only representable once the
    -- three preconditions hold; there is no code path, console session or
    -- migration that can set the flag without them.
    CONSTRAINT xero_push_requires_preconditions CHECK (
        push_enabled = false
        OR (mapping_confirmed_at IS NOT NULL
            AND demo_run_completed_at IS NOT NULL
            AND single_entry_decision <> 'not_answered'
            AND (single_entry_decision <> 'clearing_account'
                 OR length(clearing_account_code) > 0))
    )
);

-- Two-way identity map. Together with an idempotency key on the job, this is
-- what makes a retry free: the second attempt finds the link and updates
-- instead of creating a duplicate document in the customer's ledger.
CREATE TABLE IF NOT EXISTS xero_object_links (
    tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    local_kind text NOT NULL
                   CHECK (local_kind IN ('billing_account', 'invoice', 'credit_note',
                                         'payment', 'teacher_payable')),
    local_id   uuid NOT NULL,
    xero_kind  text NOT NULL,
    xero_id    text NOT NULL,
    pushed_at  timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, local_kind, local_id),
    UNIQUE (tenant_id, xero_kind, xero_id)
);

-- Failures are the studio's to see and to retry, not a support ticket. A job
-- that failed keeps its error text and its idempotency key, so replaying it
-- after the mapping is fixed cannot post a second copy.
CREATE TABLE IF NOT EXISTS integration_sync_jobs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    integration     text NOT NULL DEFAULT 'xero' CHECK (integration IN ('xero')),
    local_kind      text NOT NULL,
    local_id        uuid NOT NULL,
    idempotency_key text NOT NULL,
    status          text NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued', 'sent', 'failed', 'skipped')),
    attempts        integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error      text NOT NULL DEFAULT '',
    queued_at       timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz,
    UNIQUE (tenant_id, integration, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_pending
    ON integration_sync_jobs (tenant_id, queued_at)
    WHERE status IN ('queued', 'failed');
