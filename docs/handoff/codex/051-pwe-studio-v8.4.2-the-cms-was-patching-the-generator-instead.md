# PWE Studio v8.4.2 — the CMS was patching the generator instead of configuring it (deployed 2026-08-05)

The CMS colour problem has been open since the theme system existed. This is
why, and it is a category error rather than a list of missed values.

## What the CMS actually is

`legacy-root/src/cms-app.jsx` (5723 lines) -> esbuild -> `assets/cms-app.js`.
The shell loads the **Tailwind Play CDN**, which generates utilities in the
browser from `tailwind.config`. The app renders **1422 colour-utility
occurrences, 154 distinct, across 12 colour families** — and 703 of those 1422
are `gray`.

The shell carried **68 rules** of `[class*="bg-indigo-"]` overrides chasing what
the generator had already emitted. That layer reached **84 of the 154**; the
other **70 painted fixed Tailwind values no theme could touch**.

Patching could not converge. Every new component brings new utilities, so the
patch layer grows forever and is always behind.

## The distinction it never made

>   THE NEUTRAL RAMP INVERTS WITH THE MODE. THE ROLE RAMPS DO NOT.

`bg-gray-50` is a surface and `text-gray-900` is ink, and those swap in dark.
But `bg-red-600` is a red button in both modes, and `bg-indigo-700` — every
filled action in this app, 保存 / 刷新 / 签到 / 退出登录 — is a deep brand slab
carrying light text in both.

A rule that flips everything breaks the buttons. A rule that flips nothing
breaks the page. The override layer had no way to express "flip these, hold
those", so it could only ever be half right.

The config expresses it directly: the neutral ramp is built from `--bg` and
`--ink`, which already swap, so it inverts for free. Role ramps end at
hover/pressed, which the generator already moves in the mode-correct direction.

Measured with a dark theme applied:

```
bg-gray-50      lum 0.011   |  text-gray-900  lum 0.808   inverted
bg-indigo-700   lum 0.378   |  white on it    5.49:1      held
```

## Three attempts to install the config, two of which failed

Worth recording, because the documented Play CDN pattern does not hold for this
vendored build:

1. `<script src>` then `tailwind.config = ...` — the build installs
   `window.tailwind` AFTER the tag returns, so the assignment landed on a
   placeholder that was then replaced. `config` read back `{}` and every
   utility stayed stock Tailwind.
2. Defining `window.tailwind` through a getter/setter first — the build installs
   its own property descriptor, discarding ours.
3. Assigning once the object really exists. Works, and was proved at the console
   before being written into the page: `bg-indigo-700` went from stock `#4338CA`
   to `var(--accent)` and the JIT regenerated every affected rule.

A fourth failure was mine: the scripted edit that moved the block spliced out
its middle, and the page threw `SyntaxError: Unexpected token '}'`. The console
said so immediately; I had been reading computed styles for two rounds without
looking at it.

## The chain, because missing a link here is the whole story

* `cms-app.js` is a **build artefact**. The v8.4.1 chart-colour fix went into
  the artefact, not `cms-app.jsx`, and the next build silently reverted it.
  Fixed at source and rebuilt.
* The shell's `themeVars` map predates v8.4.0 and stopped at the loud tokens, so
  every quiet form the config references would have resolved to nothing. It now
  carries 40.
* The portal and register maps were then behind the CMS, which
  `test_the_three_surfaces_agree_field_for_field` caught on the spot — the point
  of asserting equality rather than completeness. All three carry 40.
* Six `bg-red-500/80`-style alpha modifiers cannot apply to a `var()` colour;
  they compile to an invalid value and the fill silently disappears. Rewritten
  at source.
* `bg-blue-50` marked "长期未到访 — 有余额但超过 90 天未上课" with the info role,
  so it rendered green on a green theme and green on a rose one. It is a
  warning: money sitting unused and a student drifting.

## What `white` cost, which was nothing

183 `-white` utilities, and Tailwind cannot tell `bg-white` (a card) from
`text-white` (a label on a filled button) — `colors.white` is one value. It
works only if `--panel` clears 4.5:1 on every accent, and it does: worst 5.10 at
arcade-lime dark. No source change needed.

---

