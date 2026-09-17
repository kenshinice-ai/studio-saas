# The roadshow deck's generator — and why it is not the deck's source of truth

`PWE_Studio_Roadshow_Bilingual.pptx` is the deck. **It is ahead of everything
else in this directory that claims to build it.**

## What is here

| File | What it is |
|---|---|
| `PWE_Studio_Roadshow_Bilingual.pptx` | The deck that gets presented. 11 slides. Maintained by hand since 2026-08-18 (unzip → edit `ppt/slides/slideN.xml` → zip). |
| `roadshow-build.mjs` | The generator that produced the *first* version of that deck on 2026-08-09. 10 slides. |
| `roadshow-assets/` | The screenshots, marks and `design-tokens.css` the generator reads. Screenshots are from the v9.9.5 manual set, seeded showcase tenant, synthetic people (`example.com`, `04000001xx`). |
| `PWE_Studio_Roadshow_Bilingual.html` | The generator's HTML rendering of those 10 slides. |

## How the two came apart

The generator was written in a Codex session and then sat in a `git stash` for
five weeks. The 2026-08-18 refresh could not find it, recorded "the deck has no
generator, it is hand-maintained XML"
(`docs/handoff/claude/2026-08-18-roadshow-deck-refresh.md`), and edited the
`.pptx` directly. The generator was recovered from that stash on 2026-09-17.

What the deck has that the generator does not:

- slide 11, the bilingual finance / Xero slide;
- 13 screenshots reshot from the v10.9 showcase tenant;
- current version badges.

## What was corrected on the way in

The stashed generator still sold the v9.9.6 plan table. A price in a public
repository is a claim, so these were brought to the live values before this
file was committed — the authority is
`backend/db/migrations/0046_plan_student_limits_match_published.sql` and the
tracked deck, which agree:

| | as stashed | as committed |
|---|---|---|
| Growth price | $199 | **$189** |
| Students | 100 / 500 / 1,000 | **50 / 250 / 500** |
| Plan row wording | `N team users` | `N seats · N works`, matching the deck |

Nothing else in the generator was changed except where it writes.

## Running it

It imports `@oai/artifact-tool`, which is available inside a Codex session and
is **not** a dependency of this repository — `npm ci` will not install it.

If you do run it, the `.pptx` lands in `docs/sales/build/` (git-ignored), not on
top of the tracked deck: a rebuild would silently replace 11 current slides with
10 older ones. Promoting a rebuilt deck is a deliberate copy, after slide 11 and
the reshot screenshots have been ported into the generator.

Until someone does that port, **edit the `.pptx`**, and treat this generator as
the record of how the layout was derived (golden-ratio art column, token
palette, type scale) rather than as a build step.
