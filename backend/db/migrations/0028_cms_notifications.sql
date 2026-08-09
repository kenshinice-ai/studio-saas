-- v9.2 — durable in-app notifications for the CMS.
--
-- Notification rows belong to a tenant and are intentionally separate from
-- audit_logs: audit history is append-only system evidence, while this table
-- needs per-user read state and a stable polling cursor.

CREATE TABLE IF NOT EXISTS cms_notifications (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_no      bigint GENERATED ALWAYS AS IDENTITY UNIQUE NOT NULL,
    tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    notification_type text NOT NULL CHECK (notification_type IN (
        'registration.created', 'class_booking.created'
    )),
    title            text NOT NULL,
    summary          text NOT NULL DEFAULT '',
    resource_type    text NOT NULL,
    resource_id      text NOT NULL DEFAULT '',
    target_tab       text NOT NULL DEFAULT '',
    target_subtab    text NOT NULL DEFAULT '',
    dedupe_key       text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, dedupe_key)
);

CREATE TABLE IF NOT EXISTS cms_notification_reads (
    notification_id uuid NOT NULL REFERENCES cms_notifications(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    read_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (notification_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_cms_notifications_tenant_sequence
    ON cms_notifications (tenant_id, sequence_no DESC);

CREATE INDEX IF NOT EXISTS idx_cms_notification_reads_user_notification
    ON cms_notification_reads (user_id, notification_id);
