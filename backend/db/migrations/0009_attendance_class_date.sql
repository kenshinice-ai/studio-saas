-- A1 (LetsPaintCMS v4.6 R1): attendance is accounted on the CLASS date,
-- not the operation timestamp — a make-up check-in recorded on Tuesday
-- for Monday's class belongs to Monday. attended_at stays as the audit
-- timestamp of when the action happened.

ALTER TABLE attendance_sessions
    ADD COLUMN IF NOT EXISTS class_date date;

UPDATE attendance_sessions
SET class_date = (attended_at AT TIME ZONE 'Australia/Melbourne')::date
WHERE class_date IS NULL;

ALTER TABLE attendance_sessions
    ALTER COLUMN class_date SET DEFAULT (now() AT TIME ZONE 'Australia/Melbourne')::date;

CREATE INDEX IF NOT EXISTS idx_attendance_sessions_tenant_class_date
    ON attendance_sessions (tenant_id, class_date DESC);
