-- v8.10.0 — booking a class without opening an account.
--
-- Why this is not a row in `registrations`, which already has a review queue:
--
--   a new parent booking a trial and an existing student booking one session
--   are different events. Approving the first CREATES A STUDENT; approving the
--   second TAKES A SEAT. Only the first is a new enquiry.
--
-- Filing both as registrations would inflate "new enquiries this month"
-- permanently — and that number is how a studio judges whether its advertising
-- worked. A business metric that quietly counts the wrong thing is worse than
-- not having the metric, because it is still trusted.
--
-- The CMS still shows ONE inbox. Two tabs, two counts, one place to look.
--
-- See docs/design/Public_Timetable_And_Booking.md §2.

CREATE TABLE IF NOT EXISTS class_bookings (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    schedule_id         uuid NOT NULL REFERENCES class_schedules(id) ON DELETE CASCADE,
    on_date             date NOT NULL,

    -- Either the request matched an existing student, or it grew into a
    -- registration, or neither — an unrecognised new visitor. All three are
    -- normal. Both SET NULL: deleting a student must not erase the history of
    -- who asked for what.
    student_id          uuid NULL REFERENCES students(id) ON DELETE SET NULL,
    registration_id     uuid NULL REFERENCES registrations(id) ON DELETE SET NULL,

    -- What the parent actually typed is kept verbatim and forever, even after
    -- a match is made. The match is an inference; this is the evidence.
    contact_name        text NOT NULL,
    contact_phone       text NOT NULL,
    message             text NOT NULL DEFAULT '',

    status              text NOT NULL DEFAULT 'pending',
    review_note         text NOT NULL DEFAULT '',
    reviewed_by_user_id uuid NULL REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at         timestamptz NULL,

    -- Collecting a name and a phone number requires the same consent record
    -- the registration form keeps. Same field, same version string.
    privacy_notice_version text NOT NULL DEFAULT '',
    source_language     text NOT NULL DEFAULT '',
    campaign            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT class_bookings_status_check
        CHECK (status IN ('pending', 'approved', 'declined', 'cancelled'))
);

-- The CMS queue reads exactly this predicate.
CREATE INDEX IF NOT EXISTS idx_class_bookings_pending
    ON class_bookings (tenant_id, on_date, created_at)
    WHERE status = 'pending';

-- Seats-left arithmetic on the public page counts approved bookings per
-- occurrence, so that lookup gets its own index.
CREATE INDEX IF NOT EXISTS idx_class_bookings_approved_occurrence
    ON class_bookings (schedule_id, on_date)
    WHERE status = 'approved';

-- One pending request per phone per occurrence, enforced by the database
-- rather than by a check-then-insert.
--
-- A parent who is not sure the first tap worked taps again — that is the
-- normal case, not abuse. The endpoint answers "we already have it, please
-- wait" instead of creating a second row, and this index is what makes that
-- answer true under two simultaneous submissions rather than merely usual.
-- It is partial on `pending` so a declined request can be re-submitted later.
CREATE UNIQUE INDEX IF NOT EXISTS idx_class_bookings_one_pending_per_phone
    ON class_bookings (schedule_id, on_date, contact_phone)
    WHERE status = 'pending';

-- `daily_roster_entries.source` gains 'booking' so an approved request stays
-- traceable to where it came from once it lands on a day's roster. The four
-- existing values are carried over verbatim — this widens the constraint, it
-- does not restate it from memory.
ALTER TABLE daily_roster_entries DROP CONSTRAINT IF EXISTS daily_roster_entries_source_check;
ALTER TABLE daily_roster_entries ADD CONSTRAINT daily_roster_entries_source_check
    CHECK (source IN ('manual', 'group', 'profile', 'import', 'booking'));
