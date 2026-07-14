-- Require an auditable consent confirmation before a child/student portfolio
-- item can appear on the unauthenticated public gallery.

ALTER TABLE portfolio_items
    ADD COLUMN IF NOT EXISTS public_consent_at timestamptz,
    ADD COLUMN IF NOT EXISTS public_consent_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS public_consent_note text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_portfolio_public_consent
    ON portfolio_items (tenant_id, visibility, public_consent_at)
    WHERE visibility = 'shared';
