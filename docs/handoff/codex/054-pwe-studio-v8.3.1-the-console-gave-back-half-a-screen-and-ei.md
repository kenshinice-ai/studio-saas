# PWE Studio v8.3.1 — the console gave back half a screen, and eight dark themes were upside down (deployed 2026-08-04)

> Shipped as 8.3.0, corrected twice, released as **8.3.1**. The second
> correction had to carry a new version number rather than redeploy 8.3.0,
> and that is worth understanding before the next in-place fix:
>
> Versioned assets are served `public, max-age=31536000, immutable` when
> `?v=` matches `APP_VERSION`. Redeploying under the same version leaves the
> URL `/assets/admin-i18n.js?v=8.3.0` unchanged, so **every browser that
> loaded the console during the first 8.3.0 keeps the first 8.3.0 dictionary
> for a year.** Measured on production: the versioned URL still answered
> without the new entries while an unversioned fetch of the same file had
> them. A corrected asset needs a new version, not a redeploy.

Five things, all on one page and its data, done together because they are one
page: the space the Website & Brand console spent on itself, the dark palettes
it publishes, the industry copy it starts a studio with, the phone, and the
half of the interface that stayed English when you switched to Chinese.

Each was measured before it was changed. The numbers below are from the running
page, not from reading the CSS.

## P0 — the console spent 574px of a 900px screen before the first control

Measured at 1440x900, top of `.brand-step`:

| layer | desktop | phone 390x844 |
|---|---|---|
| header-top (brand + 7 buttons) | 102 | 304 |
| nav-bar | 57 | 59 |
| section header `官网与品牌` | 55 | 97 |
| workbench hero `打造工作室的公开品牌体验` | 137 | 205 |
| studio-tabs | 57 | 57 |
| panel heading `品牌基础` | 61 | 81 |
| **to the first control** | **574** | **906** |

The same label appeared four times on the way down: nav item `官网与品牌` →
section header `官网与品牌` → hero `打造工作室的公开品牌体验` → tab `品牌` →
panel heading `品牌基础`. Draft state was published twice, in two wordings:
`workbenchStatus` said `已保存` while `saveBarStatus` said `没有未保存的更改`.
`Open CMS` existed three times at once — a header button, a nav link, and a
Public Pages card with a URL and a health check.

**What changed.** The hero and the settings section header are deleted. The
header is one row carrying brand, nav and account; identity, tenant slug,
password change and sign-out moved into a `<details>` account menu, and the two
header buttons that duplicated the nav are gone. One draft readout, in the save
bar. `--header-h` is measured by `syncHeaderOffset()` instead of the
hand-written `top: 136px`, because a wrapping row has no constant height.

**After: the first control is at 249px, and 85% of the viewport is live when
scrolled (was 75%).** φ is untouched — a layer was removed, no ratio retuned.

## P1 — all eight dark themes stacked their surfaces upside down

`palette_gen.py` built the dark surfaces by mirroring the light lightnesses
around mid-grey. Light puts the alternating band 0.047 *below* the page, so
dark put it 0.124 *above*. The distance survived; the meaning inverted. In a
dark UI lighter reads as nearer, so the band came out as the brightest surface
on the page — brighter than the cards resting on it, which then read as holes.

```
theme            mode    panel/bg  alt/bg  panel/alt  order (dim → bright)
atelier-clay     light       1.15    1.12       1.28  alt < bg < panel
atelier-clay     dark        1.17    1.43       1.23  bg < panel < alt   ← 8/8
```

The band's step off the page measured **1.39–1.61 in dark against 1.10–1.13 in
light.** On the tenant portal `--bg2` paints two full sections (790px, 733px)
and the footer.

**Why 26 contrast assertions per theme-mode were all green.** They check
legibility. Muted text on the band measured 4.60–4.65 in both modes — the
palettes were accessible and wrong at the same time. **Contrast cannot express
which surface should look nearer.**

**What changed.** The dark branch keeps its page dark and lifts the band
slightly, panel above both: `bg .068 → bg2 .102 → panel .150`, and `worst` (the
lightest surface a text token can land on) is the panel now, not the band. All
eight re-solved; `presets.py` verified token-for-token against the generator,
zero drift. Two new rules in `layer_faults()`: the panel is the nearest surface
in both modes, and the band's step is within 1.6× of the light-mode step.

**`test_the_rule_rejects_the_pre_v830_surfaces` rebuilds each dark theme with
the three lightnesses that shipped and asserts all eight are rejected.** Without
it the rule could later be relaxed into something that passes on both.

Also deleted: the `@media (prefers-color-scheme: dark)` block in
`brand-system.css`. It never took effect — `/brand` writes 34 tokens inline on
`:root`, and inline beats a stylesheet, so it was overridden on exactly the
pages it was for; on the admin surfaces all 62 fields measured `#0E1729` on
`#FFFFFF` with the OS in dark. Dead, but a trap: any page later styling itself
from `--brand-paper` without inlining would have had paper and ink flipped by
the visitor's OS while its accents stayed solved for light. **A studio's theme
decides light or dark. The visitor's OS does not get a vote.**

## P2 — the card promised one headline, the site published another

`slogan` is what the industry card renders. `hero.title` is what the published
site renders. Two hand-written strings per industry, and **in Chinese five of
the eight had drifted**:

| | card (`slogan_zh`) | published (`hero.title.zh`) |
|---|---|---|
| 艺术 | 大胆创作，让成长看得见。 | 让创意被看见，让成长有作品。 |
| 音乐 | …让每次练习都**算数**。 | …让每次练习都**有回应**。 |
| 数学 | 理解方法，建立长久的信心。 | 理解方法，建立信心，稳步进阶。 |
| 舞蹈 | 自信地舞动，在训练中成长。 | 在节奏中表达，在训练中成长。 |
| 游戏与编程 | 在**玩**中思考、创造与升级。 | 在**游戏**中思考、创造与协作。 |

In English `slogan == hero.title` for all eight, so the fork was invisible to
anyone reading the source in English.

`hero.title` is **derived** from the slogan now, and a literal `title` back in
the preset dicts fails a test — correcting five strings would have left the
fork open.

**Register page copy.** `tenant-template/register.html` falls back to
`告诉我们学员的情况` / "Tell us about the student" under an eyebrow that already
says Quick Registration. The Chinese presets followed that voice; the English
ones were noun labels ("Creative Preferences", "Music Goals") that read as a
form section and never mention registering. All eight English headings rewritten
to match. Both languages' leads rewritten so they name the questions and the
outcome instead of restarting the heading: `告诉我们…` / "Tell us about…" ×8
became `三个关于创作形式、经验与目标的问题，之后画室会推荐合适的课程与时间。`
and its seven siblings. `Game` → `Games & Coding` (the English label had dropped
编程, half the offer); `Math` → `Maths`, matching the product's own spelling.

## P3 — the phone pinned nothing

**94 controls under 44×44** (nav-link 38, studio-tab 36, header buttons 43), the
first field 906px down, and `.header` **and** `.save-bar` both
`position: static` in the mobile block — the tab you were editing under and the
Publish button both scrolled away.

Two rules were doing most of the damage, and both sat in the page's own
override block where they beat the base rules: `button { min-height: 38px }`
and `input, select, textarea { min-height: 42px }`. Raising the base alone would
have changed nothing.

**After, at 390×844: 0 undersized controls across all eight tabs, no horizontal
overflow, first control at 320px.** The tab strip and the publish bar are
sticky, the bar padded with `env(safe-area-inset-bottom)`. `.settings-panel`
had to lose `overflow: hidden` first — it makes an ancestor a scroll container,
and a sticky child of one never sticks to the viewport.

## P4 — the console spoke Chinese and hinted in English

`applyAttributes()` in `admin-i18n.js` has always localised `placeholder`,
`title` and `aria-label`. **26 of them had no dictionary entry**, so every field
on a Chinese console still hinted in English. Found by walking the rendered
document; the dictionary cannot report what it was never told about.

Down to 3, all deliberate: `owner@studio.test`, `studio@example.com`,
`https://...` — worked examples a Chinese reader types verbatim. Entries for
copy this release deleted (`Brand Builder`, `Shape the public studio
experience`, `Saved`) were removed rather than left behind.

Visible text was already clean: the only untranslated strings are the language
switch, the tenant slug, the eight English industry sub-labels (bilingual by
design) and the producer credit.

## Two things the first cut of this release got wrong

Both were caught by measuring the deployed page rather than by reading the code,
and both are recorded because the reasoning that produced them was wrong, not
just the output.

**The switch had a hit area that did not exist.** The first attempt kept the
26px track as the control and laid a transparent 44px `::before` over it. The
comment said that extended the target. It does not: Chrome does not hit-test a
form control's pseudo-element as the control. Probed on the deployed page, the
hit area came back **1px** tall against a 44px `::before`. The control is 46x44
now and the *track* is the pseudo-element, which measures 45px of hit area.
**The box that has to be 44px is the box the browser dispatches the click to.**

**`No unsaved changes` was translated and `Unsaved changes` was not.** The
lookup is exact, so the save bar reverted to English the moment anything was
edited. The attribute sweep could not have found it — the string is written by
script and never appears in the markup. Nine runtime messages were missing;
`test_every_runtime_message_has_a_chinese_translation` now scans the three calls
that put words in front of a person (`.textContent`, `showToast`,
`setLoginError`) and fails on all nine against the first cut.

A related caution for anyone measuring this page: `getBoundingClientRect()` and
`offsetParent` both report a live box for an element clipped inside a closed
`<details>`, so a sweep that trusts them counts controls nobody can see. The
first pass at proving the touch targets did exactly that.

## Verification

**1170 tests pass** (was 1147), 3 skipped. Three checkers pass. Three new files:

- `test_theme_layering.py` (39) — layering in both modes, presets↔generator
  parity, and the reconstruction check above.
- `test_preset_copy.py` (51) — the fork, the derivation, register-page voice,
  bilingual completeness.
- `test_studio_console.py` (20) — chrome budget, the 44px floor, the sticky
  phone rules, and every authored hint and runtime message having a Chinese
  entry.

**Every one of these was run against the v8.2.31 files before being trusted.**
`test_studio_console.py`: **16 of 20 fail** on the previous release. The layering
rule: **8 of 8** dark palettes rejected. The copy rules: 5/8 forks, 8/8 headings,
8/8 leads, 1/1 label. A test that passes on the code it was written to reject is
not a test — that is the v8.2.30 lesson, and it is applied here rather than
recited.

## Not done, and why

- `seed_random_demo_data.py` and `reset_professional_demo.py` keep their own
  bespoke `copy_pack` strings. They are demo fixtures representing a studio that
  has written its own copy, which is the path those fields exist to support.
  Left alone deliberately, not overlooked.
- Whether the subscription settlement should ever run unattended is still the
  owner's call, unchanged from v8.2.30.
- `/sitemap.xml` still needs submitting to Google Search Console.
- The showcase password pasted into a chat transcript still needs rotating.

---

