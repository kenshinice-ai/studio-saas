# PWE mark — Round 2 rationale

Client brief: keep the spark, fix the P. Round 1's mark was a stroked skeleton (stroke 10,
circle bowl) with the spark parked beside the baseline. Honest diagnosis before designing:

1. **No mass.** A monoline stroke at 128px reads as a wireframe, not a brand.
2. **b/p ambiguity.** The perfect-circle bowl hangs high on the stem; the silhouette drifts
   toward lowercase.
3. **The spark is a neighbor.** Center (38.5, 45) shares no edge, tangent, or axis with the
   letter. It decorates the whitespace instead of belonging to the P.
4. **Small-size collapse.** Stroke 10 on a 64 grid is 2.5px at favicon size; the spark is mush.
5. **W and E are absent** (explored in candidate C; verdict below).

All candidates: 64-grid, hand-authored geometry, Studio Navy `#0F172A` + Spark Amber `#F59E0B`
(dark: `#F8FAFC` + `#FBBF24`), 4-point quadratic-pinch spark retained as the signature
(same construction as round 1: four quadratic curves with control points at the spark's center).

---

## A — "Spark Counter" (`candidate-a.svg`)

**Concept.** Solid geometric P; the bowl's counter IS the spark, punched as negative space and
filled amber. The letter doesn't hold a spark next to it — the spark is the hole the letter is
built around. One shape, one idea.

**Construction.** Stem 11 wide (x 14–25, y 10–54). Bowl = semicircle r 14 on the cap line
(`M 14 10 H 36 A 14 14 0 0 1 36 38 H 25 V 54 H 14 Z`). Spark counter R 7.75 at (36, 24), west
tip pointing at the stem the way a real P counter meets its stem (2.25 gap — reads as aperture,
not accident). Fill-rule evenodd carries the punch; the amber path is a literal refill of the
same subpath, so monochrome = delete one path.

**Strengths.** Best 16px performance of the set — solid silhouette survives, and even when the
spark's points blur, an amber glow in the bowl remains. Monochrome works for free (the punched
counter still reads as a spark). Simplest possible file; zero masks. Clear capital-P silhouette
(bowl top-aligned to cap, stem descends well below bowl) — the b/p problem is gone.

**Risks.** Bowl depth is 64% of cap height (a semicircle's nature) — a touch heavy/bottom-deep
next to D. Sharp corners are more "tech" than "craft"; production could add a 1–1.5 unit outer
corner radius to warm it up.

## B — "Shoulder Spark" (`candidate-b.svg`)

**Concept.** The "apostrophe of craft": solid P with a true round counter; the spark perches on
the bowl's 45° shoulder — the exact point where a P's curve is purest — half-embedded through a
knocked-out halo (mask), so it reads as seated ON the letter, not floating near it, and works on
any background color.

**Construction.** Same solid skeleton, round counter r 5.75. Spark R 6.5 centered at
(46.2, 13.8) — 16.5 units from the bowl center along the 45° radial (bowl radius 14, so it
overlaps the body by ~3.5). Halo r 8.25 knocked out via mask; wall between halo and counter
kept ≥ 3.5 units so the ring never breaches. First render had the spark deeper (halo 8.75 at
distance 16.5): the bite read as an amputated ear. Refined outward + smaller halo; now it's a nick.

**Strengths.** Keeps a classical P (round counter) — most "letter-like" candidate. The
spark-at-shoulder gesture is lively and ownable; halo device guarantees separation on photos,
navy, amber, anywhere.

**Risks.** Round counter + shoulder nick can read as a face (counter = eye) once you see it.
The sparkle-on-letter device is currently everywhere in AI-tool branding — trend risk. At 16px
the halo gap (~0.5px) closes and the spark becomes a corner blip; monochrome small sizes are the
weakest of the four. Requires a mask (icon pipelines that flatten SVGs need care).

## C — "Hidden E" PWE monogram (`candidate-c.svg`)

**Concept.** The monogram question answered by building it: the P's stem doubles as the spine of
an E whose three arms live inside the bowl's counter; spark nested in the crotch below the bowl
(tangent to stem and bowl underside — anchored, not floating). W was also attempted in sketch
(zigzag counter) and discarded before rendering: a W-shaped counter destroyed the P silhouette
entirely.

**Construction.** Base skeleton of A; counter = rounded rect (25–41.5 × 16–32, rx 3); three
navy arms (h 3.5, slots 2.75) from the stem; spark R 6.5 at (33.5, 45.5).

**Verdict — kill it.** At 128px the E is legible but the mark reads as an electric plug / FAX
glyph before it reads as "PWE". At 64px the arms turn to texture; at 16px the counter is noise
(slots are 0.7px). It fails the brief's own 16px test, and the spark had to be exiled back to
the crotch because the counter was occupied — so the signature element got demoted to make room
for a gimmick. This is the candidate that proves the monogram shouldn't ship. Keeping it in the
sheet because a rejected exploration is part of the round's evidence.

## D — "Crafted P" (`candidate-d.svg`)

**Concept.** The type-design answer to "the P is the weak part": draw the P like a letter, not a
diagram, then give it the spark counter (the strongest idea from A) executed with optical care.

**Construction.** Cap height 44 (y 10–54). Bowl depth 26.6 = **60.5% of cap height** (classic
grotesk range, vs A's 64%). Bowl drawn with cubics, superelliptical shoulders; rightmost extreme
at y 23.1 — slightly **above** the bowl's vertical middle, giving the letter upward stress
instead of dead-center geometry. Stem right edge tapers 24.9 → 24.3 top-to-bottom (0.6 unit —
felt, not seen). Small ink-trap ease (`C 25.2 36.7 24.6 37.4 24.55 38.6`) where the bowl's
underside re-enters the stem, so the crotch doesn't clog at small sizes or heavy weights.
Spark counter R 7.5 at (34.5, 23.2), optically centered in the fuller bowl.

**Strengths.** Same one-idea clarity and 16px resilience as A, but the letter itself carries
craft: shallower bowl reads more confidently "capital P", the shoulder curves feel drawn rather
than compass-struck, and the details (taper, ink trap, stress) are the literal "craft" story the
brand sells to craft educators. Monochrome free, no masks.

**Risks.** The refinements are subtle — a client may ask what they paid for between A and D
(answer: put them side by side at 128px; A is a pictogram, D is a letter). Cubic-drawn curves
are harder to tweak than A's single arc. Bowl reaches x 50.2 — 0.2 outside A's box; irrelevant
optically, worth knowing for grid purists.

---

## Ranking (designer's own call)

1. **D — Crafted P. Ship this.** It is A's winning concept executed with the letterform quality
   the client explicitly asked for. It fixes every round-1 complaint: mass instead of wireframe,
   unambiguous capital P, spark structurally inside the letter, excellent at 16px, monochrome and
   masks-free. And its construction story (60.5% bowl, taper, ink trap, upward stress) is the
   brand narrative — craft you can point at.
2. **A — Spark Counter.** Identical concept, geometric execution. Keep as the fallback if the
   client prefers the crisper, more "product icon" personality; also the better base if the mark
   must ever be CNC'd/embroidered (single arc, no cubics). If D ships, A dies happily — it was
   the study for D.
3. **B — Shoulder Spark.** Competent and lively, but trend-adjacent (AI-sparkle badge), weakest
   monochrome-at-16px, needs a mask, and has a latent face-pareidolia problem. Keep only if the
   client insists the spark must stay visually amber-on-outside; otherwise kill.
4. **C — Hidden E. Kill, with the receipt.** Fails 16px, demotes the spark, reads as a plug.
   Its value is proving that "put W/E in the mark" costs more than it pays — the wordmark
   already says PWE; the mark's job is to say it with one letter and one spark.

**Follow-up if D is approved** (not done in this round, per brief): refine the wordmark's "P" in
`pwe-logo.svg` to echo D's bowl proportions, and regenerate `pwe-mark-dark.svg` usage docs.

## Files

- `candidate-{a,b,c,d}.svg` + `candidate-{a,b,c,d}-dark.svg` — 64-grid marks, light/dark.
- `compare.html` — self-contained review sheet: current mark vs candidates at 16/32/64/128 on
  light and dark, app-icon tiles (navy + paper), 16px favicon chip.
- `compare.png` — headless-Chrome render of the sheet (2x).

Live brand assets in `docs/design/brand/` are untouched; nothing committed.
