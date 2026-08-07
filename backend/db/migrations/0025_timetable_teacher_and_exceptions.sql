-- v8.8.0 — the fields a weekly schedule needs before it can face the public.
--
-- Nothing here changes a single public page. That is the point: the columns
-- land first, real studios fill them in with real classes, and the portal
-- section in v8.9.0 gets built against data that actually exists rather than
-- against a fixture. See docs/design/Public_Timetable_And_Booking.md.
--
-- Idempotent throughout: ADD COLUMN IF NOT EXISTS and CREATE TABLE IF NOT
-- EXISTS, so a re-run after a partial deploy is a no-op.

-- ── class_schedules ───────────────────────────────────────────────────────
--
-- teacher_user_id: ON DELETE SET NULL, not CASCADE. A teacher leaving must
-- not delete the班次 they used to run — the class continues, the name comes
-- off it.
ALTER TABLE class_schedules
    ADD COLUMN IF NOT EXISTS teacher_user_id uuid REFERENCES users(id) ON DELETE SET NULL;

-- is_public defaults to FALSE, and that default is the whole safety argument.
--
-- "Every class we have scheduled" and "every class we are advertising" are
-- different sets, and the difference is exactly the sensitive part: one-to-one
-- slots, internal make-up lessons, trial places held for a specific family,
-- the advanced group that only existing students may join. Defaulting to true
-- would publish all of them the moment the section shipped, retroactively,
-- for schedules created before anyone was asked.
--
-- So: opt in, one row at a time.
ALTER TABLE class_schedules
    ADD COLUMN IF NOT EXISTS is_public boolean NOT NULL DEFAULT false;

ALTER TABLE class_schedules
    ADD COLUMN IF NOT EXISTS room text NOT NULL DEFAULT '';

-- Reading the public timetable means "the public, active rows for this
-- tenant" — a partial index on exactly that predicate.
CREATE INDEX IF NOT EXISTS idx_class_schedules_public
    ON class_schedules (tenant_id, weekday, start_time)
    WHERE is_active AND is_public;

-- ── class_schedule_exceptions ─────────────────────────────────────────────
--
-- class_schedules says "every Wednesday". It has no way to say "not THIS
-- Wednesday", and daily_roster_entries.status = 'cancelled' is per-student,
-- not per-class.
--
-- Without this table a public timetable is a promise the studio cannot
-- withdraw: the week it closes for a public holiday, the site keeps saying
-- 16:00 Wednesday and a family drives across town. A timetable that cannot be
-- corrected is worse than no timetable, so this ships in the same release as
-- the fields, not after them.
--
-- The row is kept rather than the class being hidden: the public page strikes
-- that date through and prints the reason. A class that vanishes looks like a
-- broken website; a class marked 停课 · 公众假期 looks like someone is
-- minding the shop.
CREATE TABLE IF NOT EXISTS class_schedule_exceptions (
    schedule_id uuid NOT NULL REFERENCES class_schedules(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    on_date date NOT NULL,
    cancelled boolean NOT NULL DEFAULT true,
    note text NOT NULL DEFAULT '',
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (schedule_id, on_date)
);

CREATE INDEX IF NOT EXISTS idx_class_schedule_exceptions_tenant_date
    ON class_schedule_exceptions (tenant_id, on_date);

-- ── memberships ───────────────────────────────────────────────────────────
--
-- A teacher's name is the teacher's, not the studio's asset. Being rostered
-- onto a class is not consent to appear on the public internet under a legal
-- name, so this defaults to FALSE and the owner turns it on per person.
--
-- public_display_name exists because the honest alternative to "publish the
-- legal name" is not "publish nothing" — many teachers go by 「Lucy 老师」
-- professionally. Empty means "fall back to the account's full name", which
-- only matters at all once show_on_public_timetable is on.
ALTER TABLE memberships
    ADD COLUMN IF NOT EXISTS public_display_name text NOT NULL DEFAULT '';

ALTER TABLE memberships
    ADD COLUMN IF NOT EXISTS show_on_public_timetable boolean NOT NULL DEFAULT false;
