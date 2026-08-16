# PWE Studio v8.6.0 — the studio can finally show its own work (2026-08-07)

Plan written first: `docs/design/Showcase_Section.md`. Read that for the
reasoning; this records what shipped and what the browser said about it.

## Why it is not the student gallery

A portal could prove what students had made and not what the studio can do.
The principal section was a portrait and a paragraph — a claim, not evidence.

The two are separate sections because they differ in every dimension that
matters: author, consent model, provenance, and the question they answer.
Merging them would give "作品" two meanings on one page and put a commercial
portfolio under the same heading as student practice.

Reading order is the argument, and it is asserted:

```
about（空间） → artist（主理人） → showcase（成果） → courses → gallery（学员）
这是空间 → 这是教你的人 → 这是他的作品 → 这是课程 → 这是学员学成的样子
```

## Video: linked, whitelisted, and not requested until asked

`backend/studiosaas/video_embed.py`. Three providers, and the parse is the
security boundary rather than a rewrite: only a recognised provider and an id
matching `[A-Za-z0-9_-]` survive it, and the frame URL is built from OUR
template. **Nothing a studio types can reach the DOM.** Vimeo private hashes
are dropped on purpose — we do not republish a link its owner kept unlisted.

`frame-src` was ABSENT from the CSP, which means it fell back to
`default-src 'self'`. Every embed would have been blocked with no error
anywhere — the third time this exact failure mode has appeared in two
releases (the webfont, then the fonts directory, now this). The origins now
come from `video_embed.EMBED_ORIGINS`, so a provider added without a policy
entry is impossible, and the test reads the header off a **real response**
rather than off the source.

Click-to-play, not a bare embed: a YouTube iframe is several hundred KB of
third-party JavaScript per tile, spent before anyone asked to watch — and
spent by the visitor's phone. Verified in the browser: **0 third-party
requests before the click, 1 iframe after**, `youtube-nocookie`, no `allow`
attribute (a frame that can autoplay can autoplay again on re-render).

## Golden ratio: where it is, and where it deliberately is not

φ is in the **column split** — `--ui-golden-columns`, 61.8 / 38.2 — and
nowhere else. That was a correction forced by measurement, not a preference:

> With columns of 1.618k and k, a 1.618:1 lead tile is exactly k tall while
> the two stacked squares beside it are 2k + gap. **They cannot both be
> golden.** The first attempt claimed they matched and left a 447px hole under
> the lead at 1440px — measured, not guessed.

So the lead fills its two-row span instead and comes out portrait, which is
the better crop for a painting anyway. Measured after the fix at 1440px:
lead top = second top, lead bottom = third bottom, **0px on both**.

Two grids rather than one clever one: the lead block, then an equal grid for
tiles four and up. A `grid-column: 1 / -1` override would have silently fought
the φ template.

## The play button was invisible on exactly the art a studio posts

The first version relied on a scrim over the photograph. Measured:

| photograph behind it | glyph contrast |
|---|---|
| near-white | **1.22:1** |
| mid grey | 4.47:1 (still under AA) |
| black | 17.35:1 |

A light painting is not an edge case in an art studio, it is the common case.
The glyph now carries its own opaque ink disc: **16.27:1 on every image**,
54×54, a real `<button>` with an `aria-label` and a focus ring. Its separator
is localised too — a full-width colon inside an English label reads as a typo
to a screen reader, not as a style.

No shadow on it: `test_shape_language` caught an invented `box-shadow` and was
right to. The product has two elevations and neither is for a 54px control.

## Studio Admin

Its own tab. Twelve items × (photo + two bilingual texts + a link) would have
doubled the length of the Website tab. Reorder, remove, a `Lead` badge on the
first because it genuinely renders larger, and the video link is described the
moment it is typed rather than at Save.

The browser's provider check is **feedback only** — the raw link is what gets
submitted, and the server is the only thing that decides what a link becomes.
A second parser in the trust path would be a parser the attacker controls.

Publish verification compares what both sides can answer (photo, title,
whether a video is attached): the payload carries a raw link, the brand comes
back with a parsed provider and id, so comparing the link would fail every
publish that contained one.

## Local tenant workspaces

Production is the source of truth. Four local directories — `dance-dance`,
`lets-play-game`, `lets-play-piano`, `ruby-studio` — were stale generated
copies of tenants that no longer exist; git history is the archive. Kept:
`lets-paint-studio` (live) and `lets-paint-showcase` (required by the
standalone bundle, excluded from the SaaS one — `verify_release_bundles.sh`
asserts both).

`test_tenant_surfaces.py` had that set typed into it as a tuple. It now reads
the directory, so archiving a workspace is a one-step change instead of a red
suite, and a workspace that stops rendering still fails.

## Gate

- **1461 passed, 7 skipped**; palette checker **1080 assertions, 0 failures**
- CSP on the wire: `frame-src 'self' https://player.bilibili.com
  https://player.vimeo.com https://www.youtube-nocookie.com`
- 1440px: column split 0.607 (gap accounts for the rest of .618), lead/second
  and lead/third aligned to 0px, three equal tiles below, no horizontal
  overflow. 430px: single column, 4:5 lead, no overflow.
- Click-to-play: 0 third-party requests before, correct nocookie src after,
  no CSP refusal in the console.

## Not done

- No lightbox. Focus trap, Esc, back-button and mobile gestures all have to be
  right or it is worse than nothing; this release makes the board good first.
- No filters or categories — pointless under twelve items.
- The CMS shell still has no accent tokens until `/brand` answers, so
  `bg-indigo-*` is unpainted on first paint outside the chrome layer.

---

