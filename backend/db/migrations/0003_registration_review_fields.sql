-- Registration review metadata for the Studio Admin workflow.
ALTER TABLE registrations
    ADD COLUMN IF NOT EXISTS student_id uuid REFERENCES students(id) ON DELETE SET NULL;

ALTER TABLE registrations
    ADD COLUMN IF NOT EXISTS review_note text NOT NULL DEFAULT '';

ALTER TABLE registrations
    ADD COLUMN IF NOT EXISTS duplicate_of_registration_id uuid REFERENCES registrations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_registrations_tenant_status_submitted
    ON registrations (tenant_id, status, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_registrations_tenant_student
    ON registrations (tenant_id, student_id)
    WHERE student_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_registrations_tenant_duplicate
    ON registrations (tenant_id, duplicate_of_registration_id)
    WHERE duplicate_of_registration_id IS NOT NULL;
