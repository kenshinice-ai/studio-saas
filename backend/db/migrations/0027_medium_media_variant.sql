-- Add a 960px responsive-media derivative between list thumbnails and the
-- 2000px display image. Existing display/thumb rows remain valid.
ALTER TABLE media_variants
    DROP CONSTRAINT IF EXISTS media_variants_variant_check;

ALTER TABLE media_variants
    ADD CONSTRAINT media_variants_variant_check
    CHECK (variant IN ('display', 'medium', 'thumb'));
