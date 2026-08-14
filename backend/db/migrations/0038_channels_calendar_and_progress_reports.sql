-- v10.0.0 — three things that all answer "how does a family hear from us".
--
-- Grouped because they are one decision, not three. A studio replacing a
-- product that bundles unlimited SMS is about to start paying per message, and
-- the honest answer is not "buy more messages" — it is to stop sending the ones
-- a calendar can deliver for free, and keep paying only for the ones that must
-- arrive and must be evidenced.
--
-- The split this migration encodes:
--
--   calendar subscription  routine lesson reminders — free, forever, and the
--                          parent's own phone decides when to nudge them
--   SMS                    invoices, overdue notices, same-day cancellations
--   email                  statements, progress reports, anything with a PDF
--
-- One caveat is designed in rather than discovered later: calendar clients poll
-- on their own schedule and Google can take hours. A subscription feed is
-- therefore a fine channel for "your lessons this term" and a **useless** one
-- for "your lesson in two hours is cancelled". The routing table below exists
-- so that distinction is configuration a studio can see, not a rule buried in
-- a service module.

-- ── channel configuration ────────────────────────────────────────────────
--
-- The SMS account belongs to the tenant and is billed to the tenant. We are not
-- a reseller and take no margin, so there is no credit balance here — only the
-- credentials to send and the quota that stops one wrong click sending
-- hundreds of messages.

CREATE TABLE IF NOT EXISTS notification_channels (
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel             text NOT NULL CHECK (channel IN ('email', 'sms')),
    provider            text NOT NULL DEFAULT '',
    sender_identity     text NOT NULL DEFAULT '',
    config              jsonb NOT NULL DEFAULT '{}'::jsonb,
    secret_encrypted    text NOT NULL DEFAULT '',
    is_active           boolean NOT NULL DEFAULT false,
    -- A ceiling, not a budget: crossing it blocks the send and tells somebody.
    monthly_quota       integer CHECK (monthly_quota IS NULL OR monthly_quota >= 0),
    quota_alert_at      integer CHECK (quota_alert_at IS NULL OR quota_alert_at >= 0),
    unit_cost_cents     integer NOT NULL DEFAULT 0 CHECK (unit_cost_cents >= 0),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, channel)
);

-- Which events go out on which channels. Rows are per tenant so a studio with
-- a full-time person on WeChat can route routine traffic away from SMS without
-- asking us to change code.
CREATE TABLE IF NOT EXISTS notification_routes (
    tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_key  text NOT NULL,
    channels   text[] NOT NULL DEFAULT ARRAY[]::text[],
    is_active  boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, event_key),
    CONSTRAINT notification_routes_known_channels
        CHECK (channels <@ ARRAY['email', 'sms']::text[])
);

-- `notification_logs` already existed with the right shape for one message on
-- one channel. What it could not answer was "which event was this, what did it
-- cost, and what did it belong to" — the three questions a studio asks when the
-- SMS bill arrives.
ALTER TABLE notification_logs
    ADD COLUMN IF NOT EXISTS event_key text NOT NULL DEFAULT '';
ALTER TABLE notification_logs
    ADD COLUMN IF NOT EXISTS language text NOT NULL DEFAULT '';
ALTER TABLE notification_logs
    ADD COLUMN IF NOT EXISTS body_preview text NOT NULL DEFAULT '';
ALTER TABLE notification_logs
    ADD COLUMN IF NOT EXISTS cost_cents integer NOT NULL DEFAULT 0;
ALTER TABLE notification_logs
    ADD COLUMN IF NOT EXISTS attempts integer NOT NULL DEFAULT 0;
ALTER TABLE notification_logs
    ADD COLUMN IF NOT EXISTS sent_at timestamptz;
ALTER TABLE notification_logs
    ADD COLUMN IF NOT EXISTS related_kind text NOT NULL DEFAULT '';
ALTER TABLE notification_logs
    ADD COLUMN IF NOT EXISTS related_id uuid;

-- The monthly usage and spend view the cost dashboard reads.
CREATE INDEX IF NOT EXISTS idx_notification_logs_tenant_channel_month
    ON notification_logs (tenant_id, channel, created_at DESC);

-- Opt-out is per recipient and per channel, and it outlives the student record
-- it came from — which is why it is keyed by the address rather than by a
-- foreign key.
CREATE TABLE IF NOT EXISTS notification_optouts (
    tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel    text NOT NULL CHECK (channel IN ('email', 'sms')),
    recipient  text NOT NULL,
    reason     text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, channel, recipient)
);

-- ── calendar subscriptions ───────────────────────────────────────────────
--
-- A family subscribes once and their child's lessons live in their own phone
-- calendar from then on, resyncing when the studio reschedules. The token is
-- stored hashed: the feed URL is the credential, so the database keeps a
-- verifier rather than the secret itself, exactly as student access codes do.
-- Revocation is a timestamp rather than a delete, so a family that loses a
-- phone can be cut off without erasing the record that they were subscribed.

CREATE TABLE IF NOT EXISTS calendar_subscriptions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    scope              text NOT NULL CHECK (scope IN ('family', 'student', 'teacher')),
    billing_account_id uuid,
    student_id         uuid,
    teacher_user_id    uuid REFERENCES users(id) ON DELETE CASCADE,
    token_hash         text NOT NULL UNIQUE,
    label              text NOT NULL DEFAULT '',
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    revoked_at         timestamptz,
    last_fetched_at    timestamptz,
    fetch_count        integer NOT NULL DEFAULT 0,
    CONSTRAINT calendar_subscriptions_account_tenant_fkey
        FOREIGN KEY (tenant_id, billing_account_id)
        REFERENCES billing_accounts (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT calendar_subscriptions_student_tenant_fkey
        FOREIGN KEY (tenant_id, student_id)
        REFERENCES students (tenant_id, id) ON DELETE CASCADE,
    -- Each scope names exactly the subject it is about.
    CONSTRAINT calendar_subscriptions_scope_target CHECK (
        (scope = 'family'  AND billing_account_id IS NOT NULL AND student_id IS NULL AND teacher_user_id IS NULL)
     OR (scope = 'student' AND student_id IS NOT NULL AND billing_account_id IS NULL AND teacher_user_id IS NULL)
     OR (scope = 'teacher' AND teacher_user_id IS NOT NULL AND billing_account_id IS NULL AND student_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_calendar_subscriptions_live
    ON calendar_subscriptions (tenant_id, scope)
    WHERE revoked_at IS NULL;

-- ── progress reports ─────────────────────────────────────────────────────
--
-- The material already accumulates every day: attendance, lesson notes,
-- repertoire, exam progress, and consented media. What was missing was the
-- deliverable, and the discipline around it — a report is drafted from the
-- record, a teacher edits and publishes it, and the studio can see which ones
-- are overdue. A published report is never generated behind a teacher's back.

CREATE TABLE IF NOT EXISTS progress_report_settings (
    tenant_id        uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    cadence_kind     text NOT NULL DEFAULT 'lessons'
                         CHECK (cadence_kind IN ('lessons', 'term', 'off')),
    cadence_lessons  integer NOT NULL DEFAULT 6 CHECK (cadence_lessons > 0),
    include_attendance boolean NOT NULL DEFAULT true,
    include_notes      boolean NOT NULL DEFAULT true,
    include_repertoire boolean NOT NULL DEFAULT true,
    include_exam       boolean NOT NULL DEFAULT true,
    include_media      boolean NOT NULL DEFAULT false,
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS progress_reports (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id       uuid NOT NULL,
    teacher_user_id  uuid REFERENCES users(id) ON DELETE SET NULL,
    term_id          uuid REFERENCES terms(id) ON DELETE SET NULL,
    period_start     date NOT NULL,
    period_end       date NOT NULL,
    status           text NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft', 'published', 'archived')),
    -- The assembled figures, frozen when published so a later change to
    -- attendance cannot silently rewrite a report a parent already read.
    content          jsonb NOT NULL DEFAULT '{}'::jsonb,
    teacher_comment  text NOT NULL DEFAULT '',
    share_token_id   uuid REFERENCES share_tokens(id) ON DELETE SET NULL,
    published_at     timestamptz,
    published_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (period_end >= period_start),
    CONSTRAINT progress_reports_student_tenant_fkey
        FOREIGN KEY (tenant_id, student_id)
        REFERENCES students (tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_progress_reports_student
    ON progress_reports (tenant_id, student_id, period_end DESC);

-- "Which reports are overdue" — the query that turns a service promise on a
-- website into something the studio can actually manage.
CREATE INDEX IF NOT EXISTS idx_progress_reports_drafts
    ON progress_reports (tenant_id, teacher_user_id, period_end)
    WHERE status = 'draft';
