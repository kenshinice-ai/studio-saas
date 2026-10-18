-- 0050: a row and the row it points to belong to the same tenant.
--
-- Forty foreign keys joined two tenant-owned tables on `id` alone, so the
-- database accepted a reference from one tenant's row to another tenant's
-- row; only the application's checks stood in the way. Each now carries
-- `tenant_id` as well, against a UNIQUE (tenant_id, id) on the parent, and the
-- database refuses such a reference whatever route it comes from.
--
-- Measured before writing this (2026-10-18, production, read-only): the forty
-- keys linked 1,143 rows and none crossed a tenant, so nothing needs cleaning
-- first. Every child `tenant_id` is NOT NULL, so none of the keys can be
-- skipped by MATCH SIMPLE.
--
-- Delete behaviour is unchanged, with one necessary detail: a key that set the
-- child column to NULL now names that column — `ON DELETE SET NULL (x_id)`
-- (PostgreSQL 15+; production and CI run 16). The bare form would also null
-- `tenant_id`, which is NOT NULL, and every such delete would fail.
--
-- One transaction (run_migrations.py applies each file in its own). The tables
-- are small; each ADD CONSTRAINT scans its child once.

-- 1. Parents that did not yet have a (tenant_id, id) key. `id` is already the
--    primary key, so these cannot fail on existing data.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'class_schedules_tenant_id_id_key') THEN
        ALTER TABLE class_schedules ADD CONSTRAINT class_schedules_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'courses_tenant_id_id_key') THEN
        ALTER TABLE courses ADD CONSTRAINT courses_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'credit_accounts_tenant_id_id_key') THEN
        ALTER TABLE credit_accounts ADD CONSTRAINT credit_accounts_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'lesson_exceptions_tenant_id_id_key') THEN
        ALTER TABLE lesson_exceptions ADD CONSTRAINT lesson_exceptions_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'makeup_credits_tenant_id_id_key') THEN
        ALTER TABLE makeup_credits ADD CONSTRAINT makeup_credits_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'media_assets_tenant_id_id_key') THEN
        ALTER TABLE media_assets ADD CONSTRAINT media_assets_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'portfolio_items_tenant_id_id_key') THEN
        ALTER TABLE portfolio_items ADD CONSTRAINT portfolio_items_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'registrations_tenant_id_id_key') THEN
        ALTER TABLE registrations ADD CONSTRAINT registrations_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'share_tokens_tenant_id_id_key') THEN
        ALTER TABLE share_tokens ADD CONSTRAINT share_tokens_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tenant_brand_versions_tenant_id_id_key') THEN
        ALTER TABLE tenant_brand_versions ADD CONSTRAINT tenant_brand_versions_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'terms_tenant_id_id_key') THEN
        ALTER TABLE terms ADD CONSTRAINT terms_tenant_id_id_key UNIQUE (tenant_id, id);
    END IF;
END $$;

-- 2. Each key, replaced in place under its own name.
ALTER TABLE attendance_sessions
    DROP CONSTRAINT IF EXISTS attendance_sessions_course_id_fkey,
    ADD CONSTRAINT attendance_sessions_course_id_fkey FOREIGN KEY (tenant_id, course_id) REFERENCES courses (tenant_id, id) ON DELETE SET NULL (course_id);
ALTER TABLE attendance_sessions
    DROP CONSTRAINT IF EXISTS attendance_sessions_credit_transaction_id_fkey,
    ADD CONSTRAINT attendance_sessions_credit_transaction_id_fkey FOREIGN KEY (tenant_id, credit_transaction_id) REFERENCES credit_transactions (tenant_id, id) ON DELETE SET NULL (credit_transaction_id);
ALTER TABLE attendance_sessions
    DROP CONSTRAINT IF EXISTS attendance_sessions_reversal_credit_transaction_id_fkey,
    ADD CONSTRAINT attendance_sessions_reversal_credit_transaction_id_fkey FOREIGN KEY (tenant_id, reversal_credit_transaction_id) REFERENCES credit_transactions (tenant_id, id) ON DELETE SET NULL (reversal_credit_transaction_id);
ALTER TABLE attendance_sessions
    DROP CONSTRAINT IF EXISTS attendance_sessions_student_id_fkey,
    ADD CONSTRAINT attendance_sessions_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE class_bookings
    DROP CONSTRAINT IF EXISTS class_bookings_registration_id_fkey,
    ADD CONSTRAINT class_bookings_registration_id_fkey FOREIGN KEY (tenant_id, registration_id) REFERENCES registrations (tenant_id, id) ON DELETE SET NULL (registration_id);
ALTER TABLE class_bookings
    DROP CONSTRAINT IF EXISTS class_bookings_schedule_id_fkey,
    ADD CONSTRAINT class_bookings_schedule_id_fkey FOREIGN KEY (tenant_id, schedule_id) REFERENCES class_schedules (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE class_bookings
    DROP CONSTRAINT IF EXISTS class_bookings_student_id_fkey,
    ADD CONSTRAINT class_bookings_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE SET NULL (student_id);
ALTER TABLE class_schedule_exceptions
    DROP CONSTRAINT IF EXISTS class_schedule_exceptions_schedule_id_fkey,
    ADD CONSTRAINT class_schedule_exceptions_schedule_id_fkey FOREIGN KEY (tenant_id, schedule_id) REFERENCES class_schedules (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE class_schedule_students
    DROP CONSTRAINT IF EXISTS class_schedule_students_schedule_id_fkey,
    ADD CONSTRAINT class_schedule_students_schedule_id_fkey FOREIGN KEY (tenant_id, schedule_id) REFERENCES class_schedules (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE class_schedule_students
    DROP CONSTRAINT IF EXISTS class_schedule_students_student_id_fkey,
    ADD CONSTRAINT class_schedule_students_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE class_schedules
    DROP CONSTRAINT IF EXISTS class_schedules_course_id_fkey,
    ADD CONSTRAINT class_schedules_course_id_fkey FOREIGN KEY (tenant_id, course_id) REFERENCES courses (tenant_id, id) ON DELETE SET NULL (course_id);
ALTER TABLE credit_accounts
    DROP CONSTRAINT IF EXISTS credit_accounts_course_id_fkey,
    ADD CONSTRAINT credit_accounts_course_id_fkey FOREIGN KEY (tenant_id, course_id) REFERENCES courses (tenant_id, id) ON DELETE SET NULL (course_id);
ALTER TABLE credit_accounts
    DROP CONSTRAINT IF EXISTS credit_accounts_student_id_fkey,
    ADD CONSTRAINT credit_accounts_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE credit_transactions
    DROP CONSTRAINT IF EXISTS credit_transactions_account_id_fkey,
    ADD CONSTRAINT credit_transactions_account_id_fkey FOREIGN KEY (tenant_id, account_id) REFERENCES credit_accounts (tenant_id, id) ON DELETE SET NULL (account_id);
ALTER TABLE credit_transactions
    DROP CONSTRAINT IF EXISTS credit_transactions_student_id_fkey,
    ADD CONSTRAINT credit_transactions_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE invoices
    DROP CONSTRAINT IF EXISTS invoices_term_id_fkey,
    ADD CONSTRAINT invoices_term_id_fkey FOREIGN KEY (tenant_id, term_id) REFERENCES terms (tenant_id, id) ON DELETE SET NULL (term_id);
ALTER TABLE lesson_exceptions
    DROP CONSTRAINT IF EXISTS lesson_exceptions_makeup_credit_fkey,
    ADD CONSTRAINT lesson_exceptions_makeup_credit_fkey FOREIGN KEY (tenant_id, makeup_credit_id) REFERENCES makeup_credits (tenant_id, id) ON DELETE SET NULL (makeup_credit_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE lesson_series
    DROP CONSTRAINT IF EXISTS lesson_series_course_id_fkey,
    ADD CONSTRAINT lesson_series_course_id_fkey FOREIGN KEY (tenant_id, course_id) REFERENCES courses (tenant_id, id) ON DELETE SET NULL (course_id);
ALTER TABLE makeup_credits
    DROP CONSTRAINT IF EXISTS makeup_credits_consumed_exception_id_fkey,
    ADD CONSTRAINT makeup_credits_consumed_exception_id_fkey FOREIGN KEY (tenant_id, consumed_exception_id) REFERENCES lesson_exceptions (tenant_id, id) ON DELETE SET NULL (consumed_exception_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE makeup_credits
    DROP CONSTRAINT IF EXISTS makeup_credits_earned_from_exception_id_fkey,
    ADD CONSTRAINT makeup_credits_earned_from_exception_id_fkey FOREIGN KEY (tenant_id, earned_from_exception_id) REFERENCES lesson_exceptions (tenant_id, id) ON DELETE SET NULL (earned_from_exception_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE media_assets
    DROP CONSTRAINT IF EXISTS media_assets_owner_student_id_fkey,
    ADD CONSTRAINT media_assets_owner_student_id_fkey FOREIGN KEY (tenant_id, owner_student_id) REFERENCES students (tenant_id, id) ON DELETE SET NULL (owner_student_id);
ALTER TABLE media_variants
    DROP CONSTRAINT IF EXISTS media_variants_media_asset_id_fkey,
    ADD CONSTRAINT media_variants_media_asset_id_fkey FOREIGN KEY (tenant_id, media_asset_id) REFERENCES media_assets (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE packages
    DROP CONSTRAINT IF EXISTS packages_course_id_fkey,
    ADD CONSTRAINT packages_course_id_fkey FOREIGN KEY (tenant_id, course_id) REFERENCES courses (tenant_id, id) ON DELETE SET NULL (course_id);
ALTER TABLE portfolio_items
    DROP CONSTRAINT IF EXISTS portfolio_items_media_asset_id_fkey,
    ADD CONSTRAINT portfolio_items_media_asset_id_fkey FOREIGN KEY (tenant_id, media_asset_id) REFERENCES media_assets (tenant_id, id) ON DELETE RESTRICT;
ALTER TABLE portfolio_items
    DROP CONSTRAINT IF EXISTS portfolio_items_student_id_fkey,
    ADD CONSTRAINT portfolio_items_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE progress_reports
    DROP CONSTRAINT IF EXISTS progress_reports_share_token_id_fkey,
    ADD CONSTRAINT progress_reports_share_token_id_fkey FOREIGN KEY (tenant_id, share_token_id) REFERENCES share_tokens (tenant_id, id) ON DELETE SET NULL (share_token_id);
ALTER TABLE progress_reports
    DROP CONSTRAINT IF EXISTS progress_reports_term_id_fkey,
    ADD CONSTRAINT progress_reports_term_id_fkey FOREIGN KEY (tenant_id, term_id) REFERENCES terms (tenant_id, id) ON DELETE SET NULL (term_id);
ALTER TABLE registrations
    DROP CONSTRAINT IF EXISTS registrations_duplicate_of_registration_id_fkey,
    ADD CONSTRAINT registrations_duplicate_of_registration_id_fkey FOREIGN KEY (tenant_id, duplicate_of_registration_id) REFERENCES registrations (tenant_id, id) ON DELETE SET NULL (duplicate_of_registration_id);
ALTER TABLE registrations
    DROP CONSTRAINT IF EXISTS registrations_student_id_fkey,
    ADD CONSTRAINT registrations_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE SET NULL (student_id);
ALTER TABLE share_tokens
    DROP CONSTRAINT IF EXISTS share_tokens_portfolio_item_id_fkey,
    ADD CONSTRAINT share_tokens_portfolio_item_id_fkey FOREIGN KEY (tenant_id, portfolio_item_id) REFERENCES portfolio_items (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE share_tokens
    DROP CONSTRAINT IF EXISTS share_tokens_student_id_fkey,
    ADD CONSTRAINT share_tokens_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE student_access_sessions
    DROP CONSTRAINT IF EXISTS student_access_sessions_student_id_fkey,
    ADD CONSTRAINT student_access_sessions_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE student_publication_consent_events
    DROP CONSTRAINT IF EXISTS student_publication_consent_events_source_registration_id_fkey,
    ADD CONSTRAINT student_publication_consent_events_source_registration_id_fkey FOREIGN KEY (tenant_id, source_registration_id) REFERENCES registrations (tenant_id, id) ON DELETE SET NULL (source_registration_id);
ALTER TABLE student_publication_consent_events
    DROP CONSTRAINT IF EXISTS student_publication_consent_events_student_id_fkey,
    ADD CONSTRAINT student_publication_consent_events_student_id_fkey FOREIGN KEY (tenant_id, student_id) REFERENCES students (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE students
    DROP CONSTRAINT IF EXISTS students_student_photo_asset_id_fkey,
    ADD CONSTRAINT students_student_photo_asset_id_fkey FOREIGN KEY (tenant_id, student_photo_asset_id) REFERENCES media_assets (tenant_id, id) ON DELETE SET NULL (student_photo_asset_id);
ALTER TABLE teacher_pay_rates
    DROP CONSTRAINT IF EXISTS teacher_pay_rates_course_id_fkey,
    ADD CONSTRAINT teacher_pay_rates_course_id_fkey FOREIGN KEY (tenant_id, course_id) REFERENCES courses (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE teaching_sessions
    DROP CONSTRAINT IF EXISTS teaching_sessions_course_id_fkey,
    ADD CONSTRAINT teaching_sessions_course_id_fkey FOREIGN KEY (tenant_id, course_id) REFERENCES courses (tenant_id, id) ON DELETE SET NULL (course_id);
ALTER TABLE teaching_sessions
    DROP CONSTRAINT IF EXISTS teaching_sessions_schedule_id_fkey,
    ADD CONSTRAINT teaching_sessions_schedule_id_fkey FOREIGN KEY (tenant_id, schedule_id) REFERENCES class_schedules (tenant_id, id) ON DELETE SET NULL (schedule_id);
ALTER TABLE teaching_sessions
    DROP CONSTRAINT IF EXISTS teaching_sessions_series_id_fkey,
    ADD CONSTRAINT teaching_sessions_series_id_fkey FOREIGN KEY (tenant_id, series_id) REFERENCES lesson_series (tenant_id, id) ON DELETE SET NULL (series_id);
ALTER TABLE tenant_brand_versions
    DROP CONSTRAINT IF EXISTS tenant_brand_versions_source_version_id_fkey,
    ADD CONSTRAINT tenant_brand_versions_source_version_id_fkey FOREIGN KEY (tenant_id, source_version_id) REFERENCES tenant_brand_versions (tenant_id, id) ON DELETE SET NULL (source_version_id);
