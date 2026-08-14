-- v10.0.0 — the one-to-one lesson becomes a first-class object.
--
-- `class_schedules` models a *class*: a weekly slot with a capacity and a roster
-- of students attached to it. A private lesson can be squeezed into that shape
-- by setting capacity to 1, and studios have been doing exactly that — but then
-- every question a private teacher actually asks ("move Emma's Tuesday lesson to
-- Thursday this week", "she gave notice, does she get a make-up?") has to be
-- answered by editing a class.
--
-- Private teaching is the largest segment of this market and the natural buyer
-- of the entry tier, so this is a market-access gap rather than a convenience.
--
-- The idiom here is the one `class_schedules` already established: a recurring
-- row is a **template**, and dated deviations live in an exceptions table. What
-- is new is that a deviation now records two decisions that used to live in
-- somebody's head, and that both of them are about money:
--
--   `chargeable`      — does the student still pay for this one?
--   `counts_for_pay`  — does the teacher still get paid for it?
--
-- Those are different questions with different answers. A student who cancels
-- inside the notice window is usually charged *and* the teacher is usually paid.
-- A teacher who cancels is usually neither. Storing one boolean for both is the
-- bug this table exists to prevent.

-- ── terms ────────────────────────────────────────────────────────────────
--
-- Billing periods, progress-report cadence and "expires at end of term" all
-- need the same calendar. One spine, not three.

CREATE TABLE IF NOT EXISTS terms (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name       text NOT NULL,
    starts_on  date NOT NULL,
    ends_on    date NOT NULL,
    is_active  boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_on >= starts_on),
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_terms_tenant_range
    ON terms (tenant_id, starts_on DESC, ends_on DESC);

-- Dates inside a term when nothing runs. Kept separate from the term so a
-- public holiday can be added mid-term without rewriting the term's dates.
CREATE TABLE IF NOT EXISTS term_closures (
    tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    on_date    date NOT NULL,
    label      text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, on_date)
);

-- ── scheduling policy ────────────────────────────────────────────────────
--
-- Deliberately columns rather than a settings blob. These four values decide
-- whether a family is charged and whether a teacher is paid; a typo in a JSON
-- key must not silently resolve to "free lesson for everyone".

CREATE TABLE IF NOT EXISTS scheduling_policies (
    tenant_id                 uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    notice_hours              integer NOT NULL DEFAULT 24 CHECK (notice_hours >= 0),
    makeup_credit_on_notice   boolean NOT NULL DEFAULT true,
    makeup_expiry_days        integer CHECK (makeup_expiry_days IS NULL OR makeup_expiry_days > 0),
    late_absence_chargeable   boolean NOT NULL DEFAULT true,
    late_absence_pays_teacher boolean NOT NULL DEFAULT true,
    studio_cancel_chargeable  boolean NOT NULL DEFAULT false,
    updated_at                timestamptz NOT NULL DEFAULT now()
);

-- ── teacher availability ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS teacher_availability (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    teacher_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    weekday         smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time      time NOT NULL,
    end_time        time NOT NULL,
    effective_from  date,
    effective_to    date,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (end_time > start_time)
);

CREATE INDEX IF NOT EXISTS idx_teacher_availability_lookup
    ON teacher_availability (tenant_id, teacher_user_id, weekday);

-- ── the recurring private lesson ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lesson_series (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id       uuid NOT NULL,
    course_id        uuid REFERENCES courses(id) ON DELETE SET NULL,
    teacher_user_id  uuid REFERENCES users(id) ON DELETE SET NULL,
    weekday          smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time       time NOT NULL,
    duration_minutes integer NOT NULL DEFAULT 30 CHECK (duration_minutes > 0),
    room             text NOT NULL DEFAULT '',
    starts_on        date NOT NULL,
    ends_on          date,
    status           text NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active', 'paused', 'ended')),
    paused_from      date,
    paused_to        date,
    -- Null means "use the course price". An override belongs on the series
    -- because a long-standing student's rate is a promise to that family, not
    -- a property of the course.
    price_aud_cents  integer CHECK (price_aud_cents IS NULL OR price_aud_cents >= 0),
    note             text NOT NULL DEFAULT '',
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_on IS NULL OR ends_on >= starts_on),
    -- A series can only ever point at a student of its own tenant. Enforced by
    -- the database rather than by every query remembering to say so; relies on
    -- students_tenant_id_id_unique from migration 0016.
    CONSTRAINT lesson_series_student_tenant_fkey
        FOREIGN KEY (tenant_id, student_id)
        REFERENCES students (tenant_id, id) ON DELETE CASCADE,
    -- Lets dated exceptions carry the same composite-tenant guarantee.
    UNIQUE (tenant_id, id)
);

CREATE INDEX IF NOT EXISTS idx_lesson_series_tenant_weekday
    ON lesson_series (tenant_id, weekday, start_time)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_lesson_series_student
    ON lesson_series (tenant_id, student_id);

CREATE INDEX IF NOT EXISTS idx_lesson_series_teacher
    ON lesson_series (tenant_id, teacher_user_id, weekday)
    WHERE status = 'active';

-- ── dated deviations ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lesson_exceptions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    series_id          uuid NOT NULL,
    on_date            date NOT NULL,
    kind               text NOT NULL
                           CHECK (kind IN ('cancelled_by_student',
                                           'cancelled_by_studio',
                                           'rescheduled',
                                           'makeup')),
    -- Populated for 'rescheduled' and 'makeup'.
    moved_to_date       date,
    moved_to_start_time time,
    teacher_user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
    -- The two decisions this table exists for. Defaults are deliberately NOT
    -- set here: the policy resolver writes them explicitly at creation time so
    -- the stored row records what was decided, not what the column happened to
    -- default to when the policy later changes.
    chargeable          boolean NOT NULL,
    counts_for_pay      boolean NOT NULL,
    makeup_credit_id    uuid,
    reason              text NOT NULL DEFAULT '',
    created_by_user_id  uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT lesson_exceptions_series_tenant_fkey
        FOREIGN KEY (tenant_id, series_id)
        REFERENCES lesson_series (tenant_id, id) ON DELETE CASCADE,
    UNIQUE (series_id, on_date)
);

CREATE INDEX IF NOT EXISTS idx_lesson_exceptions_tenant_date
    ON lesson_exceptions (tenant_id, on_date);

-- ── make-up credits ──────────────────────────────────────────────────────
--
-- A credit is owed to a student, not to a lesson: it survives the series it was
-- earned from, which is the whole point of giving one when a family gives
-- notice. Expiry is a date rather than a flag so "expired" is derivable at read
-- time and no nightly job is required to keep the truth current.

CREATE TABLE IF NOT EXISTS makeup_credits (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id         uuid NOT NULL,
    earned_from_date   date NOT NULL,
    -- Deferrable: this table and lesson_exceptions point at each other, so a
    -- restore that inserts them in either order would trip a foreign key
    -- mid-transaction. Deferring to commit time makes the pair order-free.
    earned_from_exception_id uuid REFERENCES lesson_exceptions(id) ON DELETE SET NULL
                                 DEFERRABLE INITIALLY DEFERRED,
    expires_on         date,
    status             text NOT NULL DEFAULT 'available'
                           CHECK (status IN ('available', 'consumed', 'expired', 'cancelled')),
    consumed_on_date   date,
    consumed_exception_id uuid REFERENCES lesson_exceptions(id) ON DELETE SET NULL
                              DEFERRABLE INITIALLY DEFERRED,
    reason             text NOT NULL DEFAULT '',
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT makeup_credits_student_tenant_fkey
        FOREIGN KEY (tenant_id, student_id)
        REFERENCES students (tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_makeup_credits_available
    ON makeup_credits (tenant_id, student_id)
    WHERE status = 'available';

DO $$
BEGIN
    ALTER TABLE lesson_exceptions
        ADD CONSTRAINT lesson_exceptions_makeup_credit_fkey
        FOREIGN KEY (makeup_credit_id) REFERENCES makeup_credits(id) ON DELETE SET NULL
        DEFERRABLE INITIALLY DEFERRED;
EXCEPTION WHEN duplicate_object OR duplicate_table THEN
    NULL;
END $$;
