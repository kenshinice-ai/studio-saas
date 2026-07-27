# PWE Studio — Platform Brand Identity

Version 3.0 — 2026-07-27. Single source of truth for the **PWE product
identity** and its relationship to the parent/producer identity,
**Paradise Production · 天域文创**. The human-facing delivery kit is
`01 BRAND ASSETS/`; this document governs product integration.

Tenant surfaces always carry the tenant's own logo/theme. PWE stays quiet
inside tenant workspaces, and Paradise is absent from SaaS tenant pages.
PWE Studio Edition may show the compact contractual producer attribution in
the footer; it is enabled by default and can be removed by deployment config
where the commercial agreement permits.

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
- **P + spark** — initial letter of the brand, legible at 16px,
  monochrome-safe, and the story ("platform structure hosting a creative
  spark") matches the product exactly. Round 2 made the metaphor literal:
  the spark IS the P's counter — the letter is built around the spark.

Style grounding (ui-ux-pro-max): *Minimalism & Swiss* style for SaaS
platform/enterprise surfaces (geometric, grid-based, high contrast);
*professional navy* primary family for B2B trust; *education amber* as the
course/creative accent in education palettes.

## 2. Construction — "Crafted P" (Round 2)

The mark lives on a **64×64 grid**, drawn as a **solid custom letterform**
(cap height 44, y 10→54) with the spark punched out as the bowl's counter —
identical geometry in SVG (evenodd path + amber refill) and in the PIL
renderer (sampled bezier polygon + amber spark on top).

| Element | Geometry (64-grid) |
|---|---|
| Cap height | 44 (y 10→54); stem left edge x 14 |
| Stem | right edge tapers 24.9 → 24.3 top-to-bottom (0.6 unit — felt, not seen) |
| Bowl | cubic-drawn, depth 26.6 = **60.5% of cap height**; superelliptical shoulders; right extreme x 50.2 at y 23.1 — slightly *above* the bowl's vertical middle (upward stress) |
| Ink trap | small concave ease (`C 25.2 36.7 24.6 37.4 24.55 38.6`) where the bowl underside re-enters the stem, so the crotch doesn't clog at small sizes |
| Spark / counter | four-point star, centre (34.5, 23.2), r 7.5, quadratic-bezier sides pinched through the centre; punched via `fill-rule="evenodd"`, refilled amber |
| Ink bbox | (14, 10) → (50.2, 54) |
| Optical centre | (31.0, 30.2) — between bbox centre (32.1, 32) and ink centroid (~28, 27.4); the bowl carries the mass, the lower stem is light. Use this, not the bbox, when centring the mark in a frame |

Proportions that matter (do not change casually):

- Bowl closes at **60.5% of cap height** with the stem descending well below —
  this is what makes it read as an uppercase **P** (never "b/p") at 16px.
- The spark-as-counter keeps ≥2.4 units of wall to the stem (west tip — reads
  as the counter meeting the stem, like a real P) and ≥6 units everywhere
  else. At 16px the spark collapses gracefully to a bright dot inside the bowl.
- Solid body, no strokes: the mark survives 16px and monochrome without any
  weight compensation.

**Wordmark** ("PWE Studio"): custom monoline geometric letterforms —
skeleton lines/arcs/circles with round caps, stroke 5.5 on a 28-unit
cap-height grid (x-height 19). No font is referenced anywhere; every glyph is
authored geometry, so rendering is identical on every device. The wordmark's
**"P" echoes the mark**: bowl closes at skeleton y 14.5 (ink ≈61.6% of cap,
matching the mark's 60.5%) with a fuller shoulder (arc r 7.25, entry to x 7)
than the round-1 half-circle. Lockup viewBox 252×64; mark at **0.75 scale**
(solid mark carries more ink than the old monoline skeleton, so it steps down
from 0.78 and the mark→text gap opens to ~12 units), optically aligned so
mark ink centre = wordmark optical middle (y 32).

## 3. Colour palette

PWE and Paradise now use one family palette. The PWE Crafted-P remains an
independent mark; colour alignment creates family recognition without
collapsing product and producer into a single logo.

| Role | Name | Hex | Usage |
|---|---|---|---|
| Brand ink | Family Navy | `#0E1729` | Mark/wordmark on light surfaces; app-icon tile; console shell; manifest `theme_color` |
| Raised brand surface | Family Navy Raised | `#16233D` | Dark gradients and elevated brand panels |
| Brand ink (dark surfaces) | White | `#FFFFFF` | Mark/wordmark on Family Navy |
| Creative accent | Family Amber | `#F5B335` | PWE spark and Paradise wing. Identity accent only, not a warning or default button colour |
| Accessible amber text | Amber Text | `#A16207` | Small amber text on white or Warm Paper |
| Canvas | Warm Paper | `#F7F5F2` | Family marketing canvas; product shell background; manifest `background_color` |
| Support neutrals | Slate family | `#475569` / `#64748B` / `#E2E8F0` | Secondary text, muted text, hairlines (console tokens `--ink-soft` / `--muted` / `--line`) |
| Product interactive | Console Blue | `#3B82F6` / `#2563EB` | Buttons/links in the console. **Not part of the logo** — identity is navy+amber; blue stays a UI-interaction color |

Monochrome rule: when only one color is available, drop the amber refill —
the punched counter still reads as the spark in pure negative space (this is
the Round-2 design's built-in monochrome answer). Single ink: navy on light,
white on dark.

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
| Display / hero | 28–36px, weight 700, letter-spacing −0.5px | Family Navy `#0E1729` |
| Section heading | 20px, weight 600 | |
| Body | 15–16px, weight 400, line-height 1.5 | ≥4.5:1 contrast |
| Label / eyebrow | 11–12px, weight 600, uppercase, letter-spacing .08em | Slate `#64748B` |

Never typeset "PWE Studio" in a system font *as a logo* — use the SVG lockup.
In running text, "PWE Studio" is plain text like any other word. "SaaS" is
descriptive and never appears in the lockup.

## 5. Clearspace & minimum sizes

- **Clearspace**: keep a margin of ≥ the spark's diameter (15/64 ≈ 23% of
  mark height) on all sides of mark or lockup.
  Practical rule: at 32px mark height, keep 7px clear on every side.
- **Minimum sizes**: mark 16px; lockup 120px wide (below that, use the mark
  alone). App-icon tile: mark fills 58% of the tile (within the PWA maskable
  80% safe zone).

## 6. Light / dark usage

| Surface | Asset |
|---|---|
| Light (white / `#F7F5F2`) | `pwe-mark.svg`, `pwe-logo.svg`, root `logo.png` (Family Navy + Family Amber) |
| Dark (`#0E1729` or darker) | `pwe-mark-dark.svg`, `pwe-logo-dark.svg`, root `logo-light.png` (white + Family Amber) |
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
<meta name="theme-color" content="#0e1729">
```

Plus, where a manifest applies (already updated):

- `manifest.json` — Super Admin / platform PWA: `theme_color #0e1729`,
  `background_color #f7f5f2`, icons 192/512 (any + maskable).
- `manifest-student.json` — student portal PWA: `theme_color #0e1729`,
  `background_color #f7f5f2`.

Default logo fallbacks (tenant without a logo): use root `logo.png` on light
headers, `logo-light.png` on dark headers. Platform admin headers load the
generated `favicon.svg` mark instead of a generic square. Super Admin login
uses the producer credit line per §10; Edition may also show the compact text
credit in its tenant Portal footer under the documented mode rule.

## 9. File inventory

| File | Purpose |
|---|---|
| `docs/design/brand/pwe-mark.svg` / `pwe-mark-dark.svg` | Icon-only mark, light/dark |
| `docs/design/brand/pwe-logo.svg` / `pwe-logo-dark.svg` | Horizontal lockup, light/dark |
| `docs/design/brand/credit-line.svg` / `credit-line-dark.svg` | Producer credit line reference (see §10 — CSS spec is the source of truth for HTML) |
| `docs/design/brand/render_assets.py` | Geometry source of truth + PNG/SVG emitter |
| `docs/design/brand/preview.html` | Visual proof sheet (16/32/64/192px, light/dark, app-icon frame, credit pairing) |
| `docs/design/brand/round2/` | Round-2 exploration: candidates, review sheet, rationale (candidate D shipped) |
| `01 BRAND ASSETS/` | Complete PWE/Paradise delivery kit, tokens, architecture rules, normalized exports and SHA-256 manifest |
| `/favicon.svg` | Theme-aware vector favicon |
| `/logo.png` (800×203) | Lockup, navy-on-transparent (light surfaces) |
| `/logo-light.png` (800×203) | Lockup, white-on-transparent (dark surfaces) |
| `/icon-192.png`, `/icon-512.png` | PWA icons, navy tile (any + maskable safe) |
| `/apple-touch-icon.png` (180) | iOS icon, opaque navy tile |

## 10. 品牌架构 / Brand Architecture

Two identities, one family system. The **product brand** is **PWE Studio**
(SaaS or Edition) and keeps the Crafted-P mark. The **producer/parent brand**
is **Paradise Production · 天域文创** and keeps its wing. Their shared navy,
amber and four-point spark establish lineage; neither mark replaces the other.

- **Product brand**: PWE Studio SaaS. Brand story one-liner:
  「PWE = Paradise WE，与创作者共有的一方天域」— "Paradise WE", the shared
  paradise the platform builds with its creators. The spark in the P is that
  idea drawn: the creative energy the structure exists to hold.
- **Producer/parent identity**: Paradise Production · 天域文创. It has a
  wing symbol plus approved A/B/C lockups. Lockup C is the approved joint
  sales/marketing endorsement; it never merges with the Crafted-P.

**Canonical compact credit line:**

> A PARADISE PRODUCTION · 天域文创出品

**Typography treatment (source of truth for all HTML surfaces):**

```css
.producer-credit {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  font-size: 10px;              /* NEVER larger than 11px-equivalent in context */
  font-weight: 600;
  letter-spacing: 0.08em;       /* small-caps feel for the Latin part */
  text-transform: uppercase;    /* Latin renders as caps; CJK unaffected */
  color: #64748B;               /* light surfaces (Slate 500) */
}
/* dark surfaces (#0E1729 or darker) */
.dark .producer-credit, [data-theme="dark"] .producer-credit {
  color: #94A3B8;               /* Slate 400 */
}
```

Placement rules:

- **Allowed**: Paradise Lockup C on sales-deck cover/closing and joint launch
  material; compact text credit on Super Admin login/footer, README and
  PWE Studio Edition tenant footer.
- **SaaS tenant boundary**: Paradise is forbidden on tenant Portal,
  Register, CMS and tenant-branded Studio Admin content.
- **Edition exception**: the compact text credit is shown by default on the
  tenant Portal. Set `STUDIOSAAS_SHOW_PRODUCER_CREDIT=0` only where the
  customer agreement permits paid attribution removal.
- Never place the producer mark inside the Crafted-P clearspace, merge the
  two marks, or turn the attribution into a heading, button or link.
- Reference artwork: `docs/design/brand/credit-line.svg` (+`-dark`). These
  are documentation aids; HTML surfaces implement the CSS above (the credit
  line MAY use the system font — unlike mark and wordmark, it is text, not
  authored geometry).

## 11. Changelog

- **v3.0 (v7.8.0, 2026-07-27)** — aligned PWE and Paradise to Family Navy
  `#0E1729`, Family Amber `#F5B335` and Warm Paper `#F7F5F2`; retained the
  Crafted-P as the product mark and the Paradise wing as the producer mark;
  documented Lockups A/B/C; added the mode-aware Edition attribution rule and
  the complete validated delivery kit under `01 BRAND ASSETS/`.
- **Round 2 (v7.7.7, 2026-07-27)** — monoline mark replaced by the solid
  "Crafted P" (round-2 candidate D) after client review: 64 → **82/100** on
  the client acceptance rubric (only candidate above the 75 replacement
  threshold). Spark moved from beside the baseline into the bowl as the
  counter; wordmark "P" re-drawn to echo the new bowl proportion; lockup
  mark scale 0.78 → 0.75 with wider mark→text gap; favicon switched from
  stroked to filled paths (theme-aware behavior unchanged). Exploration
  record: `docs/design/brand/round2/`. Added §10 brand architecture with the
  Paradise Production producer credit.
- **Round 1 (v7.7.x, 2026-07-27)** — initial identity: monoline geometric P
  + baseline spark, wordmark, asset pipeline.
