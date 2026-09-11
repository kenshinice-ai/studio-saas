# PWE Studio — Brand Identity

Version 4.2 — 2026-09-11. This is the source of truth for the PWE Studio
product identity and its relationship to the house brand PWE · 天域, to the
Paradise Production film and creative line, and to tenant-owned studio
identities. The delivery kit lives in `01 BRAND ASSETS/`.

`docs/brand-guidelines.md` is a compatibility copy for tooling that expects
that conventional path. `docs/design/Brand_Identity.md` remains canonical;
update it first and keep the compatibility copy byte-for-byte aligned.

All PWE assets are generated deterministically from
`docs/design/brand/render_assets.py`. Do not hand-edit generated SVG or PNG
files.

## 1. Brand idea — Feather Star

The Feather Star is a compact story about creative progress:

- The **four-point star is the starting point of creativity**.
- The **three feather blades represent growth, ascent and possibility**.
- Together they move from a single creative spark toward an open, upward
  future.

This meaning is immutable. Short copy may simplify the language, but it must
not assign different meanings to the star or the three feathers.

The geometry is informed by the golden-ratio sequence **136 : 84 : 52**. The
ratio controls the source lengths of the three feathers, producing hierarchy
without making any feather ornamental or redundant.

## 2. Construction

The mark uses a 64 × 64 source grid and consists of three closed feather paths
plus one four-point star.

| Element | Canonical value |
|---|---|
| Mark viewBox | `0 0 64 64` |
| Mark bounding box | `(8.00, 6.30) → (54.20, 57.40)` |
| Optical centre | `(29.20, 31.85)` |
| Star centre | `(14.30, 51.10)` |
| Star radius | `6.30` |
| Feather source ratio | `136 : 84 : 52` |

The feathers use Family Navy on light backgrounds and white on Family Navy.
The star uses Family Amber. In one-colour production, all four forms use the
same ink.

## 3. Wordmark and naming

The only approved product lockup reads:

> PWE STUDIO

`PWE` and `STUDIO` are authored vector outlines arranged on two lines. The
lockup viewBox is `160 × 64`; no live font is used.

Rules:

- Never add “SaaS” or “Edition” to the logo.
- In running text, use **PWE Studio**.
- “SaaS” and “Edition” are delivery-model descriptors only.
- Do not typeset `PWE STUDIO` as a substitute logo.

## 4. Colour palette

| Role | Name | Hex | Usage |
|---|---|---|---|
| Brand ink | Family Navy | `#0E1729` | Mark, wordmark and platform shell |
| Raised surface | Family Navy Raised | `#16233D` | Dark gradients and elevated panels |
| Creative origin | Family Amber | `#F5B335` | Four-point star and Paradise family accent |
| Accessible amber text | Amber Text | `#A16207` | Small text on light surfaces |
| Canvas | Warm Paper | `#F7F5F2` | Marketing and product background |
| Support neutrals | Slate | `#475569`, `#64748B`, `#E2E8F0` | Copy and dividers |
| Product interaction | Console Blue | `#3B82F6`, `#2563EB` | Buttons and links, never the logo |

Family Amber is an identity colour, not a general warning colour.

## 5. Typography

Product UI uses the bilingual system stack:

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
             "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB",
             "Microsoft YaHei", sans-serif;
```

Use 28–36 px / 700 for display moments, 20 px / 600 for section headings and
15–16 px / 400 for body copy. Small labels use 11–12 px / 600 with modest
letter spacing.

## 6. Clearspace and minimum sizes

- Keep clearspace of at least the star diameter around the mark or lockup.
- Minimum mark size: 16 px.
- Minimum lockup width: 120 px; below this use the mark alone.
- App icons keep the mark inside the 80% maskable safe zone.

## 7. Light, dark and one-colour use

| Surface | Asset |
|---|---|
| White / Warm Paper | `pwe-mark.svg`, `pwe-logo.svg`, root `logo.png` and `pwe-mark.svg` |
| Family Navy | `pwe-mark-dark.svg`, `pwe-logo-dark.svg`, root `logo-light.png` and `pwe-mark-dark.svg` |
| Browser tab | root `favicon.svg`, theme-aware |
| App icon | `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` |

For one-colour reproduction, use all forms in navy, white or black. Do not
delete the star; its role as the creative origin must remain visible.

### 7.1 The product website runs on the shared design language

`product-home.html` is authored dark — Family Navy end to end, Family Amber as
the single accent — and re-skinned onto Warm Paper when the visitor's system
asks for a light theme. Both themes are one set of rules driven by five surface
tokens (`--surface`, `--surface-2`, `--card`, `--ink`, `--accent`), so the
layout cannot fork between them.

The rule that makes this work is §4's, stated as a token: **Family Amber
`#F5B335` is a dark-surface colour** (9.83:1 on Family Navy, 1.70:1 on Warm
Paper). Small amber things — eyebrows, rules, borders, focus rings — resolve
through `--accent`, which is `#F5B335` on navy and the accessible
`#A16207` on paper. Amber as a *fill* keeps the bright tone in both themes,
because a navy label on an amber pill measures 9.83:1 either way.

Proportion is shared with the Paradise Production site rather than re-invented:
type advances in φ^(k/2), spacing follows the Fibonacci integers, and primary
splits land on 61.8 / 38.2. Two products from one studio should be recognisable
as such without either of them borrowing the other's logo.

## 8. Correct use

Do:

- Use generated assets without changing their proportions.
- Keep the star and all three feathers.
- Use the mark alone at small sizes.
- Preserve tenant identity on tenant-owned surfaces.

Do not:

- Rotate, outline, shadow, gradient or distort the mark.
- Reorder or reinterpret the three feathers.
- Add “SaaS” to the lockup.
- merge the Feather Star with the Paradise wing.
- use a PWE or Paradise logo as the fallback tenant logo.

## 9. Brand architecture

There are four distinct ownership layers:

1. **PWE · 天域** — the house and parent brand. Its website is the root of
   `pwestudio.online` (from v10.18.0 nginx serves `/`, `/zh/` and the house's
   section prefixes ahead of the application).
2. **PWE Studio** — the house's SaaS product line; product identity on the
   product site (`/studio`), Super Admin, platform packaging and sales
   materials. The Feather Star stays its mark; a wing-family mark for the
   house's product lines is planned and nothing is swapped until it lands.
3. **Paradise Production · 天域影像** — the house's film and creative line.
   A sibling line of PWE Studio, no longer its producer or parent.
4. **Tenant studio** — primary identity in Studio Admin, CMS, Portal and
   Register.

Tenant top-left identity areas must show the configured tenant logo and studio
name. If no tenant logo exists, show the tenant name only. Never substitute a
PWE Studio, house or Paradise mark.

Canonical tenant footer:

> © 2026 [Tenant Name] · Powered by PWE

The credit is text only, 10–11 px, neutral slate and visually subordinate.
`STUDIOSAAS_SHOW_PRODUCER_CREDIT=0` may hide it only where a commercial
agreement permits attribution removal.

The product site and Super Admin use the PWE Studio mark as their primary
identity and the compact bilingual house credit:

> [PWE · 天域出品](/)

**This is PWE Studio's own credit, and it is a link.** The house's website is
at the root; a credit that names the house and then dead-ends is a weaker
signal than one a reader can follow. "出品" rather than "Powered by" because
on the product's own surfaces the relationship is authorship, not vendoring.
The product site's header wordmark also leads to the house at `/`; the
product's own home is `/studio`, which the footer wordmark, the canonical and
the language links name.

The tenant footer above keeps `Powered by PWE` unlinked. It is white-label
attribution on somebody else's site, often in English, and it is the line a
commercial agreement may remove — "出品" would overclaim there, and an
outbound link on a customer's page is not ours to add.

## 10. Integration inventory

| File | Purpose |
|---|---|
| `docs/design/brand/pwe-mark.svg` / `pwe-mark-dark.svg` | Feather Star mark |
| `docs/design/brand/pwe-logo.svg` / `pwe-logo-dark.svg` | PWE STUDIO lockup |
| `docs/design/brand/credit-line.svg` / `credit-line-dark.svg` | Credit-line reference (still renders the pre-v10.18.0 Paradise Production wording; regenerate with the wing-family mark, not by hand) |
| `docs/design/brand/render_assets.py` | Canonical geometry and renderer |
| `docs/design/brand/preview.html` | Visual proof sheet |
| `01 BRAND ASSETS/` | Delivery kit, architecture, tokens and manifest |
| `/favicon.svg` | Theme-aware platform favicon |
| `/logo.png` / `/logo-light.png` | 800 × 320 transparent lockups |
| `/icon-192.png`, `/icon-512.png` | PWA icons |
| `/apple-touch-icon.png` | 180 × 180 iOS icon |

## 11. Changelog

- **v4.2 (v10.18.0, 2026-09-11)** — PWE · 天域 becomes the house and parent
  brand, with its website at the root of `pwestudio.online`; PWE Studio is
  its SaaS product line at `/studio`; Paradise Production · 天域影像 is the
  house's film and creative line, no longer the producer (§9). Text only:
  tenant footers read `Powered by PWE`, the product site and Super Admin
  credit `PWE · 天域出品` linking to `/`. The Feather Star and every icon,
  image and generated asset are unchanged; the wing-family mark is planned.
- **v4.1 (v8.2.20, 2026-08-03)** — the product website adopts the shared
  dark-first design language and follows the visitor's system theme; the mark
  switches with it (§7.1). The producer credit became a link to
  `/paradise-production/` in v8.2.19 (§9).
- **v4.0 (2026-07-28)** — replaced the Crafted-P with the Feather Star;
  established the four-point star as creativity’s starting point and the
  three feathers as growth, ascent and possibility; removed “SaaS” from the
  product lockup; formalised tenant identity precedence and text-only Paradise
  footer credit.
- **v3.0 (v7.8.1, 2026-07-27)** — aligned PWE and Paradise to Family Navy,
  Family Amber and Warm Paper; added the validated delivery kit.
- **Round 2 (v7.7.7, 2026-07-27)** — shipped the Crafted-P identity, retained
  in history only.
