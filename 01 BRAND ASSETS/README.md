# PWE · 天域 Brand Assets — PWE Studio and Paradise Production

This folder is the human-facing delivery kit for the house brand family:
**PWE · 天域** (the house), **PWE Studio** (its SaaS product line) and
**Paradise Production · 天域影像** (its film and creative line).
Runtime assets are generated into the repository root. The canonical PWE
geometry lives in `docs/design/brand/render_assets.py`; a distribution copy is
kept in `pwe-studio/source/`.

## Brand hierarchy

1. **PWE · 天域** — the house and parent brand; the company website at the
   root of `pwestudio.online`.
2. **PWE Studio** — the house's SaaS product line, the single product brand
   in every operating mode. Home: `/studio`. Mark: the Feather Star (a
   wing-family mark is planned; nothing is swapped yet).
3. **SaaS / Edition** — delivery-model descriptors in prose, never part of
   the logo or primary product name.
4. **Paradise Production · 天域影像** — the house's film and creative line.
   A sibling of PWE Studio, not its parent or producer.
5. **Tenant studio brands** — customer-owned logos, colours and copy. They
   take visual precedence in Studio Admin, Portal, Register and CMS.

## The Feather Star

The approved PWE Studio mark has one fixed story:

- The **four-point star is the starting point of creativity**.
- The **three feather blades represent growth, ascent and possibility**.
- Their proportions begin from the golden-ratio sequence **136 : 84 : 52**.

The mark and the `PWE STUDIO` wordmark form the only approved product lockup.
Do not add “SaaS” or “Edition” to the artwork.

See [BRAND_ARCHITECTURE.md](BRAND_ARCHITECTURE.md) for placement rules and
[brand-tokens.json](brand-tokens.json) for exact colour values.

## Folder map

| Path | Purpose |
|---|---|
| `logo/` | Paradise Production (film and creative line) SVG and PNG assets |
| `source/` | Paradise Production construction, raster generation and validation |
| `pwe-studio/svg/` | Feather Star mark and PWE STUDIO lockups |
| `pwe-studio/png/` | Transparent marks and lockups |
| `pwe-studio/pwa/` | PWE favicon, app icons and Apple touch icon |
| `pwe-studio/source/` | Distribution copy of the PWE asset generator |
| `brand-identity.html` | Paradise Production (film and creative line) visual guideline |

## Production rules

- Use supplied SVG assets whenever the environment supports them.
- Use `#A16207` instead of family amber for small text on white or Warm Paper.
- Never stretch, rotate, shadow, outline or recolour either identity.
- Never merge the Feather Star and Paradise wing into a combined logo.
- Never replace a tenant logo with a PWE Studio, house or Paradise logo.
- On tenant surfaces, use only the restrained footer text `Powered by PWE`;
  do not add a house logo to the header.
- On PWE Studio's own pages the credit is `PWE · 天域出品`, linking to the
  house at `/`.

## Regeneration

```bash
.venv/bin/python docs/design/brand/render_assets.py
python "01 BRAND ASSETS/source/build_assets.py"
.venv/bin/python "01 BRAND ASSETS/source/build_raster_exports.py"
.venv/bin/python "01 BRAND ASSETS/source/validate_assets.py" --write-manifest
.venv/bin/python "01 BRAND ASSETS/source/validate_assets.py"
```

The final command validates required files, raster dimensions, SVG safety,
the live-text boundary and the deterministic SHA-256 manifest.
