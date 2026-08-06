/* A JavaScript port of palette_gen.build().
 *
 * It exists so the design lab's "tune" mode can re-solve a palette while a
 * slider moves, which is the whole point of the lab: the sliders move the
 * GENERATOR'S INPUTS — hue, saturation, the surface lightnesses — and never
 * the output hexes. A lab that let you nudge a hex would be a fifth
 * hand-built palette within a week, which is exactly what
 * docs/design/theme-proposal.html became.
 *
 * Two implementations of one algorithm is a drift risk, and the answer is the
 * same one used for presets.py: backend/tests/test_design_lab.py runs this
 * file under node and compares every token of every theme-mode, plus a grid of
 * synthetic hue/saturation inputs, against the Python. A divergence in the
 * fortieth binary-search step is a test failure, not a surprise six months on.
 *
 * Keep this a direct transliteration. Cleverness here costs more than it saves.
 */
'use strict';

function srgb(c) {
  c = c / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function lum(hex) {
  const h = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.substr(i, 2), 16));
  return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
}

function ratio(a, b) {
  let l1 = lum(a), l2 = lum(b);
  if (l1 < l2) [l1, l2] = [l2, l1];
  return (l1 + 0.05) / (l2 + 0.05);
}

/* colorsys.hls_to_rgb, transliterated. Python's argument order is (h, l, s). */
function hlsToRgb(h, l, s) {
  if (s === 0) return [l, l, l];
  const m2 = l <= 0.5 ? l * (1 + s) : l + s - l * s;
  const m1 = 2 * l - m2;
  const v = (hue) => {
    hue = hue % 1.0;
    if (hue < 0) hue += 1.0;
    if (hue < 1 / 6) return m1 + (m2 - m1) * hue * 6;
    if (hue < 0.5) return m2;
    if (hue < 2 / 3) return m1 + (m2 - m1) * (2 / 3 - hue) * 6;
    return m1;
  };
  return [v(h + 1 / 3), v(h), v(h - 1 / 3)];
}

function rgbToHls(r, g, b) {
  const maxc = Math.max(r, g, b), minc = Math.min(r, g, b);
  const sumc = maxc + minc, rangec = maxc - minc;
  const l = sumc / 2.0;
  if (minc === maxc) return [0.0, l, 0.0];
  const s = l <= 0.5 ? rangec / sumc : rangec / (2.0 - maxc - minc);
  const rc = (maxc - r) / rangec, gc = (maxc - g) / rangec, bc = (maxc - b) / rangec;
  let h;
  if (r === maxc) h = bc - gc;
  else if (g === maxc) h = 2.0 + rc - bc;
  else h = 4.0 + gc - rc;
  /* Python's % returns a non-negative result for a positive modulus and
     JavaScript's does not, so the sign has to be corrected — but ONLY when it
     is actually negative. Correcting unconditionally with `(x % 1 + 1) % 1`
     costs a mantissa bit on values that were already fine: pure blue gives
     h/6 = 0.6666666666666666, and (0.6666666666666666 + 1) % 1 comes back
     0.6666666666666665. That 6e-14 became a whole step of red once the hue
     reached a channel sitting on a rounding boundary. */
  h = (h / 6.0) % 1.0;
  if (h < 0) h += 1.0;
  return [h, l, s];
}

/* Python's round() is banker's rounding: round-half-to-even. JavaScript's
   Math.round() is round-half-up, so 0.5 differs and a channel lands one step
   away. That single byte is what the parity test would otherwise report on a
   handful of themes. */
function pyRound(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

function hexof(h, s, l) {
  const [r, g, b] = hlsToRgb(h / 360.0, l, s);
  return '#' + [r, g, b].map((c) => pyRound(c * 255).toString(16).toUpperCase().padStart(2, '0')).join('');
}

function hslOf(hex) {
  const hx = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hx.substr(i, 2), 16) / 255);
  const [h, l, s] = rgbToHls(r, g, b);
  return [h * 360, s, l];
}

function mix(a, b, p) {
  const ha = a.replace('#', ''), hb = b.replace('#', '');
  return '#' + [0, 2, 4].map((i) =>
    pyRound(parseInt(ha.substr(i, 2), 16) * p + parseInt(hb.substr(i, 2), 16) * (1 - p))
      .toString(16).toUpperCase().padStart(2, '0')).join('');
}

/* Perceived lightness. HSL's L is not it, and the difference is the point:
   the same numeric step buys much less separation near black than near white,
   which is why the dark cards sat 5.33 perceived units above the band where
   light mode puts them 8.13. */
function oklabL(hex) {
  const hx = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => srgb(parseInt(hx.substr(i, 2), 16)));
  const l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b;
  const m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b;
  const s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b;
  const [l_, m_, s_] = [l, m, s].map((v) => (v > 0 ? Math.cbrt(v) : 0));
  return 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_;
}

function solvePerceived(h, s, above, lift) {
  let lo = 0.0, hi = 1.0, best = null;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    const cand = hexof(h, s, mid);
    if (oklabL(cand) - oklabL(above) >= lift) { best = cand; hi = mid; } else { lo = mid; }
  }
  return best || hexof(h, s, 1.0);
}

function hueGap(a, b) {
  const d = Math.abs(a - b) % 360;
  return Math.min(d, 360 - d);
}

function chroma(hex) {
  const h = hex.replace('#', '');
  const ch = [0, 2, 4].map((i) => parseInt(h.substr(i, 2), 16));
  return Math.max(...ch) - Math.min(...ch);
}

function atChroma(hue, lightness, target) {
  let lo = 0.0, hi = 1.0;
  for (let i = 0; i < 44; i++) {
    const mid = (lo + hi) / 2;
    if (chroma(hexof(hue, mid, lightness)) < target) lo = mid; else hi = mid;
  }
  return hexof(hue, hi, lightness);
}

function chipAt(hue, s, panel, baseL, step) {
  const pl = hslOf(panel)[2];
  let lo = 0.0, hi = 1.0;
  for (let i = 0; i < 44; i++) {
    const mid = (lo + hi) / 2;
    if (ratio(hexof(hue, s, pl + mid * (baseL - pl)), panel) < step) lo = mid; else hi = mid;
  }
  return hexof(hue, s, pl + hi * (baseL - pl));
}

function liftChroma(hue, colour, panel, baseL, step, floor) {
  if (chroma(colour) >= floor) return colour;
  let best = colour;
  const s0 = hslOf(colour)[1];
  for (let i = Math.trunc(s0 * 100) + 1; i <= 100; i++) {
    best = chipAt(hue, i / 100, panel, baseL, step);
    if (chroma(best) >= floor) break;
  }
  return best;
}

function solveAtChroma(hue, s0, against, target, darker, chromaTarget) {
  let best = solve(hue, s0, against, target, darker);
  if (chroma(best) >= chromaTarget) return best;
  for (let i = Math.trunc(s0 * 100) + 1; i <= 100; i++) {
    best = solve(hue, i / 100, against, target, darker);
    if (chroma(best) >= chromaTarget) break;
  }
  return best;
}

function mixToRatio(a, b, target) {
  let lo = 0.0, hi = 1.0, best = b;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    const cand = mix(a, b, mid);
    if (ratio(cand, b) >= target) { best = cand; hi = mid; } else { lo = mid; }
  }
  return best;
}

function solve(h, s, against, target, darker = true) {
  let lo = 0.0, hi = 1.0, best = null;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    const cand = hexof(h, s, mid);
    if (ratio(cand, against) >= target) {
      best = cand;
      if (darker) lo = mid; else hi = mid;
    } else {
      if (darker) hi = mid; else lo = mid;
    }
  }
  return best || hexof(h, s, darker ? 0.0 : 1.0);
}

const MODES_DEFAULT = ['light', 'dark'];
const SEMANTIC = { success: [152, 0.44], warning: [36, 0.58], danger: [6, 0.52], info: [212, 0.46] };
const SEM_S_PULL = 0.60, SEM_S_FLOOR = 0.32, SEM_S_CEIL = 0.72;
const SEM_HUE_GAP = 30.0, SEM_LUM_GAP = 1.55, SEM_TEXT_MIX = 0.618;
const TARGETS = { body: 8.0, muted: 4.6, accent: 4.6, semantic: 4.6, line_strong: 3.05, on_accent: 4.6 };
const SOFT_STEP = 1.22, SOFT_LINE = 1.45, HOVER_STEP = 1.06;
const PANEL_LIFT = 0.0556;
const CHROMA_FLOOR = 22, CHROMA_FLOOR_NEAR = 32, CHROMA_NEAR_HUE = 20.0;
const PANEL_RISE = 0.034, PANEL_CHROMA = 0.60, LINE_CHROMA = 1.90, LINE_STRONG_CHROMA = 3.20;
const ACCENT_SOFT_STEP = 1.52, SOFT_SEPARATION = 1.14;

const inkHue = (t) => (t.ink_hue !== undefined ? t.ink_hue : t.hue);
const inkSat = (t) => (t.ink_sat !== undefined ? t.ink_sat : t.sat);
const accentHue = (t) => (t.accent_hue !== undefined ? t.accent_hue : t.hue);
const accentSat = (t) => (t.accent_sat !== undefined ? t.accent_sat : t.sat);
const secHue = (t) => (t.sec_hue !== undefined ? ((t.sec_hue % 360) + 360) % 360
  : ((accentHue(t) + t.sec_off) % 360 + 360) % 360);
const anchored = (t, role) => (t.anchors || {})[role];

function solveSemantic(hue, targetS, accent, bg, bg2, panel, ink, onAccent, dark,
                       accentIsFixed = false) {
  const accentH = hslOf(accent)[0];
  const seedL = hslOf(solve(hue, targetS, bg, TARGETS.semantic, !dark))[2];
  const nearAccent = hueGap(hue, accentH) < SEM_HUE_GAP;
  let best = null;
  for (const ds of [0, -0.03, 0.03, -0.06, 0.06, -0.10, 0.10, -0.15, 0.15]) {
    const sTry = Math.max(0.10, Math.min(0.90, targetS + ds));
    for (let step = 0; step <= 120; step++) {
      for (const sign of (step === 0 ? [0] : [-1, 1])) {
        const lTry = seedL + sign * step * 0.005;
        if (!(lTry >= 0.05 && lTry <= 0.95)) continue;
        const cand = hexof(hue, sTry, lTry);
        if (ratio(cand, bg) < TARGETS.semantic) continue;
        if (ratio(cand, bg2) < 3.0 || ratio(cand, panel) < 3.0) continue;
        if (ratio(onAccent, cand) < 4.5) continue;
        const mixed = mix(cand, ink, SEM_TEXT_MIX);
        if (ratio(mixed, bg2) < 4.5 || ratio(mixed, panel) < 4.5) continue;
        /* Kept only for the internal console, whose accent is pinned. A
           tenant's accent must never reach this, or the semantics stop being
           constants — see the note in build(). */
        if (nearAccent && accentIsFixed && ratio(cand, accent) < SEM_LUM_GAP) continue;
        const cost = Math.abs(sTry - targetS) * 2 + step * 0.005;
        if (best === null || cost < best[0]) best = [cost, cand];
      }
      if (best !== null && best[0] < 0.02) break;
    }
    if (best !== null && best[0] < 0.02) break;
  }
  if (best === null) throw new Error(`no semantic solution for hue ${hue}`);
  return best[1];
}

function build(theme, dark) {
  const h = theme.hue, s = theme.sat;
  let inkH = inkHue(theme), inkS = inkSat(theme);
  let accH = accentHue(theme), accS = accentSat(theme);
  const secH = secHue(theme), secS = theme.sec_sat;
  const neutral = s < 0.05;

  if (anchored(theme, 'ink')) {
    const [hh, ss] = hslOf(anchored(theme, 'ink'));
    inkH = hh; inkS = ss < 0.30 ? ss / 0.30 : ss;
  }
  if (anchored(theme, 'accent')) {
    const [hh, ss] = hslOf(anchored(theme, 'accent'));
    accH = hh; accS = ss;
  }

  let bg, bg2, panel, worst, ink, ink2, muted, line, lineStrong, accent, secondary, onDark, scheme;
  if (!dark) {
    bg = hexof(h, Math.min(s * 0.58, 0.40), 0.935);
    panel = hexof(h, Math.min(s * 0.42, 0.30), 0.992);
    bg2 = hexof(h, Math.min(s * 0.60, 0.42), 0.888);
    if (anchored(theme, 'background')) {
      bg = anchored(theme, 'background');
      const [aH, aS, aL] = hslOf(bg);
      bg2 = hexof(aH, aS, Math.max(0.0, aL - 0.047));
      panel = atChroma(aH, Math.min(1.0, aL + PANEL_RISE),
        Math.max(1, pyRound(chroma(bg) * PANEL_CHROMA)));
    }
    worst = bg2;
    ink = solve(inkH, Math.min(inkS * 0.30, 0.20), worst, 13.0, true);
    ink2 = solve(inkH, Math.min(inkS * 0.22, 0.16), worst, TARGETS.body, true);
    muted = solve(inkH, Math.min(inkS * 0.20, 0.15), worst, TARGETS.muted, true);
    line = atChroma(h, 0.845, Math.max(1, pyRound(chroma(bg) * LINE_CHROMA)));
    lineStrong = solveAtChroma(h, Math.min(s * 0.26, 0.20), worst, TARGETS.line_strong, true,
      Math.max(1, pyRound(chroma(bg) * LINE_STRONG_CHROMA)));
    accent = solve(accH, accS, worst,
      theme.accent_target !== undefined ? theme.accent_target : TARGETS.accent, true);
    secondary = solve(secH, secS, worst, TARGETS.accent, true);
    onDark = null;
    scheme = 'light';
  } else {
    bg = hexof(h, Math.min(s * 0.52, 0.38), 0.068);
    bg2 = hexof(h, Math.min(s * 0.46, 0.34), 0.102);
    panel = solvePerceived(h, Math.min(s * 0.44, 0.32), bg2, PANEL_LIFT);
    worst = panel;
    ink = solve(inkH, Math.min(inkS * 0.18, 0.10), worst, 11.0, false);
    ink2 = solve(inkH, Math.min(inkS * 0.16, 0.09), worst, TARGETS.body, false);
    muted = solve(inkH, Math.min(inkS * 0.16, 0.10), worst, TARGETS.muted, false);
    line = hexof(h, Math.min(s * 0.30, 0.22), 0.255);
    lineStrong = solve(h, Math.min(s * 0.26, 0.20), worst, TARGETS.line_strong, false);
    onDark = hexof(accH, Math.min(accS * 0.30, 0.22), 0.070);
    accent = solve(accH, Math.min(accS * 0.92, 0.84), onDark, 7.6, false);
    secondary = solve(secH, Math.min(secS * 0.92, 0.84), onDark, 7.2, false);
    scheme = 'dark';
  }

  if (neutral) {
    accent = !dark ? solve(accH, 0.04, worst, 11.0, true) : solve(accH, 0.06, onDark, 9.0, false);
    secondary = solve(215, 0.14, !dark ? worst : onDark, !dark ? 5.0 : 6.6, !dark);
  }

  if (!dark) {
    if (anchored(theme, 'ink')) ink = anchored(theme, 'ink');
    if (anchored(theme, 'accent')) accent = anchored(theme, 'accent');
    if (anchored(theme, 'secondary')) secondary = anchored(theme, 'secondary');
  }

  const bestOn = (colour) => {
    const lightOpt = '#FFFFFF', darkOpt = onDark || ink;
    return ratio(lightOpt, colour) >= ratio(darkOpt, colour) ? lightOpt : darkOpt;
  };
  const onAccent = bestOn(accent);
  const onSecondary = bestOn(secondary);

  const onAccentL = hslOf(onAccent)[2];
  const accentMuted = solve(accH, Math.min(accS * 0.18, 0.12), accent, 4.6, onAccentL < 0.5);

  /* The four semantics are CONSTANTS: they used to be nudged toward the accent
     and pulled 60% of the way to its saturation, which with a free accent knob
     means a studio's logo decides what "saved" looks like. See the Python. */
  const sem = {};
  for (const [role, [sh, ss]] of Object.entries(SEMANTIC)) {
    sem[role] = solveSemantic(sh, ss, accent, bg, bg2, panel, ink, onAccent, dark,
      Boolean(anchored(theme, 'accent')));
  }

  const shift = (colour, delta) => {
    const hx = colour.replace('#', '');
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(hx.substr(i, 2), 16) / 255);
    const [hh, ll, ss] = rgbToHls(r, g, b);
    return hexof(hh * 360, ss, Math.max(0.0, Math.min(1.0, ll + delta)));
  };

  let step = !dark ? -0.06 : 0.07;
  const accentL = hslOf(accent)[2];
  if (!(accentL + step * 2 >= 0.0 && accentL + step * 2 <= 1.0)) step = -step;
  const accentHover = shift(accent, step);
  const accentPressed = shift(accent, step * 2);

  const disabledSurface = shift(bg2, !dark ? -0.02 : 0.03);
  const disabledText = solve(inkH, Math.min(inkS * 0.14, 0.10), disabledSurface, 3.0, !dark);
  const focusRing = solve(accH, Math.min(accS * 1.0, 0.70), worst, 3.2, !dark);
  const scrim = !dark ? 'rgba(0,0,0,0.5)' : 'rgba(0,0,0,0.66)';
  const surfaceHover = mixToRatio(ink, panel, HOVER_STEP);

  const out = {
    color_scheme: scheme,
    background_color: bg, background_alt_color: bg2, panel_color: panel,
    surface_hover_color: surfaceHover,
    text_color: ink, text_soft_color: ink2, muted_text_color: muted,
    border_color: line, border_strong_color: lineStrong,
    accent_color: accent, accent_text_color: onAccent, accent_muted_text_color: accentMuted,
    accent_hover_color: accentHover, accent_pressed_color: accentPressed,
    secondary_accent_color: secondary, secondary_text_color: onSecondary,
    success_color: sem.success, warning_color: sem.warning,
    danger_color: sem.danger, info_color: sem.info,
    focus_ring_color: focusRing, disabled_surface_color: disabledSurface,
    disabled_text_color: disabledText, scrim_color: scrim,
  };

  for (const role of ['accent', 'secondary', ...Object.keys(SEMANTIC)]) {
    const base = role === 'accent' ? accent : role === 'secondary' ? secondary : sem[role];
    const [rh, rs] = hslOf(base);
    const floor = hueGap(rh, hslOf(bg)[0]) < CHROMA_NEAR_HUE ? CHROMA_FLOOR_NEAR : CHROMA_FLOOR;
    const step_ = role === 'accent' ? ACCENT_SOFT_STEP : SOFT_STEP;
    const soft = liftChroma(rh, mixToRatio(base, panel, step_),
      panel, hslOf(base)[2], step_, floor);
    out[`${role}_soft_color`] = soft;
    out[`${role}_on_soft_color`] = ratio(base, soft) >= 4.5
      ? base : solve(rh, Math.min(rs, 0.80), soft, 4.5, !dark);
    out[`${role}_border_color`] = mixToRatio(base, soft, SOFT_LINE);
  }

  for (const role of Object.keys(SEMANTIC)) {
    const pair = ratio(out.accent_soft_color, out[`${role}_soft_color`]);
    if (pair < SOFT_SEPARATION) {
      throw new Error(`the accent chip ${out.accent_soft_color} and the ${role} chip `
        + `${out[`${role}_soft_color`]} are ${pair.toFixed(2)}:1 apart, under ${SOFT_SEPARATION}`);
    }
  }
  return out;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { build, ratio, lum, hexof, hslOf, mix, MODES_DEFAULT };
}
