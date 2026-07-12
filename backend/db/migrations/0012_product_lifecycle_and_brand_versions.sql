-- Product lifecycle, brand publication history, and registration funnel fields.

ALTER TABLE tenants
    DROP CONSTRAINT IF EXISTS tenants_status_check;

ALTER TABLE tenants
    ADD CONSTRAINT tenants_status_check
    CHECK (status IN (
        'lead', 'trial', 'onboarding', 'active', 'past_due',
        'paused', 'cancelled', 'archived', 'deleted'
    ));

CREATE TABLE IF NOT EXISTS tenant_brand_drafts (
    tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    updated_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_brand_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    version_number integer NOT NULL CHECK (version_number > 0),
    payload jsonb NOT NULL,
    published_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    published_at timestamptz NOT NULL DEFAULT now(),
    source_version_id uuid REFERENCES tenant_brand_versions(id) ON DELETE SET NULL,
    UNIQUE (tenant_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_tenant_brand_versions_tenant_published
    ON tenant_brand_versions(tenant_id, version_number DESC);

ALTER TABLE registrations
    ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'standalone_register',
    ADD COLUMN IF NOT EXISTS source_path text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_language text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS campaign jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS assigned_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS first_contacted_at timestamptz,
    ADD COLUMN IF NOT EXISTS next_follow_up_at timestamptz,
    ADD COLUMN IF NOT EXISTS converted_at timestamptz,
    ADD COLUMN IF NOT EXISTS loss_reason text NOT NULL DEFAULT '';

ALTER TABLE registrations
    DROP CONSTRAINT IF EXISTS registrations_status_check;

ALTER TABLE registrations
    ADD CONSTRAINT registrations_status_check
    CHECK (status IN (
        'pending', 'contacted', 'trial_booked', 'waiting', 'approved',
        'converted', 'rejected', 'duplicate', 'lost', 'archived'
    ));

CREATE INDEX IF NOT EXISTS idx_registrations_tenant_follow_up
    ON registrations(tenant_id, next_follow_up_at)
    WHERE status IN ('pending', 'contacted', 'trial_booked', 'waiting');
