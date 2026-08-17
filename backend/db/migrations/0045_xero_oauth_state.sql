-- 0045: pending OAuth handshakes for the Xero connection flow (X2).
--
-- PKCE requires the code_verifier to stay server-side between the redirect to
-- Xero and the callback. It cannot ride in the browser state parameter (that
-- would hand the verifier to the user agent, defeating PKCE), and it cannot
-- live in xero_connections (whose status CHECK models settled connections,
-- not handshakes in flight). One row per attempt; rows are single-use and
-- expire quickly, so an abandoned consent screen leaves nothing usable.
--
-- The verifier is encrypted by the application before INSERT, same contract
-- as the token columns in 0037.

CREATE TABLE IF NOT EXISTS xero_oauth_states (
    state_hash              text PRIMARY KEY,          -- sha256 of the state nonce; the nonce itself never lands in the DB
    tenant_id               uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code_verifier_encrypted text NOT NULL,
    created_by_user_id      uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    expires_at              timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS xero_oauth_states_expiry ON xero_oauth_states (expires_at);

-- The callback arrives on a root URL with no tenant context, so resolution
-- happens by state alone; RLS would make the row invisible to the very
-- request that must consume it. The table carries no long-lived secrets
-- (encrypted verifier, minutes-long lifetime) and is therefore exempted the
-- same way other non-tenant-scoped operational tables are.
ALTER TABLE xero_oauth_states FORCE ROW LEVEL SECURITY;
ALTER TABLE xero_oauth_states ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS xero_oauth_states_all ON xero_oauth_states;
CREATE POLICY xero_oauth_states_all ON xero_oauth_states
    USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON xero_oauth_states TO studiosaas_app;
