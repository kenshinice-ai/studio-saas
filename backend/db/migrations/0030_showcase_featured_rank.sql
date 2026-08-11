-- v9.8.7: add an explicit, tenant-owned editorial order to showcase records.
--
-- Showcase items live inside tenants.settings.website_profile as JSONB rather
-- than in a separate table.  This additive backfill makes the new key visible
-- in existing records without changing their order or publication state.  The
-- application still treats a missing/invalid value as NULL, so this migration
-- is idempotent and safe for workspaces created before v9.8.7.

UPDATE tenants AS t
SET settings = jsonb_set(
    t.settings,
    '{website_profile,showcase_items}',
    COALESCE((
        SELECT jsonb_agg(
            CASE
                WHEN jsonb_typeof(item) = 'object'
                     AND NOT (item ? 'featured_rank')
                THEN item || jsonb_build_object('featured_rank', NULL)
                ELSE item
            END
            ORDER BY ordinal
        )
        FROM jsonb_array_elements(
            t.settings->'website_profile'->'showcase_items'
        ) WITH ORDINALITY AS entries(item, ordinal)
    ), '[]'::jsonb),
    true
)
WHERE jsonb_typeof(t.settings->'website_profile') = 'object'
  AND jsonb_typeof(t.settings->'website_profile'->'showcase_items') = 'array';
