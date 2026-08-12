-- v9.9.0: a studio can change its public address without losing the old one.
--
-- A slug is printed on flyers and encoded into QR codes months before anyone
-- thinks about renaming, so an address is never really replaced — it is only
-- superseded.  This table is the register of every address the platform has
-- ever issued: the current one for each tenant, plus every retired one, which
-- keeps answering forever as a 301.
--
-- `ON DELETE SET NULL` rather than CASCADE is the load-bearing choice.  When a
-- tenant is deleted the row stays behind as a tombstone, so its addresses are
-- never handed to a different studio.  Recycling one would quietly redirect a
-- closed studio's printed QR codes into somebody else's business.

CREATE TABLE IF NOT EXISTS tenant_slug_aliases (
    slug        text PRIMARY KEY CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
    tenant_id   uuid REFERENCES tenants(id) ON DELETE SET NULL,
    is_current  boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    retired_at  timestamptz
);

-- One current address per tenant, enforced by the database rather than by
-- remembering to.  Same idiom as idx_class_bookings_one_pending_per_phone.
CREATE UNIQUE INDEX IF NOT EXISTS idx_tenant_slug_aliases_one_current
    ON tenant_slug_aliases (tenant_id) WHERE is_current;

CREATE INDEX IF NOT EXISTS idx_tenant_slug_aliases_tenant
    ON tenant_slug_aliases (tenant_id);

-- Every existing address becomes its tenant's current one. Idempotent: a
-- second run finds the rows already there.
INSERT INTO tenant_slug_aliases (slug, tenant_id, is_current)
SELECT slug, id, true FROM tenants
ON CONFLICT (slug) DO NOTHING;

-- NULL means "never changed", which is not the same as "changed at creation".
-- Backfilling this with created_at would lock every existing studio out of
-- its first rename for a year.
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS slug_changed_at timestamptz;
