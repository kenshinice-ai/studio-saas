-- Persist proof that a public registration accepted the current privacy notice.

ALTER TABLE registrations
    ADD COLUMN IF NOT EXISTS privacy_consent_at timestamptz,
    ADD COLUMN IF NOT EXISTS privacy_notice_version text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_registrations_tenant_privacy_consent
    ON registrations (tenant_id, privacy_consent_at DESC);
