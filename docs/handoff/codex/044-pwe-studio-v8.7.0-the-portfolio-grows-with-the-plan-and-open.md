# PWE Studio v8.7.0 — the portfolio grows with the plan, and opens properly (2026-08-07)

Plans: `docs/design/Showcase_Round_2.md`, `docs/design/Showcase_Plan_Limits.md`.
Owner's decisions, settled before any code: **15 / 60 / 150**, **no unlimited
tier at all**, categories **not** plan-limited, and on downgrade keep
everything / publish what the plan allows / say so plainly.

Six pieces: A placeholders, B plan limit, C categories + own endpoint,
D upload, E lightbox, F release.

## A — every English-half field showed a Chinese placeholder

Product-wide and pre-existing, visible in the owner's screenshot: 「版块眉题 ·
English」 offered 「工作室作品」 as its example. `applyAttributes()` localised
`placeholder`, so `Founder & Principal`, `Courses & Classes` and the rest all
rendered Chinese under an English label.

**A placeholder has one job — show what to type — and it was showing the wrong
language to type in.**

Locked by id suffix (`/En\d*$/`), not by a hand-applied attribute: an
attribute is a thing to forget on the next bilingual pair. `title` and
`aria-label` still localise; those are interface chrome. Verified in the
browser in both console languages.

## B — `plans.showcase_limit`, 15 / 60 / 150

A column with a CHECK, matching this table's convention (numeric ceilings are
columns; `features` holds booleans). No unlimited tier, so no per-tenant
override, no `-1`/NULL sentinel, and no `if limit is None` branches anywhere.

**The load-bearing part is what did NOT change.** v8.6.0 truncated in
`_normalize_website_profile` at `[:SHOWCASE_ITEM_LIMIT]`. Had that survived
contact with a per-plan cap, a studio moving growth → starter would have lost
135 works **the next time it saved anything at all** — changing a phone number
would have destroyed a portfolio, silently. The same shape as the v8.5.4
outage: an innocuous truncation operating on someone else's data.

Now: `SHOWCASE_STORAGE_CEILING = 500`, plan-independent, purely to bound a
hostile request. Publishing is limited on read. `test_the_write_path_does_not_
cap_by_plan` asserts 200 works survive normalisation.

Wired through the plan editor, the public pricing cards and `pricing.md` —
omitting the pricing page would have left the thing being sold invisible on
the page that sells it.

## C — categories, and the board on its own endpoint

- Category ids are **server-generated, never derived from the label**, so a
  rename cannot detach the works under it. Deleting a drawer never deletes
  what is in it.
- `GET /v1/public/<slug>/showcase?category=&offset=`, 12 a page.
- **The plan limit is applied before the category filter.** The other order
  lets an entry-plan studio publish its archive one drawer at a time —
  measured: 10 works in one category under a 15-work plan.
- `showcase_limit_for()` never raises; a missing plan row costs part of a
  board for one request, never the page.

**The board left `/brand` deliberately.** That response carries every word and
image of a portal, and v8.5.4 proved what one unreadable field in it costs.

**Which re-creates the v8.5.3 race on purpose**, with the fix designed in
rather than discovered. Measured in the browser:

| order | result |
|---|---|
| board first, switch unknown | 3 tiles, nav shown |
| then switch arrives OFF | **0 tiles, nav hidden, section unresolved** |
| switch ON, board empty | hidden |
| switch ON, board has works | shown |

Caught during that check: the filter chips live outside the grid and survived
the teardown, leaving a row of filters above a hidden section. Fixed.

## D — upload

Was: one file input per card, one file at a time, no compression.

**Client-side downscale is the biggest single win here and it is not about our
bandwidth.** A 24MP phone photo is ~8MB against a 10MB per-file limit, so a
studio photographing its own work was one portrait away from a rejection it
could not explain. Measured in the browser: a 4000×3000 JPEG becomes 2400×1800
at **24.5% of its size**.

`imageOrientation: 'from-image'` is load-bearing — canvas does not apply EXIF
rotation, and without it every portrait phone photo ships lying on its side.
Verified with a hand-built JPEG carrying EXIF Orientation 6.

Two guards worth keeping: a re-encode that comes out **larger** is discarded
(a flat PNG easily does), and `createImageBitmap` failing falls back to the
original file rather than blocking the upload.

Also: one dropzone, multi-select, drag and drop, optimistic cards with local
previews, real per-file progress (XHR — `fetch` cannot report upload
progress, and an unmeasured progress bar is a lie), concurrency 2, per-file
failure. And **uploads patch one card instead of rebuilding the list**, so
finishing an upload no longer destroys a caption being typed three cards down.

## E — lightbox

Native `<dialog>` + `showModal()`: focus trap, Escape and inertness come free.
No `showModal` → the old behaviour is kept. **There is no half version of
this; a lightbox you cannot close is worse than none.**

**The back button closes it.** On a phone, back is how people dismiss anything
covering the screen — before this, tapping it to leave a photograph would have
taken the visitor off the studio's site entirely. This is the most commonly
missed part of a lightbox and the most damaging.

Measured on a clean page load:

```
opened from tile 2 -> open, focus inside, "2 / 4", body locked, gutter stable
Escape             -> closed, focus back on that tile, history state clean
back button        -> closed AND still on the same page
play               -> 0 iframes before, 1 nocookie iframe inside after
close              -> 0 iframes anywhere (the video actually stops)
Esc x3             -> no history leak, length stable
```

Arrows and swipe move; swipe-down dismisses; only n±1 preload; the scroll lock
uses `scrollbar-gutter: stable` so opening does not jolt the page sideways.

`test_dark_framework` caught `&#8592;` / `&#10005;` reading as hex colour
literals — a false positive that pointed at a real rule (icons are SVG, not
characters). Replaced with inline SVG, which also stops them rendering at the
mercy of whatever font resolves them.

## Gate

- **1483 passed, 7 skipped**; palette checker **1080 assertions, 0 failures**
- migration `0024_plan_showcase_limit.sql` applied; starter 15 / studio 60 /
  growth 150 confirmed in production

## Still open

- No filters beyond categories, and no per-work deep links — both deliberate,
  see `Showcase_Round_2.md` §5.
- The CMS shell still has no accent tokens until `/brand` answers, so
  `bg-indigo-*` is unpainted on first paint outside the chrome layer.
- No endpoint reports media usage, so the console shows the publish count and
  the resize rule instead of a storage figure. Inventing a number there would
  have been worse than saying nothing.

---

