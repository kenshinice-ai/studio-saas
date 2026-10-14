-- 0049: a booking request keeps its place for a while.
--
-- Lee, 2026-10-14: a request on the public timetable holds a free place for a
-- fixed time (48 hours unless the tenant sets another value in
-- tenants.settings.booking_hold_hours). NULL means the request holds nothing:
-- every request made before this migration, a request that arrived when the
-- class was already full, and a second request from a phone that already
-- holds a place.
--
-- No job expires a hold. Every count asks `hold_expires_at > now()`, so a
-- hold stops counting at the moment it ends. The rules live in
-- services/booking_holds.py.

ALTER TABLE class_bookings
    ADD COLUMN IF NOT EXISTS hold_expires_at timestamptz;

-- The counts filter on exactly this: pending rows with a hold, per class date.
CREATE INDEX IF NOT EXISTS idx_class_bookings_live_holds
    ON class_bookings (schedule_id, on_date, hold_expires_at)
    WHERE status = 'pending' AND hold_expires_at IS NOT NULL;
