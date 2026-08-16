# PWE Studio — user manual, phases A and B done; screenshots next (2026-08-03)

Medium decided and recorded in `docs/design/User_Manual_Plan_2026-08-03.md`:
**one HTML document, an `@media print` stylesheet for the PDF.** Not two
artefacts. A PDF is a second copy of facts that move every release, and this
project has been bitten by that pattern three times already.

## A — `docs/guides/` refreshed to v8.2.20, and now tested

1,327 lines of accurate, backend-aligned content sitting on a **v8.1.0
baseline through nine releases**. Every claim was re-checked against code.

Wrong and now fixed:

* Super Admin guide said the audit log had **no search or pagination** —
  v8.2.11 added both.
* It said a plan **could not be created from the console** because the code
  field was disabled — v8.2.20 made it editable.
* It documented a **Commercial Attention** card that v8.2.11 deleted.
* The permission matrix had **no `courses:write` row at all**, and stated the
  front desk's portfolio boundary as "no write" when the backend gives it
  **no read either** — that decides what a receptionist sees of a child's photos.
* The Owner guide described the theme preview as nine flat swatches; v8.2.7–9
  split it into six theme colours and three status colours solved per theme,
  which is the whole change.

Added: 30 audit action types with readable summaries, the 30-megapixel image
ceiling (and that uploads worked at all only from v8.2.6), archive/delete
becoming usable in v8.2.10, retention windows, and plans no longer publishing
themselves.

**`backend/tests/test_user_guides.py` is the point.** These drifted because
nothing checked them — no page 500s, no test goes red, and the reader cannot
tell. It parses the permission matrix out of `README.md` and compares it with
`ROLE_PERMISSIONS` row by row, checks every counted claim against its source
(audit actions, status colours, theme list, pixel ceiling, retention windows,
CMS tabs), and asserts the three superseded claims cannot come back.

## B — the manual shell, readable now, screenshots pending

`manual.html` + `/assets/manual.css` + `/assets/manual.js`, served at
**`/manual/` (en) and `/zh/manual/` (zh)** through the same `apply_language`
the home page uses. Twelve sections ordered by a studio's week rather than by
the menu, each as *what to do → screenshot → what people get wrong*.

* **Screenshot slots are in place** with captions and `.ui-shot` framing;
  the images themselves are phase C. Callout numbers will be **DOM text, not
  pixels** — so they translate, get read out, and follow the theme.
* **`manual.css` restates no family hex.** It reads `--pwe-family-*` from
  `ui-tokens.css`. This is the fourth page to carry the palette and the
  previous three drifted onto a retired one by each holding a copy.
* **φ where it works**: `--measure: 61.8ch` for the reading column, Fibonacci
  vertical rhythm, φ^(k/2) type. The contents sidebar is sized by its content
  — 38.2% would be a 440px navigation column, which is φ as decoration.
* **Print is the PDF**: contents and search removed, `@page` margins, sections
  break to a fresh page, link targets printed after the text, and `[hidden]`
  forced visible so a filtered screen cannot print a manual with sections
  missing. The print button clears the filter first.
* **Section 09 stops at "what the platform can and cannot do"** — no console
  instructions. Asserted: the manual contains no `/platform-admin`.

Measured: no contrast pair below 4.5:1 in either theme, no horizontal overflow
at 390px, contents collapse and every bar control is 44×44 (it was 41×43 —
fixed), wide tables scroll inside their own box.

## C — next: screenshots

Capture against the local instance and the `lets-paint-showcase` tenant (its
data is synthetic by design, which is why it exists). Write
`docs/design/manual_shots.md` first — path, role, viewport and required page
state per shot — so the set can be retaken on a later release instead of
re-derived. Budget ~30 images, 2–3.5 MB, all lazy-loaded; state in the manual
that a studio on another theme sees different colours in the same places.

Not deployed. 510 tests pass.

---

