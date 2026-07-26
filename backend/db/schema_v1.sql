-- StudioSaaS PostgreSQL schema v1.
-- REQUIRES PostgreSQL 16+ (pg_input_is_valid, see the daily roster backfill
-- around line ~582; same floor as migration 0016 and docs/Database.md).
-- All tenant-owned business tables include tenant_id. Application code must
-- always bind tenant-scoped queries to a resolved tenant context.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL UNIQUE,
    name text NOT NULL,
    monthly_price_aud integer NOT NULL CHECK (monthly_price_aud >= 0),
    student_limit integer NOT NULL CHECK (student_limit > 0),
    user_limit integer NOT NULL CHECK (user_limit > 0),
    storage_limit_mb integer NOT NULL CHECK (storage_limit_mb > 0),
    features jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
    status text NOT NULL CHECK (status IN ('lead', 'trial', 'onboarding', 'active', 'past_due', 'paused', 'cancelled', 'archived', 'deleted')),
    plan_code text NOT NULL REFERENCES plans(code),
    primary_color text NOT NULL DEFAULT '#312e81',
    secondary_color text NOT NULL DEFAULT '#6366f1',
    logo_asset_id uuid,
    welcome_message text NOT NULL DEFAULT '',
    contact_phone text NOT NULL DEFAULT '',
    contact_email text NOT NULL DEFAULT '',
    address text NOT NULL DEFAULT '',
    timezone text NOT NULL DEFAULT 'Australia/Melbourne',
    settings jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    archived_at timestamptz,
    archived_by uuid,
    archive_path text,
    deletion_requested_at timestamptz,
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    full_name text NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    last_login_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    ALTER TABLE tenants
        ADD CONSTRAINT tenants_archived_by_fkey
        FOREIGN KEY (archived_by) REFERENCES users(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

CREATE TABLE IF NOT EXISTS memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('super_admin', 'owner', 'manager', 'teacher', 'front_desk', 'staff', 'parent')),
    permissions jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'disabled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS memberships_platform_user_uniq
    ON memberships (user_id)
    WHERE tenant_id IS NULL;

CREATE TABLE IF NOT EXISTS password_setup_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_password_setup_tokens_user
    ON password_setup_tokens(user_id);

CREATE TABLE IF NOT EXISTS students (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    first_name text NOT NULL,
    last_name text NOT NULL DEFAULT '',
    display_name text NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'trial', 'archived')),
    birthday date,
    enrolled_on date DEFAULT CURRENT_DATE,
    student_photo_asset_id uuid,
    parent_name text NOT NULL DEFAULT '',
    mobile text NOT NULL DEFAULT '',
    email text NOT NULL DEFAULT '',
    wechat text NOT NULL DEFAULT '',
    tags text[] NOT NULL DEFAULT ARRAY[]::text[],
    notes text NOT NULL DEFAULT '',
    source_legacy_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_students_tenant_status ON students(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_students_tenant_name ON students(tenant_id, lower(display_name));
CREATE UNIQUE INDEX IF NOT EXISTS idx_students_tenant_legacy_id
    ON students(tenant_id, source_legacy_id)
    WHERE source_legacy_id IS NOT NULL AND source_legacy_id <> '';

CREATE TABLE IF NOT EXISTS courses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text NOT NULL DEFAULT '',
    category text NOT NULL DEFAULT '',
    age_range text NOT NULL DEFAULT '',
    duration_minutes integer NOT NULL DEFAULT 60 CHECK (duration_minutes > 0),
    credit_unit text NOT NULL DEFAULT 'credits',
    default_credit_debit numeric(8,2) NOT NULL DEFAULT 1 CHECK (default_credit_debit > 0),
    price_aud_cents integer NOT NULL DEFAULT 0 CHECK (price_aud_cents >= 0),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS packages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    course_id uuid REFERENCES courses(id) ON DELETE SET NULL,
    name text NOT NULL,
    credits numeric(8,2) NOT NULL CHECK (credits > 0),
    price_aud_cents integer NOT NULL CHECK (price_aud_cents >= 0),
    expires_after_days integer CHECK (expires_after_days IS NULL OR expires_after_days > 0),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS class_schedules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    course_id uuid REFERENCES courses(id) ON DELETE SET NULL,
    label text NOT NULL DEFAULT '',
    weekday smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time time NOT NULL DEFAULT '16:00',
    duration_minutes integer NOT NULL DEFAULT 60 CHECK (duration_minutes > 0),
    capacity integer NOT NULL DEFAULT 10 CHECK (capacity > 0),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_class_schedules_tenant_weekday
    ON class_schedules (tenant_id, weekday)
    WHERE is_active;

CREATE TABLE IF NOT EXISTS class_schedule_students (
    schedule_id uuid NOT NULL REFERENCES class_schedules(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    added_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (schedule_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_class_schedule_students_tenant_student
    ON class_schedule_students (tenant_id, student_id);

CREATE TABLE IF NOT EXISTS credit_accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id uuid REFERENCES courses(id) ON DELETE SET NULL,
    balance numeric(10,2) NOT NULL DEFAULT 0,
    low_balance_threshold numeric(10,2) NOT NULL DEFAULT 2,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, student_id, course_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_accounts_default_account
    ON credit_accounts (tenant_id, student_id)
    WHERE course_id IS NULL;

CREATE TABLE IF NOT EXISTS credit_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    account_id uuid REFERENCES credit_accounts(id) ON DELETE SET NULL,
    actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    transaction_type text NOT NULL CHECK (transaction_type IN ('purchase', 'consume', 'adjustment', 'refund', 'expire', 'migration')),
    amount numeric(10,2) NOT NULL,
    balance_after numeric(10,2),
    fee_aud_cents integer NOT NULL DEFAULT 0
        CHECK (fee_aud_cents BETWEEN -100000000 AND 100000000),
    note text NOT NULL DEFAULT '',
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_tenant_student ON credit_transactions(tenant_id, student_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS attendance_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id uuid REFERENCES courses(id) ON DELETE SET NULL,
    actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    credit_transaction_id uuid REFERENCES credit_transactions(id) ON DELETE SET NULL,
    reversal_credit_transaction_id uuid REFERENCES credit_transactions(id) ON DELETE SET NULL,
    attended_at timestamptz NOT NULL DEFAULT now(),
    class_date date DEFAULT (now() AT TIME ZONE 'Australia/Melbourne')::date,
    reversed_at timestamptz,
    reversed_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    note text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_tenant_student_attended
    ON attendance_sessions (tenant_id, student_id, attended_at DESC);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_credit_transaction
    ON attendance_sessions (tenant_id, credit_transaction_id)
    WHERE credit_transaction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_tenant_class_date
    ON attendance_sessions (tenant_id, class_date DESC);

CREATE TABLE IF NOT EXISTS registrations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'contacted', 'trial_booked', 'waiting', 'approved', 'converted', 'rejected', 'duplicate', 'lost', 'archived')),
    first_name text NOT NULL,
    last_name text NOT NULL DEFAULT '',
    parent_name text NOT NULL DEFAULT '',
    mobile text NOT NULL DEFAULT '',
    email text NOT NULL DEFAULT '',
    message text NOT NULL DEFAULT '',
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    student_id uuid REFERENCES students(id) ON DELETE SET NULL,
    duplicate_of_registration_id uuid REFERENCES registrations(id) ON DELETE SET NULL,
    reviewed_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at timestamptz,
    review_note text NOT NULL DEFAULT '',
    submitted_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    source text NOT NULL DEFAULT 'standalone_register',
    source_path text NOT NULL DEFAULT '',
    source_language text NOT NULL DEFAULT '',
    campaign jsonb NOT NULL DEFAULT '{}'::jsonb,
    assigned_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    first_contacted_at timestamptz,
    next_follow_up_at timestamptz,
    converted_at timestamptz,
    loss_reason text NOT NULL DEFAULT '',
    privacy_consent_at timestamptz,
    privacy_notice_version text NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_registrations_tenant_status_submitted
    ON registrations (tenant_id, status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_registrations_tenant_student
    ON registrations (tenant_id, student_id)
    WHERE student_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_registrations_tenant_duplicate
    ON registrations (tenant_id, duplicate_of_registration_id)
    WHERE duplicate_of_registration_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_registrations_tenant_follow_up
    ON registrations(tenant_id, next_follow_up_at)
    WHERE status IN ('pending', 'contacted', 'trial_booked', 'waiting');
CREATE INDEX IF NOT EXISTS idx_registrations_tenant_privacy_consent
    ON registrations (tenant_id, privacy_consent_at DESC);

CREATE TABLE IF NOT EXISTS media_assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    owner_student_id uuid REFERENCES students(id) ON DELETE SET NULL,
    asset_type text NOT NULL DEFAULT 'portfolio'
        CHECK (asset_type IN ('student_photo', 'registration_photo', 'portfolio', 'homework', 'sheet_music', 'logo')),
    storage_provider text NOT NULL DEFAULT 'local' CHECK (storage_provider IN ('local', 's3')),
    storage_key text NOT NULL,
    original_filename text NOT NULL DEFAULT '',
    mime_type text NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    checksum_sha256 text NOT NULL DEFAULT '',
    visibility text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'public_token')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, storage_key)
);

DO $$
BEGIN
    ALTER TABLE students
        ADD CONSTRAINT students_student_photo_asset_id_fkey
        FOREIGN KEY (student_photo_asset_id) REFERENCES media_assets(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

CREATE TABLE IF NOT EXISTS portfolio_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    media_asset_id uuid NOT NULL REFERENCES media_assets(id) ON DELETE RESTRICT,
    title text NOT NULL DEFAULT '',
    description text NOT NULL DEFAULT '',
    artwork_date date,
    visibility text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'shared')),
    public_consent_at timestamptz,
    public_consent_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    public_consent_note text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS share_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id uuid REFERENCES students(id) ON DELETE CASCADE,
    portfolio_item_id uuid REFERENCES portfolio_items(id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    scope text NOT NULL CHECK (scope IN ('student_portfolio', 'portfolio_item', 'balance_query')),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS email_templates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    template_key text NOT NULL,
    subject text NOT NULL,
    body text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, template_key)
);

CREATE TABLE IF NOT EXISTS notification_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel text NOT NULL CHECK (channel IN ('email', 'sms', 'whatsapp', 'push')),
    recipient text NOT NULL,
    subject text NOT NULL DEFAULT '',
    status text NOT NULL CHECK (status IN ('queued', 'sent', 'failed')),
    provider_message_id text NOT NULL DEFAULT '',
    error_message text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES tenants(id) ON DELETE SET NULL,
    actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL DEFAULT '',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    ip_address inet,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_created ON audit_logs(tenant_id, created_at DESC);

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

CREATE TABLE IF NOT EXISTS subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    plan_code text NOT NULL REFERENCES plans(code),
    status text NOT NULL CHECK (status IN ('trialing', 'active', 'past_due', 'paused', 'cancelled', 'archived')),
    starts_at timestamptz NOT NULL DEFAULT now(),
    ends_at timestamptz,
    trial_ends_at timestamptz,
    current_period_ends_at timestamptz,
    external_customer_id text NOT NULL DEFAULT '',
    external_subscription_id text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_usage (
    tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    student_count integer NOT NULL DEFAULT 0 CHECK (student_count >= 0),
    user_count integer NOT NULL DEFAULT 0 CHECK (user_count >= 0),
    storage_used_mb integer NOT NULL DEFAULT 0 CHECK (storage_used_mb >= 0),
    calculated_at timestamptz NOT NULL DEFAULT now()
);

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
-- No extra (tenant_id, version_number DESC) index: the UNIQUE constraint
-- above serves the same scans (btree reads both directions; the DESC-only
-- duplicate was dropped in migration 0020).

INSERT INTO plans (code, name, monthly_price_aud, student_limit, user_limit, storage_limit_mb, features)
VALUES
    ('starter', 'Starter', 49, 100, 2, 5120, '{"public_registration": true, "portfolio": true}'::jsonb),
    ('studio', 'Studio', 99, 500, 8, 30720, '{"public_registration": true, "portfolio": true, "email_templates": true, "data_export": true}'::jsonb),
    ('growth', 'Growth', 199, 1500, 20, 102400, '{"public_registration": true, "portfolio": true, "email_templates": true, "data_export": true, "priority_support": true}'::jsonb)
ON CONFLICT (code) DO NOTHING;

ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS starts_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS ends_at timestamptz;

-- ── 0015–0017 increments (kept in sync with db/migrations/) ─────────────────
-- When a migration adds tenant-scoped objects, mirror them here AND in
-- studiosaas/services/tenant_archive.py SNAPSHOT_TABLES. Both inventories
-- drifted once (0015–0017) and the gap only surfaced in an audit.

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
-- No extra (tenant_id, media_asset_id, variant) index: the UNIQUE constraint
-- above already provides it (redundant copy dropped in migration 0020).

-- Canonical tenant-scoped daily roster entries.
--
-- Recurring class schedules remain templates. This table records explicit
-- date-level additions and their reversible cancellation state, replacing the
-- mutable legacy JSON roster board as the source of truth.

DO $$
BEGIN
    ALTER TABLE students
        ADD CONSTRAINT students_tenant_id_id_unique UNIQUE (tenant_id, id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN
    -- ADD CONSTRAINT ... UNIQUE raises duplicate_table (42P07, from the
    -- backing index) on re-run; duplicate_object kept for completeness.
    NULL;
END $$;

CREATE TABLE IF NOT EXISTS daily_roster_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    roster_date date NOT NULL,
    student_id uuid NOT NULL,
    source text NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'group', 'profile', 'import')),
    status text NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'makeup', 'cancelled')),
    status_before_cancel text
        CHECK (status_before_cancel IS NULL OR status_before_cancel IN ('scheduled', 'makeup')),
    note text NOT NULL DEFAULT '',
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    cancelled_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    cancelled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT daily_roster_student_tenant_fkey
        FOREIGN KEY (tenant_id, student_id)
        REFERENCES students(tenant_id, id) ON DELETE CASCADE,
    UNIQUE (tenant_id, roster_date, student_id)
);

CREATE INDEX IF NOT EXISTS idx_daily_roster_tenant_date_status
    ON daily_roster_entries (tenant_id, roster_date, status, created_at);
CREATE INDEX IF NOT EXISTS idx_daily_roster_tenant_student
    ON daily_roster_entries (tenant_id, student_id, roster_date DESC);

-- Import existing CMS roster JSON once. IDs are joined through the tenant and
-- invalid/stale student IDs are skipped, preserving the tenant boundary.
INSERT INTO daily_roster_entries (
    tenant_id, roster_date, student_id, source, status, note
)
SELECT t.id, valid.roster_day, s.id, 'import', 'scheduled',
       'Migrated from legacy CMS roster'
FROM tenants t
CROSS JOIN LATERAL jsonb_each(
    CASE
        WHEN jsonb_typeof(t.settings #> '{legacy_cms,rosters}') = 'object'
        THEN t.settings #> '{legacy_cms,rosters}'
        ELSE '{}'::jsonb
    END
) AS board(roster_date, student_ids)
CROSS JOIN LATERAL (
    SELECT CASE
        WHEN board.roster_date ~ '^\d{4}-\d{2}-\d{2}$'
         AND pg_input_is_valid(board.roster_date, 'date')
        THEN board.roster_date::date
        ELSE NULL
    END AS roster_day
) AS valid
CROSS JOIN LATERAL jsonb_array_elements_text(
    CASE WHEN jsonb_typeof(board.student_ids) = 'array'
         THEN board.student_ids ELSE '[]'::jsonb END
) AS member(student_id)
JOIN students s
  ON s.tenant_id = t.id
 AND s.id::text = member.student_id
WHERE valid.roster_day IS NOT NULL
ON CONFLICT (tenant_id, roster_date, student_id) DO NOTHING;

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

-- 0011's consent index (was missing here) + 0019 stability indexes.
CREATE INDEX IF NOT EXISTS idx_portfolio_public_consent
    ON portfolio_items (tenant_id, visibility, public_consent_at)
    WHERE visibility = 'shared';


CREATE INDEX IF NOT EXISTS idx_portfolio_items_tenant_student
    ON portfolio_items (tenant_id, student_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_logs_tenant_created
    ON notification_logs (tenant_id, created_at DESC);

DROP INDEX IF EXISTS credit_accounts_general_uniq;
