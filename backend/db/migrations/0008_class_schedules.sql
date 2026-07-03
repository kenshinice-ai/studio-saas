-- A1: recurring weekly class schedules (排课).
-- weekday uses the JavaScript Date.getDay() convention: 0=Sunday .. 6=Saturday,
-- so the CMS can resolve "who is due today" client-side without conversion.

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
