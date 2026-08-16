# PWE Studio v8.5.4 — five portals had been serving 500 for their whole content payload (2026-08-07)

Started as "find the text and images this one tenant wrote". Nothing had been
lost. **Five of six live portals had been blank since v8.5.2, and every check
we own said the release was healthy.**

## The outage

`GET /v1/public/ruby-s-studio/brand` → 500. The page itself was 200, which is
why it looked like missing content rather than an outage: a portal's copy,
images, principal bio and contact details all travel in that one response.

Production log:

```
ValueError: Visual style is not recognised.
```

v8.5.2 renamed the single-palette style id `studio` → `custom`. Nothing
migrated the rows:

```
hong-s-studio  | studio | hue=195.0     lets-paint-showcase | atelier-clay
jjl-s-studio   | studio | hue=25.0      lets-paint-studio   | studio | hue=17.0
n-piano-studio | studio | hue=286.2     ruby-s-studio       | studio | hue=341.8
```

And the READ path was the WRITE validator. `api_v1.py` re-normalised the
stored theme on every brand read to fill in tokens added since the record was
written — reasonable — but `_normalize_visual_theme` **raises** on an id it
does not know, because on a write that is the correct behaviour.

**Renaming a key is a data migration whether or not anyone runs one.** A
stored record is written by whichever release the owner last saved under, and
the read path meets all of them.

### Nothing was lost

Every field the tenant wrote is intact and was intact throughout — 2189 bytes
of `localized_copy`, a 556-byte bilingual `principal_profile`, `faq_items`,
`registration_profile`, `hero_profile`, and all 10 media assets (logo and hero
both still serve 200). Replayed against the fix, `ruby-s-studio` resolves to
`custom` at hue 341.8 with accent `#883850` — the rose it picked.

### Three parts, because the bug needed all three to be missing

1. **`presets.RETIRED_STYLE_ALIASES` + `resolve_style_id()`.** `studio` →
   `custom`, forever. Cheaper than a migration and strictly safer: a migration
   only repairs the rows that existed when it ran, this also catches a record
   restored from an older backup. Entries are never removed.

2. **`_stored_visual_theme()` on the read path**, with
   `_normalize_visual_theme(..., strict=False)` under it. The invariant, stated
   once: **a stored theme has two possible outcomes — the studio's theme or the
   default theme — and never an exception.** A stored record is not user input;
   there is no owner present to tell, and raising renders nothing.
   `test_stored_theme_tolerance.py` fires eleven shapes of bad stored value at
   it, including the real rows.

3. **The deploy gate now asks about the data.** `/v1/health?deep=1` reports
   `themes.unreadable` — how many live tenants store a theme this release
   cannot read — and `pwestudio_remote.sh deploy` refuses to keep a release
   unless it is 0. `SELECT 1` proved the database answered; it never proved
   this release could render the tenants inside it. Deliberately **not** a 503:
   deep health drives the container healthcheck, and a stale row is no reason
   to restart a service that is answering every request.

## About was an orphan, and Save was deleting it

`show_about` plus seven sibling fields were stored, validated, and fully
rendered by the portal — bilingual eyebrow/title/body, a numbered highlight
list, a six-image carousel — with **no control anywhere in Studio Admin**.

Worse than invisible. `_normalize_website_profile` rebuilds the profile from
the payload alone; it does not merge. So **every Save from that page erased
all seven**, which is also why the flagship tenant's reclaimed `seo_title`
never survived its first Save Draft.

Added: the seventh switch, an About disclosure (bilingual copy, up to six
uploaded photos via a new `target=about`, three highlight slots), an SEO
disclosure, and all of it in the save payload *and* the publish verification.

`test_the_admin_sends_every_field_the_server_stores` reads the **server's**
field list out of `_normalize_website_profile` and checks each one appears in
the admin payload, so the next omission fails in CI rather than at somebody's
Save. Verified by deleting a field and watching it go red.

## The empty hero was a shaped void

`background_style: image` with no image uploaded rendered the decorative
gradient inside the chosen hero shape — a large blob exactly where a
photograph obviously belongs. It collapses to the one-column `hero-minimal`
now, and so does an image that fails to load, because "did not load" and "is
not there" are the same thing to a visitor. `soft` is untouched: that is a
studio choosing the gradient on purpose.

## The CMS was two full slabs of accent before a single button

`bg-indigo-900` on the sidebar, the mobile tab bar and the mobile top bar. The
Tailwind config maps `indigo` → `role('accent')`, so `-900` is
`--accent-pressed`: **the largest surfaces in the app were the studio's accent,
at full saturation, permanently.** Design_Constraints §1.1 allows one per
screen.

Replaced with a `.cms-chrome` token layer. The accent is not deleted, it is
spent where it means something: the active tab, and the one link out to Studio
Admin.

Two things here were **measured in the browser, and both changed the design**:

- The active item was going to sit on `--bg2`. Against `--bg2` the
  `--accent-soft` chip is **1.00:1 with +6 chroma — invisible**, the same trap
  §1.3 documents for the status chips. On `--panel` it is 1.25:1 and +21
  chroma, and its border goes 1.66 → 2.07:1. The rail is `--panel`.
- On the CMS shell the **entire accent family is undefined** until `/brand`
  answers and the runtime sets it. A bare `var(--accent-soft)` computes to an
  invalid value, the declaration drops, and the current tab has **no indicator
  at all** — worst precisely when `/brand` fails, which is what this release
  is fixing. Every accent token in the chrome now carries a neutral fallback.
  The fallbacks are **tokens, never literals**, so colour still has one source.

Final measurements, both before and after `/brand` answers: idle text 10.05:1,
active text on chip 9.61:1 (14.46 on the fallback), inset border present in
both, mobile tab rule 7.55:1 (16.27 fallback).

## The display face had never once loaded

`tenant-template` linked `fonts.googleapis.com` while this site's own CSP
(`server.py`: `default-src 'self'`, `font-src 'self' data:`) blocked both the
stylesheet and the font file. So `"Cormorant Garamond"` never resolved —
**every portal has been rendering Georgia since the CSP shipped**, while still
paying for two requests per page load that could not succeed. The template
comment describing the intent had been true of the intent and false of the
code.

Self-hosted instead (approved: 4 × woff2, ~142 KB, SIL OFL 1.1, licence
shipped at `/assets/fonts/OFL.txt`). It is a variable font, so 300–700 costs
one file per subset, and `unicode-range` means a CJK-only page fetches
neither. This also delivers what the comment always claimed: mainland visitors
no longer wait on Google.

Two traps avoided, both worth keeping:

- The preload URL and the `@font-face` `src:` must be **byte-identical**. A
  `?v=` on one and not the other is two URLs, and the face downloads twice on
  first paint. Neither carries one.
- Which means the font cannot be cache-busted by version — so
  `_cache_versioned_asset` sends `font/*` as immutable unconditionally. Safe
  because the face, style and unicode subset are in the filename: a different
  cut is a different file, not new bytes at the same URL.

Verified in the browser: `latin normal` reports `loaded`, the other three
subsets stay `unloaded` (correct — nothing on the page needs them), and the
same string renders 408.3px in Cormorant vs 484.9px in Georgia, which is proof
it is being *used* and not merely fetched.

## One more thing the screenshot found

With the portal rendering again, `ruby-s-studio` still showed the decorative
gradient blob — while holding a hero photograph it had uploaded. Cause: before
v8.4.0, uploading a hero image filled `hero_image_url` and did not move
`background_style` off `soft`, and the portal only reveals `.hero-art img`
under `body.hero-image`. Upload succeeded, Save succeeded, Publish succeeded,
and the photograph was never on the site. v8.4.0 closed the dead end for new
uploads but repaired none of the existing records, and **a studio has no way
to discover this**: nothing is broken, there is just a shape where their
painting should be.

`backend/scripts/show_uploaded_hero_images.py` reports and repairs it (dry-run
by default). Exactly one tenant was affected across all six; backed up, then
applied to `ruby-s-studio`. Her painting is now the hero. Reversible from
Studio Admin in one click, and the photograph was never at risk either way.

## Gate

- **1423 passed, 7 skipped**
- palette checker: 18 theme-modes × 60 pairs = **1080 assertions, 0 failures**
- 6 tenant workspaces regenerated from the template; no Google Fonts link left
  in any portal
- `/assets/fonts/*.woff2` → 200, `font/woff2`, `immutable`

## Still open

- The CMS shell has no accent tokens until `/brand` answers, so every
  `bg-indigo-*` is unpainted on first paint. Pre-existing, now survivable
  everywhere the chrome touches, but the flash is still there for the rest.
- `tenants/ruby-studio/` exists locally while the live slug is `ruby-s-studio`
  — the local workspace set and production have drifted.

---

