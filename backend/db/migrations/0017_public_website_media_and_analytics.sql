-- Tenant-owned public website media and privacy-preserving portal analytics.
--
-- Website images use the same upload-time, metadata-stripped derivative
-- pipeline as public logos. Analytics deliberately stores no IP address,
-- user agent, student identifier, name, phone, email, or raw browser token.

ALTER TABLE media_assets
    DROP CONSTRAINT IF EXISTS media_assets_asset_type_check;

ALTER TABLE media_assets
    ADD CONSTRAINT media_assets_asset_type_check
    CHECK (asset_type IN (
        'student_photo', 'registration_photo', 'portfolio', 'homework',
        'sheet_music', 'logo', 'website_image'
    ));

CREATE TABLE IF NOT EXISTS public_analytics_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_name text NOT NULL CHECK (event_name IN (
        'page_view', 'cta_click', 'registration_started', 'registration_submitted'
    )),
    path text NOT NULL DEFAULT '',
    session_hash text NOT NULL,
    campaign jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_public_analytics_tenant_time
    ON public_analytics_events (tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_public_analytics_tenant_event_time
    ON public_analytics_events (tenant_id, event_name, occurred_at DESC);
