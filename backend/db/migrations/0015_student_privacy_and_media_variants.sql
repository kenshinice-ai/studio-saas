-- Student self-service access, append-only publication consent, and safe
-- derivative media. Every row is tenant-scoped so public sessions and media
-- can never cross a StudioSaaS tenant boundary.

ALTER TABLE students
    ADD COLUMN IF NOT EXISTS access_code_hash text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS access_code_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS access_code_revoked_at timestamptz;

CREATE TABLE IF NOT EXISTS student_access_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    token_hash text NOT NULL,
    created_ip inet,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    UNIQUE (tenant_id, token_hash)
);
CREATE INDEX IF NOT EXISTS idx_student_access_sessions_active
    ON student_access_sessions (tenant_id, token_hash, expires_at)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_student_access_sessions_student
    ON student_access_sessions (tenant_id, student_id, created_at DESC);

CREATE TABLE IF NOT EXISTS student_access_attempts (
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    lookup_hash text NOT NULL,
    ip_address inet NOT NULL,
    failed_count integer NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    window_started_at timestamptz NOT NULL DEFAULT now(),
    locked_until timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, lookup_hash, ip_address)
);

CREATE TABLE IF NOT EXISTS student_publication_consent_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('confirmed', 'withdrawn')),
    consent_by text NOT NULL DEFAULT '',
    relationship text NOT NULL DEFAULT '',
    consent_method text NOT NULL DEFAULT '',
    notice_version text NOT NULL DEFAULT '',
    note text NOT NULL DEFAULT '',
    actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    source_registration_id uuid REFERENCES registrations(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_student_publication_consent_latest
    ON student_publication_consent_events (tenant_id, student_id, created_at DESC, id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_student_publication_consent_registration
    ON student_publication_consent_events (tenant_id, source_registration_id)
    WHERE source_registration_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS media_variants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    media_asset_id uuid NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
    variant text NOT NULL CHECK (variant IN ('display', 'thumb')),
    storage_key text NOT NULL,
    mime_type text NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    checksum_sha256 text NOT NULL,
    pixel_width integer NOT NULL CHECK (pixel_width > 0),
    pixel_height integer NOT NULL CHECK (pixel_height > 0),
    metadata_sanitized boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, media_asset_id, variant)
);
CREATE INDEX IF NOT EXISTS idx_media_variants_asset
    ON media_variants (tenant_id, media_asset_id, variant);
