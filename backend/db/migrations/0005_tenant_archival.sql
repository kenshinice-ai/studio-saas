-- Safe tenant archival before permanent deletion.

ALTER TABLE tenants
    DROP CONSTRAINT IF EXISTS tenants_status_check;

ALTER TABLE tenants
    ADD CONSTRAINT tenants_status_check
    CHECK (status IN ('trial', 'active', 'past_due', 'paused', 'cancelled', 'archived', 'deleted'));

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS archived_at timestamptz,
    ADD COLUMN IF NOT EXISTS archived_by uuid REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS archive_path text,
    ADD COLUMN IF NOT EXISTS deletion_requested_at timestamptz,
    ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

DO $$
BEGIN
    ALTER TABLE tenants
        ADD CONSTRAINT tenants_archived_by_fkey
        FOREIGN KEY (archived_by) REFERENCES users(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

ALTER TABLE subscriptions
    DROP CONSTRAINT IF EXISTS subscriptions_status_check;

ALTER TABLE subscriptions
    ADD CONSTRAINT subscriptions_status_check
    CHECK (status IN ('trialing', 'active', 'past_due', 'paused', 'cancelled', 'archived'));

CREATE TABLE IF NOT EXISTS tenant_archives (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES tenants(id) ON DELETE SET NULL,
    tenant_slug text NOT NULL,
    tenant_name text NOT NULL,
    archive_path text NOT NULL,
    db_snapshot_path text,
    media_archive_path text,
    workspace_archive_path text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_tenant_archives_tenant_created
    ON tenant_archives(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tenant_archives_slug_created
    ON tenant_archives(tenant_slug, created_at DESC);
