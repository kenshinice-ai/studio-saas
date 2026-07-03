-- StudioSaaS PostgreSQL schema v1.
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
    status text NOT NULL CHECK (status IN ('trial', 'active', 'past_due', 'paused', 'cancelled', 'archived', 'deleted')),
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
    role text NOT NULL CHECK (role IN ('super_admin', 'owner', 'staff', 'parent')),
    permissions jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'disabled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS students (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    first_name text NOT NULL,
    last_name text NOT NULL DEFAULT '',
    display_name text NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'trial', 'archived')),
    birthday date,
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
    fee_aud_cents integer NOT NULL DEFAULT 0 CHECK (fee_aud_cents >= 0),
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
    reversed_at timestamptz,
    reversed_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    note text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_tenant_student_attended
    ON attendance_sessions (tenant_id, student_id, attended_at DESC);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_credit_transaction
    ON attendance_sessions (tenant_id, credit_transaction_id)
    WHERE credit_transaction_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS registrations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'duplicate', 'contacted', 'archived')),
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
    updated_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_registrations_tenant_status_submitted
    ON registrations (tenant_id, status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_registrations_tenant_student
    ON registrations (tenant_id, student_id)
    WHERE student_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_registrations_tenant_duplicate
    ON registrations (tenant_id, duplicate_of_registration_id)
    WHERE duplicate_of_registration_id IS NOT NULL;

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
