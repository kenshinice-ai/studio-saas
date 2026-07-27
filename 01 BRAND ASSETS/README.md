# PWE Studio / Paradise Production Brand Assets

This folder is the human-facing delivery kit for the StudioSaaS brand family.
Runtime assets remain generated into the repository root; source-of-truth
geometry lives in the `source/` folders named below.

## Brand hierarchy

1. **PWE Studio SaaS** — the multi-tenant product.
2. **PWE Studio Edition** — the single-customer standalone product.
3. **Paradise Production · 天域文创** — the producer and parent brand.
4. **Tenant studio brands** — customer-owned logos, colours and copy. These
   always take precedence on Portal, Register and CMS surfaces.

PWE retains its Crafted-P mark and geometric wordmark. The PWE mark is not
replaced by the Paradise wing. The two identities share the family navy,
family amber and four-point spark motif.

See [BRAND_ARCHITECTURE.md](BRAND_ARCHITECTURE.md) for placement rules and
[brand-tokens.json](brand-tokens.json) for exact colour values.

## Folder map

| Path | Purpose |
|---|---|
| `logo/` | Supplied Paradise Production SVG and PNG assets |
| `source/` | Paradise wing construction and deterministic SVG generator |
| `pwe-studio/svg/` | PWE mark and horizontal lockups |
| `pwe-studio/png/` | Transparent PWE marks and lockups |
| `pwe-studio/pwa/` | PWE favicon, app icons and Apple touch icon |
| `pwe-studio/source/` | Copy of the deterministic PWE geometry generator |
| `brand-identity.html` | Supplied Paradise Production visual guideline |

## Production rules

- Use SVG for web and digital layouts when the environment preserves the
  referenced fonts.
- Supplied Paradise lockup SVGs contain editable `<text>` elements. Use their
  PNG exports for uncontrolled third-party environments until outlined print
  masters are supplied.
- Use `#A16207` rather than family amber for small text on white or warm-paper
  backgrounds.
- Do not stretch, rotate, shadow, outline or recolour either mark.
- Do not merge the PWE mark and Paradise wing into a new combined logo.
- Never replace a configured tenant logo with either platform or producer
  branding.

## Regeneration

```bash
.venv/bin/python docs/design/brand/render_assets.py
python "01 BRAND ASSETS/source/build_assets.py"
.venv/bin/python "01 BRAND ASSETS/source/build_raster_exports.py"
.venv/bin/python "01 BRAND ASSETS/source/validate_assets.py" --write-manifest
.venv/bin/python "01 BRAND ASSETS/source/validate_assets.py"
```

The final command validates required files, exact raster dimensions, SVG
viewBoxes, the documented live-text boundary and the deterministic SHA-256
manifest. Supplied legacy Paradise PNGs remain unchanged; normalized web/PWA
exports live in `logo/png/web/` and use truthful size suffixes.
