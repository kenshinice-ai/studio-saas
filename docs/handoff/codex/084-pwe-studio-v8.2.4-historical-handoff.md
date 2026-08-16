# PWE Studio v8.2.4 — Historical Handoff

## Theme completeness, console information architecture, SEO — packaged (2026-08-01)

**Baseline:** v8.2.3. **Branch:** `claude/ui-ux-pro-max-audit-073a82`.

### The Tailwind debt was measured, not guessed

The CMS carries 1,422 Tailwind colour utility uses across 154 distinct
utilities, remapped to tenant tokens by role (danger/success/structure) in the
shell stylesheet. Scripted coverage analysis against the `[class*=]` mapping
table found **148 of 154 already re-pointed** — the architecture works. The
entire gap was `ring-*`, which Tailwind implements through its own
`--tw-ring-color` and which the role map never claimed: all 65 focus rings drew
Tailwind indigo, so a clay or forest studio got an indigo halo on every focused
input, and on a dark theme an indigo ring against a dark panel can fall under
the 3:1 WCAG 1.4.11 requires of a focus indicator. The tenant palette had
shipped `focus_ring_color` all along.

`ring-*` is now mapped by family — not by the six utilities in use today — so a
ring added later is themed on arrival. Coverage is now 1,421/1,422; the
remaining `placeholder-gray-400` is already handled by the shell's generic
`::placeholder` rule. **No tenant rebuild was needed**: the problem lived in one
shared stylesheet, not in tenant data, so deleting and recreating the six
workspaces would have carried risk for zero benefit.

### Platform console reordered as a work surface

Overview presented eight counters in one undifferentiated grid, giving "Past
Due" (chase an invoice) the same weight as "Total Tenants" (a standing fact),
and put the list naming the at-risk tenants *below* all eight. It is now
ordered by what the operator does with each block: **Needs attention** (Past
Due / Trials Ending / Onboarding, with Commercial Attention directly beneath) →
**Business health** (five standing totals) → **30-Day Acquisition Funnel**,
last and collapsed by default. All ids unchanged; the JS addresses them by id,
so no data path moved.

### Studio Admin controls simplified without losing customisation

- Six "Show / Hide" dropdowns — two taps and a popup each to set a boolean —
  are one switch list. State is carried by knob position as well as colour, so
  it survives a colour-blind reading. Same six settings, same ids.
- The eight visibility controls moved from `<select>.value` to
  `.checked` via `toggleOn()` / `setToggle()` helpers; 24 call sites converted,
  zero `.value` references left. `change` listeners were untouched (checkboxes
  fire it too).
- Five fine colour inputs are collapsed behind a disclosure. Every field stays
  present and editable — the theme picker above already produces a complete,
  contrast-checked palette, so this is refinement, not setup.

### Product home

Release-evidence link removed from the public footer and placed inside
`/platform-admin` (it is an internal delivery record, and the public link had
gone stale — still pointing at the v8.1.0 notes two releases later).
Reachability for both audiences is now asserted by tests rather than assumed.

SEO: the title led with the brand and a tagline, so the page ranked for nothing
but its own name. It now leads with what a studio owner searches for, under 60
characters, plus canonical, keywords and Open Graph/Twitter cards so a shared
link renders as a titled card instead of a bare URL.

### Verification

```text
pytest: 309 passed (2 new reachability tests)
Legacy CMS smoke: 73/73 · Tenant isolation: 228/228
Tailwind coverage: 148/154 -> 153/154 distinct (1,421/1,422 uses)
Browser (local, Chrome):
  platform console order: Needs attention -> Commercial Attention ->
    Business health -> funnel (collapsed); funnel still loads on expand
  Studio Admin switches: all 8 load from server state as checkboxes
  round-trip: Gallery off -> Save Draft -> websiteProfile.showGallery=false
    in DB, other seven unchanged -> reload shows off -> restored to on
  switch geometry 46x26, on=brand accent knob right, off=grey knob left
  both consoles verified in Chinese and English; no console errors
```

Two defects were found by browser verification and fixed before release: the
new group headings were not in the i18n dictionary (English text on a Chinese
page), and the switch resolved `--accent`/`--panel`/`--focus-ring`, none of
which Studio Admin defines — it uses `--brand-accent` — so the track rendered
transparent and 42px tall under the global `input` rule.

