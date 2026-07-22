-- Preserve the real date a student joined the studio. Existing records remain
-- NULL so reports can fall back to their earliest trustworthy activity.
ALTER TABLE students
    ADD COLUMN IF NOT EXISTS enrolled_on date;

ALTER TABLE students
    ALTER COLUMN enrolled_on SET DEFAULT CURRENT_DATE;
