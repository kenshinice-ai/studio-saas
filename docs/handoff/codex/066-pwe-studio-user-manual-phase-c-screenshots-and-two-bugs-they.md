# PWE Studio — user manual phase C: screenshots, and two bugs they exposed (2026-08-03)

22 images (11 screens × 2 languages), 0.94 MB, wired into `/manual/` with
callouts. **Every screen is captured twice** — a Chinese screenshot in the
English manual reads as a different install, not a different language.

## The shot list runs

`backend/scripts/capture_manual_shots.py` + `docs/design/manual_shots.md`.
Chrome's `--screenshot` flag cannot carry a session and half these screens are
behind a login, so the script signs in over HTTP, hands the cookie to a
headless Chrome over the DevTools Protocol, clicks the tab **by its visible
label**, and captures. A renamed tab therefore fails the capture loudly rather
than photographing the wrong screen. The ~60 lines of WebSocket framing are
there because CDP is JSON-over-WS and this repository has no WS dependency.

Source is `lets-paint-showcase`, whose records are synthetic by construction.
No screenshot can contain a real student. Credentials are read from the 0600
file `reset_professional_demo.py` writes — never an argument, never printed.

## Two bugs the run exposed

**1 · The English CMS is incomplete.** Capturing every screen in English put
the gaps on a contact sheet: **22 Chinese strings on the roster alone**. The
self-contained ones are now in `cms-i18n.js` (+30 entries: `网站与品牌`,
`固定课表 ICS`, weekday abbreviations, the empty-roster hint, `已签`/`未签`,
the stats hints…). **Known gap, not fixed:** number-adjacent fragments — `人`,
`次`, `笔`, `条`, `分钟` — which React splits into their own text nodes.
Translating those in isolation would reorder the phrase rather than translate
it; the dictionary needs pattern support first.

**2 · `/assets/<path>` flattened every path to a basename**, so
`/assets/manual/03-roster.en.webp` 404'd — and the symptom was a blank column,
not a broken route. Fixed with an allowlist of subdirectory names
(`ASSET_SUBDIRECTORIES = {'manual'}`) rather than a traversal check: `..` is
not the only way out of a directory, and a fixed set of names cannot be talked
into anything. The leaf is still reduced to a basename.

Two smaller ones: the roster shot would have been an **empty state** because
today has no class (`class_schedules.weekday` is 1 = Monday, Python's is 0 —
off by one, and it still produced a plausible screenshot); and
`reset_professional_demo.py` had **v8.1.0 typed into its credentials header**,
now read from VERSION.

## What is asserted

`test_manual.py` grew to 24 cases: every referenced image exists, every screen
has both languages, alt text is present (word count for English, character
count for Chinese — ten Chinese characters carry what four English words do),
explicit dimensions and lazy loading, the set stays under 3 MB with **no
unreferenced images shipping publicly** (v8.2.18's 9.2 MB of orphaned demo art
was in the sibling directory), every captured shot appears in the spec, the
callouts are DOM text rather than pixels, and the assets route serves
`manual/` and refuses everything else.

## Left for the reader to judge

* Screenshots are one theme in light mode; the manual says so at the top —
  "the colours will not match, the positions will".
* Phone captures are constrained to 400px. Stretching a 390px screen to the
  article width would show text at twice the size it is on the device.
* Not deployed. 518 tests pass.

---

