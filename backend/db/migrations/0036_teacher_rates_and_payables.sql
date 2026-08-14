-- v10.0.0 — what a teacher earned, traceable to the sessions that earned it.
--
-- This module stops at a **summary**. It works out what each teacher is owed
-- for a period and from exactly which sessions, lets the teacher confirm it,
-- and hands the figures to whoever runs payroll. It does not withhold tax, does
-- not calculate superannuation, does not lodge anything, and does not pay
-- anybody. Those belong to a registered payroll provider and an accountant;
-- a scheduling system that crossed that line would be answerable for a
-- studio's tax compliance.
--
-- The reason a single hourly rate was never enough: a studio pays per lesson
-- for private tuition, per head for a group class that only pays when it fills,
-- a share of tuition for a senior teacher, and a flat call-out for an ensemble
-- rehearsal or a school incursion. Those are five different bases and studios
-- run several at once, which is why the spreadsheet survives every system that
-- offers only one.

-- ── how a teacher is engaged ─────────────────────────────────────────────
--
-- Load-bearing for the Xero push, not paperwork. A contractor's total becomes
-- a payable bill; an employee's must not, because posting wages as a bill
-- bypasses the payroll accounts and misstates the books. The integration reads
-- this column to decide, and refuses to guess when it is unset.

CREATE TABLE IF NOT EXISTS teacher_engagements (
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    teacher_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    engagement      text NOT NULL DEFAULT 'unset'
                        CHECK (engagement IN ('unset', 'employee', 'contractor')),
    abn             text NOT NULL DEFAULT '',
    payee_reference text NOT NULL DEFAULT '',
    note            text NOT NULL DEFAULT '',
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, teacher_user_id)
);

-- ── rates ────────────────────────────────────────────────────────────────
--
-- Effective-dated. Raising a rate must never rewrite what was already settled,
-- so a session stores the rate it was computed with (below) and this table is
-- only ever consulted for sessions that have not been locked yet.

CREATE TABLE IF NOT EXISTS teacher_pay_rates (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    teacher_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Null course means "this teacher's default rate".
    course_id       uuid REFERENCES courses(id) ON DELETE CASCADE,
    basis           text NOT NULL
                        CHECK (basis IN ('per_lesson', 'per_hour', 'per_head',
                                         'percent_of_tuition', 'per_session')),
    amount_cents    integer CHECK (amount_cents IS NULL OR amount_cents >= 0),
    percent_bp      integer CHECK (percent_bp IS NULL OR (percent_bp >= 0 AND percent_bp <= 10000)),
    effective_from  date NOT NULL DEFAULT CURRENT_DATE,
    effective_to    date,
    note            text NOT NULL DEFAULT '',
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    -- The basis decides which figure is meaningful; storing both, or neither,
    -- is how a pay run silently produces zeros.
    CONSTRAINT teacher_pay_rates_figure_matches_basis CHECK (
        (basis = 'percent_of_tuition' AND percent_bp IS NOT NULL AND amount_cents IS NULL)
        OR (basis <> 'percent_of_tuition' AND amount_cents IS NOT NULL AND percent_bp IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_teacher_pay_rates_lookup
    ON teacher_pay_rates (tenant_id, teacher_user_id, course_id, effective_from DESC);

-- ── pay periods ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS teacher_pay_periods (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    teacher_user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period_start       date NOT NULL,
    period_end         date NOT NULL,
    status             text NOT NULL DEFAULT 'open'
                           CHECK (status IN ('open', 'confirmed', 'exported')),
    sessions_cents     integer NOT NULL DEFAULT 0,
    adjustments_cents  integer NOT NULL DEFAULT 0,
    total_cents        integer GENERATED ALWAYS AS
                           (sessions_cents + adjustments_cents) STORED,
    -- The teacher's own acknowledgement, captured before anybody is paid.
    -- Disputes belong before the money moves, not after.
    confirmed_at       timestamptz,
    confirmed_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    exported_at        timestamptz,
    note               text NOT NULL DEFAULT '',
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CHECK (period_end >= period_start),
    UNIQUE (tenant_id, teacher_user_id, period_start, period_end),
    UNIQUE (tenant_id, id)
);

CREATE INDEX IF NOT EXISTS idx_teacher_pay_periods_open
    ON teacher_pay_periods (tenant_id, period_end DESC)
    WHERE status = 'open';

CREATE TABLE IF NOT EXISTS teacher_pay_adjustments (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    period_id          uuid NOT NULL,
    label              text NOT NULL,
    -- Signed: a deduction is a negative adjustment rather than a second kind.
    amount_cents       integer NOT NULL,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT teacher_pay_adjustments_period_tenant_fkey
        FOREIGN KEY (tenant_id, period_id)
        REFERENCES teacher_pay_periods (tenant_id, id) ON DELETE CASCADE
);

-- ── the sessions themselves ──────────────────────────────────────────────
--
-- One row per taught session, carrying a frozen copy of the rate that produced
-- the figure. Freezing is what lets a studio raise a rate mid-year without
-- rewriting history, and what lets a teacher's confirmed period stay confirmed.

CREATE TABLE IF NOT EXISTS teaching_sessions (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    teacher_user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id            uuid REFERENCES courses(id) ON DELETE SET NULL,
    occurred_on          date NOT NULL,
    start_time           time,
    duration_minutes     integer NOT NULL DEFAULT 0 CHECK (duration_minutes >= 0),
    student_count        integer NOT NULL DEFAULT 1 CHECK (student_count >= 0),
    -- Where the session came from, so every figure is traceable to a record a
    -- human made rather than to a nightly job nobody watched.
    source               text NOT NULL DEFAULT 'roster'
                             CHECK (source IN ('roster', 'attendance', 'series',
                                               'schedule', 'manual')),
    series_id            uuid REFERENCES lesson_series(id) ON DELETE SET NULL,
    schedule_id          uuid REFERENCES class_schedules(id) ON DELETE SET NULL,
    -- Whether this one is paid at all: a studio cancellation usually is not,
    -- a late student cancellation usually is. Written from the scheduling
    -- policy at the time, never inferred later.
    counts_for_pay       boolean NOT NULL DEFAULT true,
    rate_basis           text CHECK (rate_basis IS NULL OR rate_basis IN
                             ('per_lesson', 'per_hour', 'per_head',
                              'percent_of_tuition', 'per_session')),
    rate_amount_cents    integer,
    rate_percent_bp      integer,
    tuition_basis_cents  integer NOT NULL DEFAULT 0,
    amount_cents         integer NOT NULL DEFAULT 0,
    period_id            uuid,
    locked_at            timestamptz,
    note                 text NOT NULL DEFAULT '',
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT teaching_sessions_period_tenant_fkey
        FOREIGN KEY (tenant_id, period_id)
        REFERENCES teacher_pay_periods (tenant_id, id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_teaching_sessions_teacher_date
    ON teaching_sessions (tenant_id, teacher_user_id, occurred_on DESC);

CREATE INDEX IF NOT EXISTS idx_teaching_sessions_period
    ON teaching_sessions (period_id)
    WHERE period_id IS NOT NULL;

-- A session may only be counted into one period once, and re-running the
-- collector must update rather than duplicate. The natural key is the teacher,
-- the day and what produced it.
CREATE UNIQUE INDEX IF NOT EXISTS idx_teaching_sessions_natural_key
    ON teaching_sessions (tenant_id, teacher_user_id, occurred_on,
                          COALESCE(series_id, '00000000-0000-0000-0000-000000000000'::uuid),
                          COALESCE(schedule_id, '00000000-0000-0000-0000-000000000000'::uuid),
                          COALESCE(start_time, '00:00'::time))
    WHERE source <> 'manual';

-- A confirmed period's sessions are frozen: the figures a teacher signed off
-- must still be the figures a month later.
CREATE OR REPLACE FUNCTION assert_locked_teaching_session_is_immutable()
RETURNS trigger AS $$
BEGIN
    IF OLD.locked_at IS NOT NULL
       AND (NEW.amount_cents IS DISTINCT FROM OLD.amount_cents
            OR NEW.counts_for_pay IS DISTINCT FROM OLD.counts_for_pay
            OR NEW.rate_basis IS DISTINCT FROM OLD.rate_basis
            OR NEW.rate_amount_cents IS DISTINCT FROM OLD.rate_amount_cents
            OR NEW.rate_percent_bp IS DISTINCT FROM OLD.rate_percent_bp) THEN
        RAISE EXCEPTION
            'Teaching session % belongs to a confirmed pay period; correct it with an adjustment on the next period.',
            OLD.id
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_teaching_sessions_locked ON teaching_sessions;
CREATE TRIGGER trg_teaching_sessions_locked
    BEFORE UPDATE ON teaching_sessions
    FOR EACH ROW EXECUTE FUNCTION assert_locked_teaching_session_is_immutable();
