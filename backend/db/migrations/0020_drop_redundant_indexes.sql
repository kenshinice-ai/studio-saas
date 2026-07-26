-- v7.6.0 stability pass (2026-07-27 DB audit findings D3 + L4).
--
-- Two secondary indexes duplicate the index that already backs a UNIQUE
-- constraint on the same table. Every write pays to maintain both copies;
-- reads gain nothing. Same class of fix as 0019's credit_accounts cleanup.
--
-- 1. idx_media_variants_asset (introduced in 0015) is column-for-column
--    identical to the index backing
--    UNIQUE (tenant_id, media_asset_id, variant) on media_variants.
-- 2. idx_tenant_brand_versions_tenant_published (introduced in 0012)
--    differs from the index backing UNIQUE (tenant_id, version_number) on
--    tenant_brand_versions only by DESC on the second key — a btree is
--    scanned backwards just as efficiently, so the constraint index serves
--    the latest-version-first queries on its own.
--
-- ON CONFLICT inference is unaffected: it resolves against the UNIQUE
-- constraints, which both remain.

DROP INDEX IF EXISTS idx_media_variants_asset;
DROP INDEX IF EXISTS idx_tenant_brand_versions_tenant_published;
