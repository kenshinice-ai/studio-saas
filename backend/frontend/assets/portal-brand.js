/* One palette, applied by one function, on every public surface.
 *
 * The token map below used to exist twice — once inline in the portal and once
 * inline in the register page — and the two had already drifted: the portal
 * mapped `accent_color` to two variables and the register page to three. A
 * third copy was about to be written for the timetable page, which is the
 * moment to stop.
 *
 * The rule this enforces is the product's oldest colour rule: **a colour has
 * exactly one source, and a surface may not declare its own — a fallback value
 * counts as declaring one.** A page that keeps its own copy of this map is a
 * page that will one day render half a theme, silently, with no error
 * anywhere, because a token added to the palette was added to two of the three
 * copies.
 *
 * Loaded before the page's own script so `applyVisualTheme` is defined by the
 * time /brand answers.
 */
(function (global) {
  'use strict';

  /* Server token → the CSS custom properties it feeds. The aliases are not
     redundancy: `--clay` is the portal's own name for the accent and
     `--brand-accent` is the shared design-system name, and both are referenced
     by stylesheets this file cannot see. */
  var THEME_TOKENS = {
    background_color:       ['--bg', '--brand-paper'],
    background_alt_color:   ['--bg2'],
    panel_color:            ['--panel', '--surface', '--brand-paper-raised'],
    text_color:             ['--ink', '--brand-ink'],
    text_soft_color:        ['--ink2'],
    muted_text_color:       ['--muted', '--brand-ink-soft'],
    border_color:           ['--line', '--brand-line'],
    border_strong_color:    ['--line-strong'],
    accent_color:           ['--clay', '--brand', '--brand-accent'],
    accent_hover_color:     ['--clay-hover'],
    accent_pressed_color:   ['--clay-pressed'],
    accent_text_color:      ['--on-accent', '--brand-on-accent'],
    secondary_accent_color: ['--clay-d', '--brand-2', '--brand-accent-strong'],
    success_color:          ['--success', '--brand-success'],
    warning_color:          ['--warning', '--brand-warning'],
    danger_color:           ['--danger', '--brand-danger'],
    focus_ring_color:       ['--focus-ring'],
    disabled_surface_color: ['--disabled-surface'],
    disabled_text_color:    ['--disabled-text'],
    surface_hover_color:    ['--surface-hover'],
    accent_muted_text_color:['--on-accent-muted'],
    accent_soft_color:      ['--accent-soft'],
    accent_on_soft_color:   ['--on-accent-soft'],
    accent_border_color:    ['--accent-border'],
    secondary_soft_color:   ['--accent-2-soft'],
    secondary_on_soft_color:['--on-accent-2-soft'],
    secondary_border_color: ['--accent-2-border'],
    success_soft_color:     ['--success-soft'],
    success_on_soft_color:  ['--on-success-soft'],
    success_border_color:   ['--success-border'],
    warning_soft_color:     ['--warning-soft'],
    warning_on_soft_color:  ['--on-warning-soft'],
    warning_border_color:   ['--warning-border'],
    danger_soft_color:      ['--danger-soft'],
    danger_on_soft_color:   ['--on-danger-soft'],
    danger_border_color:    ['--danger-border'],
    info_color:             ['--info'],
    info_soft_color:        ['--info-soft'],
    info_on_soft_color:     ['--on-info-soft'],
    info_border_color:      ['--info-border'],
    scrim_color:            ['--scrim']
  };

  function applyVisualTheme(b) {
    b = b || {};
    var visual = b.visualTheme || b.visual_theme || {};
    var root = document.documentElement;
    /* Who decides light or dark.
       The studio does, unless the studio said otherwise. `system` is the one
       setting that hands the choice to the visitor, and it is only ever
       offered where BOTH palettes were published — the server refuses it for a
       single-mode style rather than letting the page render a dark theme's
       tokens on a light surface. */
    var published = b.visualThemes || b.visual_themes || null;
    var preference = visual.scheme_preference || visual.schemePreference
                     || visual.color_scheme || visual.colorScheme || 'light';
    function schemeNow() {
      if (preference !== 'system' || !published) return preference === 'system' ? 'light' : preference;
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    function paint(scheme) {
      var theme = (published && published[scheme]) || visual;
      Object.keys(THEME_TOKENS).forEach(function (key) {
        var camel = key.replace(/_([a-z])/g, function (_, c) { return c.toUpperCase(); });
        var value = theme[key] || theme[camel] || visual[key] || visual[camel];
        if (!value) return;
        THEME_TOKENS[key].forEach(function (cssVar) { root.style.setProperty(cssVar, value); });
      });
      root.dataset.brandScheme = scheme;
      /* The browser chrome is a surface too. This was pinned to #F4F0E8 in the
         markup and never updated, so a studio on a dark theme got a cream
         address bar above a near-black page on every phone. */
      var meta = document.querySelector('meta[name="theme-color"]');
      var page = theme.background_color || theme.backgroundColor
                 || visual.background_color || visual.backgroundColor;
      if (meta && page) meta.setAttribute('content', page);
    }
    paint(schemeNow());
    if (preference === 'system' && published && window.matchMedia) {
      var query = window.matchMedia('(prefers-color-scheme: dark)');
      var onChange = function () { paint(schemeNow()); };
      /* Safari below 14 has no addEventListener on a MediaQueryList. */
      if (query.addEventListener) query.addEventListener('change', onChange);
      else if (query.addListener) query.addListener(onChange);
    }
    /* Legacy tenants stored only a primary/secondary colour. */
    var accent = visual.accent_color || visual.accentColor || b.primaryColor;
    if (accent && !(visual.accent_color || visual.accentColor)) {
      root.style.setProperty('--clay', accent);
      root.style.setProperty('--brand-accent', accent);
    }
    var secondary = visual.secondary_accent_color || visual.secondaryAccentColor
                    || b.secondaryColor || b.secondary_color;
    if (secondary && !(visual.secondary_accent_color || visual.secondaryAccentColor)) {
      root.style.setProperty('--clay-d', secondary);
      root.style.setProperty('--brand-accent-strong', secondary);
    }
    if (document.body) {
      var button = visual.button_style || visual.buttonStyle;
      var font = visual.font_mood || visual.fontMood;
      document.body.classList.toggle('button-rounded', button === 'rounded');
      document.body.classList.toggle('button-sharp', button === 'sharp');
      document.body.classList.toggle('font-modern', font === 'modern');
      document.body.classList.toggle('font-classic', font === 'classic');
    }
  }

  global.StudioSaaS = global.StudioSaaS || {};
  global.StudioSaaS.THEME_TOKENS = THEME_TOKENS;
  global.StudioSaaS.applyVisualTheme = applyVisualTheme;
})(window);
