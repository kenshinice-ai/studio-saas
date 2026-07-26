# PWE Studio — Platform Brand Identity

Version 1.0 — 2026-07-27. Single source of truth for the **platform** brand
(Super Admin console, default logo fallbacks, favicons/manifests, docs).
Tenant surfaces always carry the tenant's own logo/theme; the platform mark is
deliberately quiet so it never competes with tenant brands.

All assets are generated from one geometry table:
`docs/design/brand/render_assets.py`. Edit geometry/colors there and re-run
(`.venv/bin/python docs/design/brand/render_assets.py`) — it re-emits every
SVG, PNG, and the preview page deterministically (Pillow only, no SVG
rasterizer, no fonts).

---

## 1. Concept — "the spark inside the P"

One idea, carried everywhere: a **geometric uppercase P monogram** (the
platform: structure, reliability, the operating system) holding a
**four-pointed spark** in its negative space (the creativity the platform
hosts: art, music, dance, teaching). Navy provides the trust; the single amber
spark provides the creative energy — one accent, never more.

Why this concept won over the alternatives explored:

- **Brush-stroke abstraction** — too tenant-flavoured (reads "art school",
  not "platform for many kinds of studios") and degrades badly at 16px.
- **Spark/star alone** — generic (reads "AI sparkle" in 2026) and not ownable.
- **Stage/easel geometry** — ambiguous at small sizes, needs a caption.
- **P + spark** — initial letter of the brand, legible at 16px, monochrome-safe
  (the spark is a separate solid shape, not a knockout), and the story
  ("platform structure hosting a creative spark") matches the product exactly.

Style grounding (ui-ux-pro-max): *Minimalism & Swiss* style for SaaS
platform/enterprise surfaces (geometric, grid-based, high contrast);
*professional navy* primary family for B2B trust; *education amber* as the
course/creative accent in education palettes.

## 2. Construction

The mark lives on a **64×64 grid**, drawn as a stroked skeleton
(monoline, round caps) — identical in SVG and in the PIL renderer.

| Element | Geometry (64-grid) |
|---|---|
| Stem | vertical line x=17.75, y 13→51, stroke 10, round caps (ink y 8→56) |
| Bowl | full ring, centre (27, 22.25), skeleton r 9.25, stroke 10 (outer r 14.25, counter r 4.25) |
| Counter | opens exactly at the stem's right ink edge (x 22.75) — no overlap, no gap |
| Spark | four-point star, centre (38.5, 45), r 7.5, quadratic-bezier sides pinched through the centre |
| Ink bbox | (12.75, 8) → (46, 56) |
| Optical centre | (28.5, 32) — slightly left of the bbox centre because the spark is visually light; use this, not the bbox, when centring the mark in a frame |

Proportions that matter (do not change casually):

- Bowl occupies the **top 59%** of the stem — this is what makes it read as an
  uppercase **P** rather than lowercase "p" at 16px.
- Mark stroke : height = 10 : 48 (≈0.21) — bold enough to survive 16px.
- The spark sits in the P's "armpit" with ≥4.8 units clearance from the bowl
  and ≥8 from the stem: at 16px it collapses gracefully to a bright dot.

**Wordmark** ("PWE Studio"): custom monoline geometric letterforms —
skeleton lines/arcs/circles with round caps, stroke 5.5 on a 28-unit
cap-height grid (x-height 19). No font is referenced anywhere; every glyph is
authored geometry, so rendering is identical on every device. Lockup viewBox
252×64; mark at 0.78 scale, optically aligned so mark centre = wordmark
centre (y 32); the mark is ~10% taller than the caps so it reads as the anchor.

## 3. Color palette

Anchored to the Super Admin console tokens (`super-admin.html :root`), plus
one accent. Exact values:

| Role | Name | Hex | Usage |
|---|---|---|---|
| Brand ink | Studio Navy | `#0F172A` | The mark/wordmark on light surfaces; app-icon tile background; console `--ink`; manifest `theme_color` |
| Brand ink (dark surfaces) | Cloud | `#F8FAFC` | The mark/wordmark on navy/dark surfaces |
| Creative accent | Spark Amber | `#F59E0B` | The spark on light surfaces. Brand accent ONLY — never for body UI (amber is a warning color inside the console) |
| Creative accent (dark surfaces) | Spark Amber 400 | `#FBBF24` | The spark on navy/dark surfaces (better pop on `#0F172A`) |
| Canvas | Slate 100 | `#F1F5F9` | Light app canvas; console `--bg`; manifest `background_color` |
| Support neutrals | Slate family | `#475569` / `#64748B` / `#E2E8F0` | Secondary text, muted text, hairlines (console tokens `--ink-soft` / `--muted` / `--line`) |
| Product interactive | Console Blue | `#3B82F6` / `#2563EB` | Buttons/links in the console. **Not part of the logo** — identity is navy+amber; blue stays a UI-interaction color |

Monochrome rule: when only one color is available, the entire mark (including
the spark) is drawn in a single ink — navy on light, white on dark. The spark
is a solid separate shape, so nothing breaks.

## 4. Typography (UI)

The product deliberately ships **system font stacks** (fast, bilingual 中文/EN
without webfont weight). Policy:

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
             "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB",
             "Microsoft YaHei", sans-serif;
```

Brand moments (login screens, empty states, marketing headers):

| Role | Size / weight | Notes |
|---|---|---|
| Display / hero | 28–36px, weight 700, letter-spacing −0.5px | Navy `#0F172A` |
| Section heading | 20px, weight 600 | |
| Body | 15–16px, weight 400, line-height 1.5 | ≥4.5:1 contrast |
| Label / eyebrow | 11–12px, weight 600, uppercase, letter-spacing .08em | Slate `#64748B` |

Never typeset "PWE Studio" in a system font *as a logo* — use the SVG lockup.
In running text, "PWE Studio" is plain text like any other word. "SaaS" is
descriptive and never appears in the lockup.

## 5. Clearspace & minimum sizes

- **Clearspace**: keep a margin of the counter's diameter × 2 (= the mark's
  stroke width, 10/64 of mark height) on all sides of mark or lockup.
  Practical rule: at 32px mark height, keep 5px clear on every side.
- **Minimum sizes**: mark 16px; lockup 120px wide (below that, use the mark
  alone). App-icon tile: mark fills 58% of the tile (within the PWA maskable
  80% safe zone).

## 6. Light / dark usage

| Surface | Asset |
|---|---|
| Light (white / `#F1F5F9`) | `pwe-mark.svg`, `pwe-logo.svg`, root `logo.png` (navy ink + `#F59E0B` spark) |
| Dark (`#0F172A` or darker) | `pwe-mark-dark.svg`, `pwe-logo-dark.svg`, root `logo-light.png` (`#F8FAFC` ink + `#FBBF24` spark) |
| Either (browser tab) | root `favicon.svg` — theme-aware via `prefers-color-scheme` |
| App icon / home screen | `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` — always the navy tile with white P + amber spark (opaque; iOS dislikes transparency) |

Mid-tone backgrounds: pick whichever variant clears 4.5:1 for the ink;
if neither does, put the mark on a white or navy chip first.

## 7. DO / DON'T

**DO**

- Use the generated assets as-is; regenerate via `render_assets.py`.
- Keep the spark amber (or same-ink in monochrome).
- Use the mark alone at small sizes; the lockup at ≥120px width.
- Keep the platform mark off tenant-branded surfaces except neutral chrome
  (favicon, "powered by" footer if ever added).

**DON'T**

- Don't rotate, outline, shadow, gradient, or recolor the mark.
- Don't put the amber spark on amber/yellow backgrounds.
- Don't rebuild the wordmark in a font — letterforms are authored paths.
- Don't add "SaaS" to the lockup.
- Don't use Spark Amber as a general UI accent (it collides with the
  console's warning amber); interactive UI stays Console Blue.
- Don't stretch the lockup or change mark:wordmark scale.
- Don't place the navy mark on dark surfaces (use the dark variant).

## 8. Integration checklist (applied by the orchestrator — not by this doc)

Every **platform-owned** HTML surface (`super-admin.html`,
`studio-admin.html`) and **tenant-template pages** carry the PLATFORM favicon
set (tenant logo remains the tenant's inside the page; favicon/manifest chrome
is platform):

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0f172a">
```

Plus, where a manifest applies (already updated):

- `manifest.json` — Super Admin / platform PWA: `theme_color #0f172a`,
  `background_color #f1f5f9`, icons 192/512 (any + maskable).
- `manifest-student.json` — student portal PWA: `theme_color #0f172a`,
  `background_color #f8fafc`.

Default logo fallbacks (tenant without a logo): use root `logo.png` on light
headers, `logo-light.png` on dark headers. Super Admin header mark: inline
`pwe-mark.svg` (or `-dark` per header background) replacing the generic blue
rounded square.

## 9. File inventory

| File | Purpose |
|---|---|
| `docs/design/brand/pwe-mark.svg` / `pwe-mark-dark.svg` | Icon-only mark, light/dark |
| `docs/design/brand/pwe-logo.svg` / `pwe-logo-dark.svg` | Horizontal lockup, light/dark |
| `docs/design/brand/render_assets.py` | Geometry source of truth + PNG/SVG emitter |
| `docs/design/brand/preview.html` | Visual proof sheet (16/32/64/192px, light/dark, app-icon frame) |
| `/favicon.svg` | Theme-aware vector favicon |
| `/logo.png` (800×203) | Lockup, navy-on-transparent (light surfaces) |
| `/logo-light.png` (800×203) | Lockup, white-on-transparent (dark surfaces) |
| `/icon-192.png`, `/icon-512.png` | PWA icons, navy tile (any + maskable safe) |
| `/apple-touch-icon.png` (180) | iOS icon, opaque navy tile |
