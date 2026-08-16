# PWE Studio v8.5.3 — two section switches only reached the navigation (deployed 2026-08-06)

Audit prompted by a direct question: do the six section switches in Studio
Admin correspond one-to-one with the portal's sections? Two did not.

## The finding

| switch | portal section | how it was enforced | verdict |
|---|---|---|---|
| `show_principal` | `#artist` | `resolveSection('artist', hasPrincipal)` | OK |
| `show_courses` | `#courses` | **`setNavVisible` only** | **BROKEN** |
| `show_gallery` | `#gallery` | **`setNavVisible` only** | **BROKEN** |
| `show_faq` | `#faq` | nav + `renderFaq` skipped, so it stayed empty | OK, indirectly |
| `show_contact` | `#contact` | `showSection` | OK |
| `show_student_area` | `#parent` | `showSection`, OR'd with `show_student_login` | OK, two owners |

Switching off 课程 or 作品墙 removed the menu entry and left the section on the
page. **The studio saw it disappear from the navigation and concluded it was
off; a visitor scrolling past still saw it.** Nothing failed, so nothing said
so — the same shape of defect as the industry/palette weld in v8.5.2.

## Why it needed fixing in two places

`#courses`, `#gallery` and `#faq` are `data-awaits-data` sections: hidden until
their render function calls `resolveSection(id, true)` once content arrives.
The switches ride on `/brand`; the content rides on `/programs` and
`/public-gallery`. **Those are independent fetches and either can answer
first.** Hiding the section when `/brand` lands is not enough — a slow `/brand`
means the content already revealed it, and a fast one means the render reveals
it afterwards.

So the switch is recorded in `state.sectionsOff` when `/brand` answers, applied
immediately to whatever is already on the page, AND consulted by each render
function. Neither order can win.

## Verified against the adverse order, not by reading

A probe driving the real portal runtime with a stubbed network — `/programs`
answering at 0 ms, `/brand` at 250 ms, which is the order that produced the
bug:

```
contentArrivedFirst: 2          <- two course cards rendered before /brand
switchesOff: {courses:true, gallery:true, faq:false}
principal ON  -> artist   true
courses  OFF -> courses   false  <- hidden despite content having arrived
gallery  OFF -> gallery   false
faq      ON  -> faq       true
contact  ON  -> contact   true
student  ON  -> parent    true
```

Three false starts getting there, each worth remembering: the external assets
404 under `file://` and took the page script down before the code under test
ran (fixed by inlining the real `ui-common.js` / `public-register.js` /
`public-analytics.js` rather than stubbing them); the stub was anchored on a
string that does not exist in this template and was **silently never inserted**;
and the payload used `principal` where the portal reads `principalProfile`,
which looked exactly like a seventh broken switch.

## `show_about` — a whole section with no way to reach it

`_normalize_website_profile` validates and stores `show_about`, and the portal
has a complete `renderAbout()` with a bilingual title, body and a six-image
slideshow. **Studio Admin has no control for any of it** — zero occurrences of
any about field. It defaults to `false`, so no tenant has ever seen it.

Not fixed here, because building an image-uploading editor is a feature and
this release is a correspondence fix. Recorded as a task, and pinned in
`test_section_switches.py` as a `known_orphans` entry so a SECOND one cannot
appear without failing.

## Tests

`backend/tests/test_section_switches.py`, 23 assertions. The load-bearing one:

```python
SWITCHES = {
    "show_courses": ("courses", "settingShowCourses", "state.sectionsOff.courses"),
    ...
}
```

Each switch names the expression that carries it to its section, so losing the
enforcement fails here rather than being re-derived by a regex that might guess
right. Plus: every switch has an admin control, every switch is validated
server-side, every data-fed section's revealing `resolveSection` consults its
switch, `state.sectionsOff` is declared before any render can read it, and no
NEW orphan appears on the server.

Two of my own assertions were wrong first and were corrected rather than
relaxed: the mechanism check guessed at `showSection('artist'` when principal
routes through `hasPrincipal`, and the reveal check matched
`resolveSection('gallery', false)` — a teardown for a failed image, not a
reveal.

## Numbers

* 1387 passed, 7 skipped.
* Palette checker: 18 theme-modes × 60 pairs = 1080 assertions, 0 failures.

## Carried forward

The empty-hero fallback (Design_Constraints section 5), the CMS rendering the
accent as a filled sidebar (section 1.1 at scale), Cormorant Garamond blocked
by the site's own CSP, and now the orphaned About section.

---

