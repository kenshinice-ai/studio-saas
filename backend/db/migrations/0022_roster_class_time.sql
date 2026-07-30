-- 0022 — a class time and a one-to-one flag on the daily roster.
--
-- Why: the roster answered "who is coming today" but not "when". A studio that
-- runs a 10:00 group and a 17:00 one-to-one on the same afternoon saw one flat
-- list, so the front desk could not tell from the roster whether a student was
-- due now or in six hours, and a one-to-one booked into an occupied slot was
-- only discovered when both families arrived.
--
-- `class_time` is nullable on purpose. Every existing row predates this column
-- and there is no honest value to backfill — inventing 09:00 for 43 imported
-- students would look like data rather than the absence of it. The UI groups
-- rows without a time under an explicit "time not set" heading and sorts them
-- last, which keeps the gap visible instead of hiding it behind a default.
--
-- `time` rather than `timestamptz`: this is a wall-clock slot in the studio's
-- own timezone ("the 17:00 class"), not an instant. Storing it as an instant
-- would make it move when the studio's offset changes, which is exactly wrong
-- for a recurring 17:00 lesson.

ALTER TABLE daily_roster_entries
    ADD COLUMN IF NOT EXISTS class_time time,
    ADD COLUMN IF NOT EXISTS one_to_one boolean NOT NULL DEFAULT false;

-- The roster view reads one tenant + one date and then groups by slot. The
-- existing index already covers (tenant_id, roster_date); adding class_time
-- lets the group-by read in slot order instead of sorting afterwards.
CREATE INDEX IF NOT EXISTS idx_daily_roster_tenant_date_time
    ON daily_roster_entries (tenant_id, roster_date, class_time);

COMMENT ON COLUMN daily_roster_entries.class_time IS
    'Wall-clock slot in the studio timezone. NULL means the slot was never set; '
    'do not backfill a guess.';
COMMENT ON COLUMN daily_roster_entries.one_to_one IS
    'Marks a private lesson. The UI reports a conflict when a one-to-one shares '
    'its slot with anyone else.';
