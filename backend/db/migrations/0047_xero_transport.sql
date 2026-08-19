-- v10.10.0 — the Xero transport arrives; the queue learns to wait politely.
--
-- Two columns and one fact:
--
--   next_attempt_at — retry backoff lives in the row, not in a scheduler's
--       memory. A 429 or a 5xx pushes this forward; the drain simply skips
--       rows whose turn has not come. Restarting the worker loses nothing.
--
--   xero_object_links.org_id — a link is only meaningful inside ONE Xero
--       organisation. The wizard's whole point is "try against the Demo
--       Company first, then connect the real org": the moment the org
--       changes, every stored id belongs to the wrong ledger. Recording the
--       org makes that visible, so a push after reconnecting creates fresh
--       documents instead of updating ghosts in the demo ledger.

ALTER TABLE integration_sync_jobs
    ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS last_attempt_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_due
    ON integration_sync_jobs (tenant_id, next_attempt_at)
    WHERE status = 'queued';

ALTER TABLE xero_object_links
    ADD COLUMN IF NOT EXISTS org_id text NOT NULL DEFAULT '';
