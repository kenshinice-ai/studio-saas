-- 0048: a family's calendar feed can find its own subscription again.
--
-- The feed URL carries a token and nothing else: no session, no tenant. The
-- route has to learn the tenant FROM the token. Since 0042 put
-- calendar_subscriptions under FORCE ROW LEVEL SECURITY, a connection that has
-- not yet been bound to a tenant sees zero rows there — so under the runtime
-- role every token, valid or not, resolved to "Calendar not found". No test
-- requested the URL, so nothing noticed.
--
-- The fix is deliberately narrower than exempting the table (the route for
-- share_tokens) or adding a USING (true) policy (the route for
-- xero_oauth_states). This function answers exactly one question — "which
-- tenant owns the live subscription with this token hash?" — and nothing else
-- becomes visible. The caller then binds the connection to that tenant and
-- reads everything else under the ordinary tenant policy.
--
-- It runs with the caller's rights (not SECURITY DEFINER): under FORCE RLS the
-- table owner is filtered too, so definer rights would buy nothing. Platform
-- scope is switched on by the SET clause, which PostgreSQL applies for the
-- duration of the call and restores afterwards, so it cannot leak into the
-- rest of the request.

CREATE OR REPLACE FUNCTION calendar_subscription_tenant(p_token_hash text)
RETURNS uuid
LANGUAGE sql
STABLE
SET studiosaas.platform = 'on'
AS $$
    SELECT tenant_id
      FROM calendar_subscriptions
     WHERE token_hash = p_token_hash
       AND revoked_at IS NULL
$$;
