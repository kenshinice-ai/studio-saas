# Design System

> **StudioSaaS Brand & UI Reference**
> Last updated: 2026-07-29 · Brand family integration: v8.0.1

The visual system is generated, not hand-picked: every colour token is solved
for a measured WCAG contrast target by `docs/design/palette_gen.py`, and the
canonical values live in `backend/studiosaas/presets.py`
(`VISUAL_STYLE_PRESETS`). This document describes what exists in code; the
code is the source of truth.

---

## 1. Theme System

### Product family layer

The product shell uses the PWE / Paradise family tokens from
`01 BRAND ASSETS/brand-tokens.json`, mirrored in
`backend/frontend/assets/ui-tokens.css`:

| Token | Value | Scope |
|---|---|---|
| `--pwe-family-navy` | `#0E1729` | Product mark, platform shell, PWA theme |
| `--pwe-family-navy-raised` | `#16233D` | Raised dark brand panels |
| `--pwe-family-amber` | `#F5B335` | Mark/wing spark only |
| `--pwe-family-amber-text` | `#A16207` | Accessible amber text on light surfaces |
| `--pwe-warm-paper` | `#F7F5F2` | Product/marketing canvas |

These tokens never overwrite tenant themes or semantic success/warning/danger
colours. Tenant Portal, Register and CMS surfaces keep their published tenant
identity. The PWE family layer governs platform chrome and fallbacks.

### Golden-ratio hierarchy

The Feather Star uses the golden-ratio sequence `136 : 84 : 52`; v8.0.1
extends that geometry into layout hierarchy through semantic tokens in
`ui-tokens.css`:

| Token group | Values | Purpose |
|---|---|---|
| Layout | `1.618fr / 1fr` | Decision-oriented primary/secondary content |
| Spacing | `5, 8, 13, 21, 34, 55, 89px` | Predictable component and section rhythm |
| Type | `13, 16, 21, 34, 55px` | Restrained modular hierarchy |
| Motion | `144ms / 233ms` | Faster exits, calm entrances |
| Measure | `55ch` | Readable body-copy width |

Use the ratio only when one region is genuinely primary. Tables, repeated KPI
cards, mobile forms and peer controls stay equal-width when equal importance
is the clearer interaction model. Below 900–1024px, golden splits collapse to
one column; accessibility and content fit take priority over geometry.

Eight visual themes, each shipping a matched **light and dark** variant —
except `arcade-lime`, which is dark-only (a neon-lime accent cannot reach
4.5:1 on a light page without turning olive). That makes **15 theme-modes**
in total.

| Key | 中文名 | English | Recommended industry | Hue relationship | Modes |
|---|---|---|---|---|---|
| `atelier-clay` | 陶土工坊 | Atelier Clay | art | split-complementary | light + dark |
| `vintage-press` | 复古印刷 | Vintage Press | general (default) | split-complementary | light + dark |
| `studio-ink` | 黑白纸墨 | Studio Ink | — | neutral / monochrome | light + dark |
| `harbour-calm` | 静谧海港 | Harbour Calm | math, language | analogous | light + dark |
| `cedar-grove` | 雪松林 | Cedar Grove | sports | triadic | light + dark |
| `recital-plum` | 独奏紫 | Recital Plum | music | analogous | light + dark |
| `rehearsal-rose` | 排练玫瑰 | Rehearsal Rose | dance | split-complementary | light + dark |
| `arcade-lime` | 街机青柠 | Arcade Lime | game | split-complementary | **dark only** |

- Industry → theme mapping: `INDUSTRY_STYLE_RECOMMENDATIONS` in `presets.py`.
- Button shape and font mood are presentation choices carried beside the
  palette (`STYLE_SHAPE`): e.g. `atelier-clay` = soft/serif,
  `studio-ink` = sharp/modern, `recital-plum` = rounded/classic.
- `style_theme(style_id, scheme)` resolves a theme-mode with safe fallbacks:
  unknown ids fall back to the default style (`vintage-press`), and a missing
  mode falls back to the theme's first mode (so `arcade-lime` always renders
  dark).

## 2. Semantic Colour Tokens

Each theme-mode defines the same **21 semantic tokens** (plus a
`color_scheme` marker):

| Group | Tokens |
|---|---|
| Surfaces | `background_color`, `background_alt_color`, `panel_color` |
| Text | `text_color`, `text_soft_color`, `muted_text_color` |
| Borders | `border_color` (quiet dividers), `border_strong_color` (interactive boundaries, ≥3:1 — WCAG 1.4.11) |
| Accent | `accent_color`, `accent_text_color`, `accent_hover_color`, `accent_pressed_color` |
| Secondary accent | `secondary_accent_color`, `secondary_text_color` |
| Status | `success_color`, `warning_color`, `danger_color` (fixed hue anchors 152/36/6, nudged 4% toward the theme, lightness re-solved per surface) |
| Focus | `focus_ring_color` |
| Overlay | `scrim_color` |
| Disabled | `disabled_surface_color`, `disabled_text_color` |

**Every hex is reverse-solved from a WCAG contrast target by
`docs/design/palette_gen.py`, which asserts 26 contrast pairs per theme-mode
(390 assertions total). Never hand-edit a hex value** — change the generator
and re-emit, then re-run the assertions.

## 3. Style Layering

| Layer | File | Scope |
|---|---|---|
| Public surfaces | `backend/frontend/assets/portal-theme.css` | **Single source of truth** for the tenant portal (`/<slug>`) and the standalone register page (`/<slug>/register`). Default values are the `vintage-press` light theme; `/brand` overrides them per tenant at runtime. |
| Admin surfaces | `backend/frontend/assets/brand-system.css` | Shared brand language for admin pages (`--brand-*` roles built from the portal tokens; tenant branding may override `--brand`/`--tenant-primary` at runtime). |
| CMS icons | Inline SVG `Icon` component in `legacy-root/src/cms-app.jsx` | **No emoji as icons** — emoji glyphs differ across platforms and are read aloud by screen readers as descriptions (see `docs/Glossary.md`). |

Load order for public pages: `ui-tokens.css` → `portal-theme.css` →
`brand-system.css`.

## 4. Accessibility Rules (v7.4.0 remediation, completed in v7.5.0)

- **Focus ring:** `:focus-visible` gets a 2px outline with 2px offset on all
  interactive elements (`portal-theme.css` uses `--focus-ring`;
  `brand-system.css` uses `--brand-accent` plus the `--brand-focus-ring`
  box-shadow). Each theme carries its own solved `focus_ring_color`.
- **Touch targets:** minimum 44px (`--tap-min: 44px`; CMS controls use
  `min-h-[44px]`).
- **Reduced motion:** both stylesheets honour
  `@media (prefers-reduced-motion: reduce)` — portal durations collapse to
  0ms; brand-system disables animations/transitions/smooth-scroll globally.
- **Disabled states:** disabled controls use `disabled_surface_color` /
  `disabled_text_color` rather than opacity alone.
- Form labels, modal focus trap/restore, ARIA tab keyboard contract,
  keyboard-reachable lightbox, and per-field error reporting are release
  checks — see `docs/QA_Checklist.md`.

## 5. Commands

```bash
python3 docs/design/palette_gen.py            # verify (390 assertions)
python3 docs/design/palette_gen.py --table    # inspect every token
open docs/design/theme-proposal.html          # see all 15 theme-modes as real UI
```

Migrating existing tenants to regenerated themes (idempotent; never touches a
hand-tuned theme unless `--include-custom` is passed):

```bash
.venv/bin/python backend/scripts/migrate_visual_themes.py --dry-run
.venv/bin/python backend/scripts/migrate_visual_themes.py
```

## 6. Usage Guidelines

1. **Use the semantic tokens** — never hard-code hex values in pages.
2. **Interactive boundaries use `border_strong_color`**, not `border_color`.
3. **Hover/pressed move in one direction** (darker in light mode, lighter in
   dark) so states are never mistaken for each other.
4. **Icons + text** for primary actions; SVG `Icon` component only, no emoji.
5. **Error messages** must state a cause and a way out.
