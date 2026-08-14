-- v10.0.0 — entitlements that do not belong to a plan.
--
-- Until now the only thing a tenant could be entitled to was whatever its plan
-- bundled, and `plans.features` was read in exactly one place: the plan-change
-- preview that shows an operator which capabilities would light up or go dark.
-- Nothing enforced it.
--
-- The money layer needs two different shapes of entitlement:
--
--   * bundled by tier   — invoicing, payments, the parent calendar feed;
--   * bought per tenant — Xero, on any tier.
--
-- The second shape cannot live in `plans.features`. Plans are shared rows: a
-- studio on Starter that buys the Xero connection must not drag every other
-- Starter tenant along with it, and "available on any tier" degrades into
-- "change your plan" the moment the two are stored in the same place.
--
-- So: plan features stay where they are, and this table carries what a specific
-- tenant has been granted. Effective entitlement is the union, resolved in one
-- place (`studiosaas.services.entitlements`), with standalone deployments
-- answering "yes" to everything because there is nobody to bill.
--
-- Revoking an add-on closes the door to *new* work. It never deletes a row and
-- never blocks a financial write — an unpaid Xero add-on stops new pushes and
-- leaves the connection, the id mappings and the error queue intact, because an
-- invoice is a legal document rather than a quota resource.

CREATE TABLE IF NOT EXISTS tenant_addons (
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    addon_key          text NOT NULL CHECK (addon_key ~ '^[a-z][a-z0-9_]{1,48}$'),
    status             text NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active', 'suspended', 'expired')),
    granted_at         timestamptz NOT NULL DEFAULT now(),
    granted_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    expires_at         timestamptz,
    note               text NOT NULL DEFAULT '',
    updated_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, addon_key)
);

-- The resolver asks one question on every gated request: which add-ons are live
-- for this tenant right now. A partial index keeps that answer cheap and keeps
-- expired grants — which are kept for the audit trail — out of the hot path.
CREATE INDEX IF NOT EXISTS idx_tenant_addons_active
    ON tenant_addons (tenant_id)
    WHERE status = 'active';

COMMENT ON TABLE tenant_addons IS
    'Per-tenant entitlements bought independently of the plan. Union with '
    'plans.features gives the effective feature set; standalone mode is all-on.';
