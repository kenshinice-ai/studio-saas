-- Attendance reversal metadata for traceable check-in undo/refund flows.

ALTER TABLE attendance_sessions
    ADD COLUMN IF NOT EXISTS reversed_at timestamptz;

ALTER TABLE attendance_sessions
    ADD COLUMN IF NOT EXISTS reversed_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE attendance_sessions
    ADD COLUMN IF NOT EXISTS reversal_credit_transaction_id uuid REFERENCES credit_transactions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_attendance_sessions_tenant_student_attended
    ON attendance_sessions (tenant_id, student_id, attended_at DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_sessions_credit_transaction
    ON attendance_sessions (tenant_id, credit_transaction_id)
    WHERE credit_transaction_id IS NOT NULL;
