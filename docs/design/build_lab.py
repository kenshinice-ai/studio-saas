"""Generate docs/design/lab.html — the design lab.

Run:  python3 docs/design/build_lab.py

Why this is GENERATED and not written by hand: docs/design/theme-proposal.html
was written by hand. It is 1009 lines, it shows eight themes, and since v8.3.0
the dark half of what it shows has been wrong — it still displays the inverted
surfaces that release replaced. A design reference nobody regenerates becomes a
picture of a product that used to exist, and it is most convincing exactly when
it is most out of date. backend/tests/test_design_lab.py regenerates this file
and fails on any difference.

Three modes:

  Light / Dark  every component, every theme-mode, with the measured contrast
                of each pair printed under it.
  Tune          sliders. They move the GENERATOR'S INPUTS — hue, saturation,
                secondary offset, the three surface lightnesses — and re-solve
                through the same algorithm the Python uses (docs/design/
                solver.js, checked token-for-token against palette_gen.py under
                node). Never the output hexes: a lab that let you nudge a hex
                would be a fifth hand-built palette inside a week. The "copy
                THEMES entry" button prints the five numbers to paste back into
                palette_gen.py, which is what closes the loop.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
import importlib.util

_spec = importlib.util.spec_from_file_location("palette_gen", HERE / "palette_gen.py")
pg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pg)


# The component inventory, merged from the 199 / 182 / 109 class names the two
# consoles and the public portal declare. Grouped by the question each group
# answers, not by where it happens to live.
COMPONENTS = [
    ("Surfaces", [
        ("Page", '<div class="lab-surface" style="background:var(--bg)">--bg</div>'),
        ("Alternating band", '<div class="lab-surface" style="background:var(--bg2)">--bg2</div>'),
        ("Card", '<div class="lab-surface" style="background:var(--panel);border:1px solid var(--line)">--panel</div>'),
        ("Row hover", '<div class="lab-surface" style="background:var(--surface-hover);border:1px solid var(--line)">--surface-hover</div>'),
        ("Disabled surface", '<div class="lab-surface" style="background:var(--disabled-surface);color:var(--disabled-text)">--disabled-surface</div>'),
        ("Scrim", '<div class="lab-surface" style="background:var(--scrim);color:#fff">--scrim</div>'),
    ]),
    ("Ink", [
        ("Heading", '<p style="color:var(--ink);font-size:21px;margin:0">The quick brown fox 敏捷的棕色狐狸</p>'),
        ("Body", '<p style="color:var(--ink2);margin:0">Secondary copy at reading weight. 次级正文。</p>'),
        ("Muted", '<p style="color:var(--muted);font-size:13px;margin:0">Caption, helper text. 说明文字。</p>'),
        ("Disabled", '<p style="color:var(--disabled-text);margin:0">Unavailable 不可用</p>'),
    ]),
    ("Edges", [
        ("Divider", '<div style="border-top:1px solid var(--line);padding-top:8px;color:var(--muted);font-size:12px">--line</div>'),
        ("Control boundary", '<div style="border:1px solid var(--line-strong);border-radius:8px;padding:10px;font-size:12px">--line-strong</div>'),
        ("Focus ring", '<button class="lab-btn" style="outline:2px solid var(--focus-ring);outline-offset:2px">Focused</button>'),
    ]),
    ("Actions", [
        ("Primary", '<button class="lab-btn" style="background:var(--accent);color:var(--on-accent);border:0">Book a Trial</button>'),
        ("Primary hover", '<button class="lab-btn" style="background:var(--accent-hover);color:var(--on-accent);border:0">Hover</button>'),
        ("Primary pressed", '<button class="lab-btn" style="background:var(--accent-pressed);color:var(--on-accent);border:0">Pressed</button>'),
        ("Secondary", '<button class="lab-btn" style="background:var(--accent-2);color:var(--on-accent-2);border:0">Support</button>'),
        ("Outline", '<button class="lab-btn" style="background:transparent;color:var(--ink);border:1px solid var(--line-strong)">Outline</button>'),
        ("Quiet", '<button class="lab-btn" style="background:var(--accent-soft);color:var(--on-accent-soft);border:1px solid var(--accent-border)">Quiet</button>'),
        ("Danger", '<button class="lab-btn" style="background:var(--danger);color:var(--on-accent);border:0">Delete</button>'),
        ("Disabled", '<button class="lab-btn" disabled style="background:var(--disabled-surface);color:var(--disabled-text);border:1px solid var(--line)">Unavailable</button>'),
    ]),
    ("Form", [
        ("Text", '<input class="lab-input" value="Ada Lovelace">'),
        ("Placeholder", '<input class="lab-input" placeholder="owner@studio.test">'),
        ("Textarea", '<textarea class="lab-input" rows="2">Multi-line copy</textarea>'),
        ("Select", '<select class="lab-input"><option>Weekly</option><option>Fortnightly</option></select>'),
        ("Date", '<input class="lab-input" type="date" value="2026-08-05">'),
        ("Time", '<input class="lab-input" type="time" value="16:30">'),
        ("Checkbox", '<label style="display:flex;gap:8px;align-items:center"><input type="checkbox" checked> Consent</label>'),
        ("Radio", '<label style="display:flex;gap:8px;align-items:center"><input type="radio" checked name="lab-r"> Weekly</label>'),
        ("Colour", '<input class="lab-input" type="color" value="#835D33" style="max-width:64px">'),
        ("Disabled field", '<input class="lab-input" value="Locked" disabled>'),
        ("Invalid", '<input class="lab-input" value="not-an-email" style="border-color:var(--danger)"><p style="color:var(--danger);font-size:12px;margin:6px 0 0">Enter a valid email.</p>'),
    ]),
    ("Feedback", [
        ("Success", '<div class="lab-chip" style="background:var(--success-soft);color:var(--on-success-soft);border-color:var(--success-border)">Published</div>'),
        ("Warning", '<div class="lab-chip" style="background:var(--warning-soft);color:var(--on-warning-soft);border-color:var(--warning-border)">Trial ends in 3 days</div>'),
        ("Danger", '<div class="lab-chip" style="background:var(--danger-soft);color:var(--on-danger-soft);border-color:var(--danger-border)">Payment failed</div>'),
        ("Info", '<div class="lab-chip" style="background:var(--info-soft);color:var(--on-info-soft);border-color:var(--info-border)">Draft — not public</div>'),
        ("Solid success", '<div class="lab-chip" style="background:var(--success);color:var(--on-role);border-color:var(--success)">Active</div>'),
        ("Solid danger", '<div class="lab-chip" style="background:var(--danger);color:var(--on-role);border-color:var(--danger)">Overdue</div>'),
        ("Progress", '<div style="height:6px;border-radius:999px;background:var(--bg2);overflow:hidden"><div style="width:62%;height:100%;background:var(--accent)"></div></div>'),
        ("Empty state", '<div style="text-align:center;color:var(--muted);padding:16px;border:1px dashed var(--line-strong);border-radius:10px">No students yet</div>'),
    ]),
    ("Data", [
        ("Table", '<table class="lab-table"><thead><tr><th>Student</th><th>Credits</th></tr></thead>'
                  '<tbody><tr><td>Ada</td><td class="num">12</td></tr>'
                  '<tr class="hover"><td>Grace</td><td class="num">4</td></tr></tbody></table>'),
        ("Stat", '<div><div style="color:var(--muted);font-size:12px">Active students</div>'
                 '<div style="font-size:34px;color:var(--ink);font-variant-numeric:tabular-nums">128</div></div>'),
        ("Link", '<a href="#" style="color:var(--accent)">Open the public site →</a>'),
    ]),
    ("Content", [
        ("Hero", '<div style="padding:20px;background:var(--bg)"><p style="color:var(--muted);font-size:11px;letter-spacing:.3em;margin:0">ART</p>'
                 '<h3 style="margin:8px 0;color:var(--ink);font-size:28px;font-weight:500">Create boldly.</h3>'
                 '<p style="color:var(--ink2);margin:0 0 14px">Where beginners become confident makers.</p>'
                 '<button class="lab-btn" style="background:var(--accent);color:var(--on-accent);border:0">Book a Trial</button></div>'),
        ("Inverted band", '<div style="padding:20px;background:var(--ink);color:var(--bg);'
                          '--muted:color-mix(in srgb,var(--bg) 72%,var(--ink));--clay:color-mix(in srgb,var(--bg) 82%,var(--ink))">'
                          '<p style="color:var(--muted);font-size:11px;letter-spacing:.3em;margin:0">STUDENT AREA</p>'
                          '<p style="margin:8px 0 0">Sign in to see credits <span style="color:var(--clay)">→</span></p></div>'),
        ("Course card", '<div style="background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px">'
                        '<div style="color:var(--ink);font-weight:500">Saturday Oil Painting</div>'
                        '<div style="color:var(--muted);font-size:13px;margin-top:4px">10 sessions · ages 8+</div></div>'),
        ("FAQ", '<details style="border-bottom:1px solid var(--line);padding:10px 0"><summary style="color:var(--ink);cursor:pointer">Is there a trial class?</summary>'
                '<p style="color:var(--ink2);margin:8px 0 0">Yes — leave your details and the studio will be in touch.</p></details>'),
    ]),
]

# Pairs printed live under each theme. The same list the generator asserts, so
# a red cell in the lab is a failing assertion in the build, not a second
# opinion about what "readable" means.
LAB_PAIRS = [(name, fg, bg, need) for name, fg, bg, need in pg.CHECKS]


def theme_rows():
    rows = {}
    for spec in pg.THEMES:
        for mode in spec.get('modes', pg.MODES_DEFAULT):
            rows[f"{spec['key']}:{mode}"] = {
                'label': spec['label'], 'label_zh': spec['label_zh'],
                'harmony': spec['harmony'], 'mood': spec['mood'],
                'internal': bool(spec.get('internal')),
                'theme': pg.build(spec, mode == 'dark'),
            }
    return rows


def spec_inputs():
    """Only the fields a slider may move, plus what identifies the theme."""

    out = []
    for spec in pg.THEMES:
        out.append({k: v for k, v in spec.items()
                    if k in ('key', 'label', 'hue', 'sat', 'sec_off', 'sec_sat', 'sec_hue',
                             'ink_hue', 'ink_sat', 'accent_hue', 'accent_sat',
                             'accent_target', 'anchors', 'modes', 'harmony', 'internal')})
    return out


def render() -> str:
    solver = (HERE / 'solver.js').read_text(encoding='utf-8')
    data = json.dumps({
        'themes': theme_rows(),
        'specs': spec_inputs(),
        'pairs': [[n, f, b, t] for n, f, b, t in LAB_PAIRS],
        'roleNames': pg.CSS_ROLE_NAMES,
        'tokenOrder': pg.TOKEN_ORDER,
    }, ensure_ascii=False, separators=(',', ':'))
    groups = json.dumps(COMPONENTS, ensure_ascii=False)
    count = sum(len(items) for _, items in COMPONENTS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>StudioSaaS design lab · {len(theme_rows())} theme-modes × {count} components</title>
<!--
  GENERATED by docs/design/build_lab.py. Do not hand-edit — regenerate.
  backend/tests/test_design_lab.py fails on any difference.
-->
<style>
  :root {{
    color-scheme: light dark;
    --lab-bg:#101317; --lab-panel:#181C22; --lab-ink:#E8EBEF; --lab-muted:#98A2B0;
    --lab-line:#252B33; --lab-ok:#3E9E6B; --lab-bad:#D2685C;
    font-family:"PingFang SC","Hiragino Sans GB",system-ui,-apple-system,sans-serif;
  }}
  body {{ margin:0; background:var(--lab-bg); color:var(--lab-ink); font-size:14px; line-height:1.6; }}
  .lab-head {{ position:sticky; top:0; z-index:20; display:flex; flex-wrap:wrap; gap:13px;
    align-items:center; padding:13px 21px; background:var(--lab-panel);
    border-bottom:1px solid var(--lab-line); }}
  .lab-head h1 {{ margin:0; font-size:16px; font-weight:600; margin-right:auto; }}
  .lab-head select, .lab-head button {{ min-height:34px; padding:5px 11px; border-radius:8px;
    border:1px solid var(--lab-line); background:var(--lab-bg); color:var(--lab-ink);
    font:inherit; font-size:13px; cursor:pointer; }}
  .lab-head button[aria-pressed="true"] {{ background:var(--lab-ink); color:var(--lab-bg); }}
  .lab-body {{ padding:21px; display:grid; gap:21px; grid-template-columns:minmax(0,1.618fr) minmax(0,1fr); }}
  @media (max-width:1100px) {{ .lab-body {{ grid-template-columns:1fr; }} }}
  .stage {{ border:1px solid var(--lab-line); border-radius:13px; overflow:hidden; }}
  .stage-inner {{ padding:21px; display:grid; gap:21px; }}
  .group h2 {{ margin:0 0 8px; font-size:11px; letter-spacing:.18em; text-transform:uppercase;
    color:var(--muted); font-weight:600; }}
  .items {{ display:grid; gap:13px; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); }}
  .item > .name {{ font-size:10.5px; letter-spacing:.08em; text-transform:uppercase;
    color:var(--muted); margin-bottom:5px; }}
  .lab-surface {{ padding:16px; border-radius:8px; font:600 11px/1 ui-monospace,monospace; color:var(--ink); }}
  .lab-btn {{ min-height:38px; padding:9px 16px; border-radius:var(--radius,8px); font:inherit;
    font-size:13px; font-weight:600; cursor:pointer; }}
  .lab-input {{ width:100%; min-height:38px; padding:8px 11px; border-radius:var(--radius,8px);
    border:1px solid var(--line-strong); background:var(--panel); color:var(--ink); font:inherit; }}
  .lab-chip {{ display:inline-flex; align-items:center; min-height:26px; padding:3px 10px;
    border:1px solid transparent; border-radius:999px; font-size:12px; font-weight:600; }}
  .lab-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  .lab-table th {{ text-align:left; padding:8px 10px; background:var(--bg2); color:var(--ink2);
    font-weight:600; font-size:11px; letter-spacing:.06em; text-transform:uppercase; }}
  .lab-table td {{ padding:8px 10px; border-top:1px solid var(--line); color:var(--ink); }}
  .lab-table tr.hover td {{ background:var(--surface-hover); }}
  .lab-table .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  aside {{ position:sticky; top:70px; align-self:start; display:grid; gap:13px; }}
  .card {{ border:1px solid var(--lab-line); border-radius:13px; padding:13px 16px; background:var(--lab-panel); }}
  .card h3 {{ margin:0 0 8px; font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:var(--lab-muted); }}
  table.audit {{ width:100%; border-collapse:collapse; font-size:11.5px; }}
  table.audit td {{ padding:2px 0; border-top:1px solid var(--lab-line); }}
  table.audit td.n {{ text-align:right; font-family:ui-monospace,monospace; }}
  .ok {{ color:var(--lab-ok); }} .bad {{ color:var(--lab-bad); font-weight:700; }}
  .swatches {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(58px,1fr)); gap:5px; }}
  .sw {{ height:34px; border-radius:5px; border:1px solid var(--lab-line); position:relative; }}
  .sw span {{ position:absolute; left:0; right:0; bottom:-14px; font:500 8.5px/1 ui-monospace,monospace;
    text-align:center; color:var(--lab-muted); }}
  .sw-wrap {{ padding-bottom:15px; }}
  .tune label {{ display:grid; grid-template-columns:88px 1fr 52px; gap:8px; align-items:center;
    font-size:11.5px; margin-bottom:6px; }}
  .tune output {{ font-family:ui-monospace,monospace; text-align:right; }}
  .tune input[type=range] {{ width:100%; }}
  pre.emit {{ margin:8px 0 0; padding:10px; border-radius:8px; background:var(--lab-bg);
    border:1px solid var(--lab-line); font-size:11px; overflow-x:auto; white-space:pre; }}
  [hidden] {{ display:none !important; }}
</style>
</head>
<body>
<header class="lab-head">
  <h1>StudioSaaS design lab</h1>
  <select id="theme" aria-label="Theme"></select>
  <button id="mLight" aria-pressed="true">Light</button>
  <button id="mDark" aria-pressed="false">Dark</button>
  <button id="mTune" aria-pressed="false">Tune</button>
</header>

<div class="lab-body">
  <main class="stage" id="stage"><div class="stage-inner" id="gallery"></div></main>
  <aside>
    <div class="card">
      <h3>Tokens</h3>
      <div class="swatches" id="swatches"></div>
    </div>
    <div class="card">
      <h3>Assertions <span id="verdict"></span></h3>
      <table class="audit"><tbody id="audit"></tbody></table>
    </div>
    <div class="card tune" id="tunePanel" hidden>
      <h3>Generator inputs</h3>
      <p style="margin:0 0 10px;font-size:11.5px;color:var(--lab-muted)">
        These move the solver's inputs, never a hex. Paste the result into
        <code>THEMES</code> in palette_gen.py and regenerate.</p>
      <div id="sliders"></div>
      <button id="copySpec" style="margin-top:8px;width:100%">Copy THEMES entry</button>
      <pre class="emit" id="emit"></pre>
    </div>
  </aside>
</div>

<script>{solver}</script>
<script>
const DATA = {data};
const GROUPS = {groups};

const $ = (id) => document.getElementById(id);
let mode = 'light';
let themeKey = 'atelier-clay';
let tuned = null;

function currentSpec() {{
  return DATA.specs.find((s) => s.key === themeKey) || DATA.specs[0];
}}

function availableModes() {{
  return (currentSpec().modes || ['light', 'dark']);
}}

function currentTheme() {{
  if (mode === 'tune' && tuned) return build(tuned, tunedDark());
  const key = themeKey + ':' + mode;
  if (DATA.themes[key]) return DATA.themes[key].theme;
  /* A theme that ships one mode has no palette for the other, and showing the
     one it does have under the other label is worse than showing nothing:
     the first version of this lab reported `arcade-lime:light — all clear`
     while displaying its dark palette. The button is disabled instead. */
  return DATA.themes[themeKey + ':' + availableModes()[0]].theme;
}}

function syncModeButtons() {{
  const modes = availableModes();
  [['mLight', 'light'], ['mDark', 'dark']].forEach(([id, value]) => {{
    const button = $(id);
    const offered = modes.includes(value);
    button.disabled = !offered;
    button.style.opacity = offered ? '' : '.35';
    button.title = offered ? '' : `${{currentSpec().label}} ships ${{modes[0]}} only`;
  }});
  if (mode !== 'tune' && !modes.includes(mode)) setMode(modes[0]);
}}

function tunedDark() {{
  const modes = (tuned.modes || ['light', 'dark']);
  return modes.length === 1 ? modes[0] === 'dark' : lastRealMode === 'dark';
}}
let lastRealMode = 'light';

function applyTokens(theme) {{
  const stage = $('stage');
  Object.entries(DATA.roleNames).forEach(([key, names]) => {{
    if (theme[key] === undefined) return;
    names.forEach((n) => stage.style.setProperty(n, theme[key]));
  }});
  // Aliases the public pages use, so the gallery is styled exactly as they are.
  stage.style.setProperty('--clay', theme.accent_color);
  stage.style.setProperty('--on-role', theme.accent_text_color);
  stage.style.setProperty('--radius', '8px');
  stage.style.background = theme.background_color;
  stage.style.colorScheme = theme.color_scheme;
}}

function renderGallery() {{
  $('gallery').innerHTML = GROUPS.map(([group, items]) => `
    <section class="group">
      <h2>${{group}}</h2>
      <div class="items">
        ${{items.map(([name, html]) => `<div class="item"><div class="name">${{name}}</div>${{html}}</div>`).join('')}}
      </div>
    </section>`).join('');
}}

function renderSwatches(theme) {{
  $('swatches').innerHTML = DATA.tokenOrder
    .filter((k) => k !== 'color_scheme' && String(theme[k] || '').startsWith('#'))
    .map((k) => {{
      const short = (DATA.roleNames[k] || ['--?'])[0].replace('--', '');
      return `<div class="sw-wrap"><div class="sw" style="background:${{theme[k]}}"></div>` +
             `<span>${{short}}</span></div>`;
    }}).join('');
}}

function renderAudit(theme) {{
  let bad = 0;
  const rows = DATA.pairs.map(([name, fg, bg, need]) => {{
    if (theme[fg] === undefined || theme[bg] === undefined) return '';
    const r = ratio(theme[fg], theme[bg]);
    const ok = r >= need;
    if (!ok) bad++;
    return `<tr><td>${{name}}</td><td class="n ${{ok ? 'ok' : 'bad'}}">${{r.toFixed(2)}}</td>` +
           `<td class="n" style="color:var(--lab-muted)">${{need}}</td></tr>`;
  }}).join('');
  $('audit').innerHTML = rows;
  $('verdict').innerHTML = bad
    ? `<span class="bad">${{bad}} failing</span>`
    : `<span class="ok">all clear</span>`;
}}

const SLIDERS = [
  ['hue', 0, 359, 1], ['sat', 0, 1, 0.01],
  ['sec_off', -180, 180, 1], ['sec_sat', 0, 1, 0.01],
  ['ink_hue', 0, 359, 1], ['ink_sat', 0, 1, 0.01],
  ['accent_hue', 0, 359, 1], ['accent_sat', 0, 1, 0.01],
];

function renderSliders() {{
  const spec = tuned || currentSpec();
  $('sliders').innerHTML = SLIDERS.map(([field, min, max, step]) => {{
    const value = spec[field] !== undefined ? spec[field]
      : (field.startsWith('ink') ? (field === 'ink_hue' ? spec.hue : spec.sat)
        : field.startsWith('accent') ? (field === 'accent_hue' ? spec.hue : spec.sat)
        : (field === 'sec_off' ? 0 : 0.4));
    return `<label><span>${{field}}</span>` +
           `<input type="range" data-field="${{field}}" min="${{min}}" max="${{max}}" step="${{step}}" value="${{value}}">` +
           `<output>${{Number(value).toFixed(step < 1 ? 2 : 0)}}</output></label>`;
  }}).join('');
}}

function emitSpec() {{
  const s = tuned || currentSpec();
  const f = (v, d) => Number(v).toFixed(d);
  $('emit').textContent =
    `dict(key='${{s.key}}', label='${{s.label}}',\\n` +
    `     hue=${{f(s.hue, 0)}},  sat=${{f(s.sat, 2)}}, ` +
    `sec_off=${{f(s.sec_off !== undefined ? s.sec_off : 0, 0)}}, sec_sat=${{f(s.sec_sat, 2)}},\\n` +
    (s.ink_hue !== undefined ? `     ink_hue=${{f(s.ink_hue, 0)}}, ink_sat=${{f(s.ink_sat, 2)}},\\n` : '') +
    (s.accent_hue !== undefined ? `     accent_hue=${{f(s.accent_hue, 0)}}, accent_sat=${{f(s.accent_sat, 2)}},\\n` : '') +
    `     harmony='${{s.harmony}}')`;
}}

function draw() {{
  const theme = currentTheme();
  applyTokens(theme);
  renderSwatches(theme);
  renderAudit(theme);
  if (mode === 'tune') emitSpec();
}}

function setMode(next) {{
  mode = next;
  if (next !== 'tune') lastRealMode = next;
  ['mLight', 'mDark', 'mTune'].forEach((id, i) =>
    $(id).setAttribute('aria-pressed', String(['light', 'dark', 'tune'][i] === next)));
  $('tunePanel').hidden = next !== 'tune';
  if (next === 'tune') {{ tuned = JSON.parse(JSON.stringify(currentSpec())); renderSliders(); }}
  draw();
}}

$('theme').innerHTML = DATA.specs.map((s) =>
  `<option value="${{s.key}}">${{s.label}}${{s.internal ? ' (internal)' : ''}}</option>`).join('');
$('theme').value = themeKey;
$('theme').addEventListener('change', () => {{
  themeKey = $('theme').value;
  if (mode === 'tune') {{ tuned = JSON.parse(JSON.stringify(currentSpec())); renderSliders(); }}
  syncModeButtons();
  draw();
}});
$('mLight').addEventListener('click', () => setMode('light'));
$('mDark').addEventListener('click', () => setMode('dark'));
$('mTune').addEventListener('click', () => setMode('tune'));
$('sliders').addEventListener('input', (event) => {{
  const field = event.target.dataset.field;
  if (!field || !tuned) return;
  tuned[field] = Number(event.target.value);
  event.target.nextElementSibling.textContent =
    Number(event.target.value).toFixed(Number(event.target.step) < 1 ? 2 : 0);
  draw();
}});
$('copySpec').addEventListener('click', () => {{
  navigator.clipboard.writeText($('emit').textContent).then(
    () => {{ $('copySpec').textContent = 'Copied'; setTimeout(() => {{ $('copySpec').textContent = 'Copy THEMES entry'; }}, 1200); }},
    () => {{ $('copySpec').textContent = 'Select the text below'; }});
}});

renderGallery();
syncModeButtons();
draw();
</script>
</body>
</html>
"""


if __name__ == '__main__':
    target = HERE / 'lab.html'
    target.write_text(render(), encoding='utf-8')
    modes = len(theme_rows())
    parts = sum(len(items) for _, items in COMPONENTS)
    print(f'wrote {target.relative_to(HERE.parents[1])} — {modes} theme-modes x {parts} components')
