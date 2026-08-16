# PWE Studio v8.2.9 — status colours solved per theme (2026-08-02)

**Shipped.** Option D below was executed: all 45 semantic values regenerated,
the theme picker's grouping corrected, 88 new assertions added. The analysis
that led here is kept intact underneath, because the measurements are the
reason the constants are what they are.

## What changed

`docs/design/palette_gen.py` is the source of truth; `presets.py` is emitted
from it. The semantic block used to solve lightness against the page and
nothing else. It now solves saturation *and* lightness against every surface
the role lands on:

```text
constraint                                        floor
role as text on the page                          4.6
solid fill on --bg2 and on --panel                3.0
--on-accent label on that solid fill              4.5
color-mix(role 61.8%, text) on --bg2 / --panel    4.5
distance from the accent          hue >= 30 deg OR contrast >= 1.55

result: 45/45 solved, 0 unsolvable, 525 generator assertions pass
```

Saturation is pulled 60% from the role's anchor toward that theme's accent,
floored at 32%. **The floor is the one judgement call in the file:** without it
`studio-ink` (accent saturation 4%) drags danger to `#92625C` at S=23, which
stops reading as danger. At 32% it lands on `#9B5950` — muted, still red.

Two defects the fixed-saturation design had been hiding:

* `arcade-lime/dark` shipped **all three** fills under the 3:1 non-text floor
  (worst 2.89 on `--bg2`). Earlier passes measured this and set it aside
  because semantic *text* is compensated; a solid *badge* is not.
* Six values sat inside 30 degrees of their own accent with no lightness
  separation — `vintage-press` warning at 5 deg, `cedar-grove` success at 4
  deg. A warning badge indistinguishable from a button is a worse failure than
  a clashing one. These are the six that move a lot (11-16 lightness points);
  hue never moves, so green still means success.

## Deploy step that is easy to miss

Editing `presets.py` changes **nothing a tenant sees** — every tenant carries
its own resolved copy of the tokens in `settings.visual_theme`. The refresh
path is:

```bash
.venv/bin/python backend/scripts/migrate_visual_themes.py --dry-run
```

then without `--dry-run`. It is idempotent, and it skips `theme_mode=custom`
tenants by design — a studio that hand-tuned its colours chose those values.
Any colour input in studio-admin flips the tenant to `custom`, so this is safe.

**Production state: the refresh has now been run (2026-08-02).** 5 preset
tenants migrated, verified 0 mismatches against the v8.2.9 presets:

```text
dance-dance          rehearsal-rose light   #2E774D #8A622F #722F29   matches
lets-paint-showcase  harbour-calm   dark    #348D67 #997B30 #C85C5D   matches
lets-paint-studio    atelier-clay   light   #2D784E #5A411D #753129   matches
lets-play-piano      recital-plum   light   #32765C #8B6133 #AE4944   matches
ruby-s-studio        rehearsal-rose light   #2E774D #8A622F #722F29   matches
isolation-alpha      vintage-press  light   theme_mode=custom, skipped
```

Confirmed on the live site, `harbour-calm/dark` being the interesting case
because it sits closest to the constraints the solver targeted:

```text
fills on --bg2      3.17 / 3.22 / 3.17   (needs 3.0)
--on-accent labels  4.61 / 4.68 / 4.60   (needs 4.5)
```

**`isolation-alpha` was left alone on purpose, and it is worth knowing why.**
Its `theme_mode` is `custom` and the values are genuinely hand-picked, not a
stale preset snapshot — `accent_color #224466` is a blue that appears in no
preset, alongside `secondary_accent_color #663322`. `--include-custom` would
discard both. Check what a custom theme actually holds before reaching for that
flag; a tenant whose custom values happen to equal an old preset is a stale
snapshot and safe to refresh, one that differs is somebody's decision.

Backup taken first: `studiosaas_studiosaas_20260802T080141Z.dump`.

The command, for the next regeneration:

```bash
ssh pwestudio "cd /opt/pwestudio/current && docker compose -p pwestudio --env-file /opt/pwestudio/shared/production.env -f deploy/aws/docker-compose.yml -f deploy/aws/docker-compose.lightsail.yml --profile local-db exec -T app python backend/scripts/migrate_visual_themes.py"
```

Note the compose invocation: `lightsail_ctl.sh` composes *both* files with
`-p pwestudio --profile local-db`, and running a bare
`docker compose -f docker-compose.lightsail.yml` instead fails with
"service db has neither an image nor a build context".

## Guards added

`backend/tests/test_visual_theme_coherence.py` now asserts the five surface
constraints and the accent-distance rule per (preset, mode, role) — 88 cases.
Verified by reverting `cedar-grove` success and `arcade-lime` success to their
v8.2.8 values: both guards fired (2.89 < 3.0, and 4 deg at 1.11 contrast).

## Theme picker

The second swatch row was labelled "status colours, same in every theme" —
true in v8.2.8, false now. It reads "status colours, tuned to this theme" and
the row survives because status answers a different question than surface and
brand colour, not because the chips look alike.

---

