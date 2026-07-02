-- Platform super-admin memberships use tenant_id IS NULL (see P0-01).
-- The composite UNIQUE (tenant_id, user_id) does not constrain NULL rows,
-- so enforce at most one platform membership per user explicitly.
CREATE UNIQUE INDEX IF NOT EXISTS memberships_platform_user_uniq
    ON memberships (user_id)
    WHERE tenant_id IS NULL;
