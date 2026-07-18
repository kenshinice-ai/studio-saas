-- Canonical tenant-scoped daily roster entries.
--
-- Recurring class schedules remain templates. This table records explicit
-- date-level additions and their reversible cancellation state, replacing the
-- mutable legacy JSON roster board as the source of truth.

DO $$
BEGIN
    ALTER TABLE students
        ADD CONSTRAINT students_tenant_id_id_unique UNIQUE (tenant_id, id);
EXCEPTION WHEN duplicate_object THEN
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
