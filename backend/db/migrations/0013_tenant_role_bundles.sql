-- Explicit tenant operational roles. Brand publication remains owner-only.

ALTER TABLE memberships
    DROP CONSTRAINT IF EXISTS memberships_role_check;

ALTER TABLE memberships
    ADD CONSTRAINT memberships_role_check
    CHECK (role IN (
        'super_admin', 'owner', 'manager', 'teacher',
        'front_desk', 'staff', 'parent'
    ));
