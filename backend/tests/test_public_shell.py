"""The public shell: one header, one footer, one set of link rules.

These assertions exist because the three defects they pin were all invisible
from the source and only showed up in a browser:

* every in-page nav link on the home page became a full document load as soon
  as the visit carried a query string, which is every visit from an ad;
* four public pages carried four different footers, and the id lists in
  ``public-surface.js`` named two elements that exist in none of them;
* the timetable page never declared its own slug, so the one rewrite that makes
  hash links work away from the home page silently did nothing there.

The link rules are exercised through node against the shipped file rather than
grepped, because the bug was in what the rule computed, not in whether it was
written down.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from studiosaas.workspaces import rendered_template

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SURFACE_JS = PROJECT_ROOT / "backend/frontend/assets/public-surface.js"
TEMPLATE_DIR = PROJECT_ROOT / "tenant-template"
PAGES = ("index.html", "showcase.html", "timetable.html", "register.html")
# register.html has no header of its own yet; the other three carry the bar.
NAV_PAGES = ("index.html", "showcase.html", "timetable.html")

# A DOM small enough to read and large enough for apply() to run against.
DOM_SHIM = """
const NODES = new Map();
function node(id, tag, attrs) {
  const store = Object.assign({}, attrs || {});
  const self = {
    id,
    tagName: tag || 'A',
    style: {},
    dataset: {},
    textContent: '',
    hidden: false,
    getAttribute: (name) => (name in store ? store[name] : null),
    setAttribute: (name, value) => { store[name] = String(value); },
    removeAttribute: (name) => { delete store[name]; },
    get href() { return store.href || ''; },
    set href(value) { store.href = String(value); },
  };
  NODES.set(id, self);
  return self;
}
function makeScope(slug, language) {
  const ids = ['navPrincipal','navShowcase','navCourses','navTimetable','navGallery',
               'navFaq','navStudent','navPrimaryCta','heroSecondaryCta',
               'footShowcase','footCourses','footTimetable','footGallery','footFaq',
               'footStudent','footRegister'];
  NODES.clear();
  ids.forEach((id) => node(id, 'A', { href: '#placeholder' }));
  return {
    body: { dataset: { tenantSlug: slug } },
    documentElement: { lang: language || 'zh' },
    getElementById: (id) => NODES.get(id) || null,
    querySelectorAll: (selector) => {
      if (selector === 'a[aria-current="page"]') {
        return [...NODES.values()].filter((n) => n.getAttribute('aria-current') === 'page');
      }
      return [];
    },
  };
}
function contractFor(href) {
  const entry = (key, target) => ({
    key, visible: true, href: target, surface: key, placement: 'home',
    navigationEligible: true, footerEligible: true, reasonCode: 'ready',
    nextAction: '', label: { zh: key, en: key },
  });
  return {
    modules: {
      principal: entry('principal', '#home:artist'),
      showcase: entry('showcase', '/demo-studio/showcase'),
      courses: entry('courses', '#home:courses'),
      timetable: entry('timetable', '/demo-studio/timetable'),
      gallery: entry('gallery', '#home:gallery'),
      faq: entry('faq', href),
      student: entry('student', '#my'),
      register: entry('register', '#join'),
    },
    actions: {
      primary: { key: 'primary', visible: true, href: '#join', label: { zh: 'x', en: 'x' } },
      secondary: { key: 'secondary', visible: false, href: '', targetType: 'hidden' },
    },
  };
}
"""


def _run_probe(script_body: str, tmp_path: Path) -> dict:
    """Load the shipped module in node and return whatever the probe reports."""

    harness = tmp_path / "probe.mjs"
    harness.write_text(
        "import { readFileSync } from 'node:fs';\n"
        f"const source = readFileSync({json.dumps(str(SURFACE_JS))}, 'utf8');\n"
        "const load = (win) => new Function('window', source + '\\nreturn window.StudioSaaS.publicSurface;')(win);\n"
        + DOM_SHIM
        + script_body,
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["node", str(harness)], text=True, capture_output=True, check=True
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    ("path", "search", "expected"),
    [
        # On the home page the link must stay in the same document, which means
        # reproducing the query exactly. `/slug#faq` against `/slug?lang=en`
        # is a different URL, so the browser reloaded and dropped `lang`.
        #
        # The fragment is `#faq`, not `#home:faq`: the contract key names a
        # surface AND an anchor, and only the second half is an element id. The
        # composite used to reach the href unchanged, so all four of these links
        # pointed at ids that do not exist and moved the page zero pixels. This
        # test asserted the composite as a side effect of checking the query,
        # which is how the broken fragment survived every run.
        ("/demo-studio", "?lang=en", "/demo-studio?lang=en#faq"),
        ("/demo-studio/", "?lang=en", "/demo-studio/?lang=en#faq"),
        ("/demo-studio", "?utm_source=wechat", "/demo-studio?utm_source=wechat#faq"),
        ("/demo-studio", "", "/demo-studio#faq"),
        # Away from home the link has to name the home page. The visitor's
        # language travels with them; a page-local filter does not.
        ("/demo-studio/showcase", "?lang=en&category=abc", "/demo-studio?lang=en#faq"),
        ("/demo-studio/showcase", "", "/demo-studio#faq"),
        ("/demo-studio/timetable", "?lang=zh", "/demo-studio?lang=zh#faq"),
    ],
)
def test_hash_links_stay_in_the_document_they_belong_to(path, search, expected, tmp_path):
    """A nav click must not reload the page, and must not lose the query."""

    body = f"""
const win = {{ location: {{ pathname: {json.dumps(path)}, search: {json.dumps(search)},
                            href: 'https://example.test' + {json.dumps(path + search)} }} }};
const surface = load(win);
const scope = makeScope('demo-studio', 'zh');
surface.apply(contractFor('#home:faq'), scope);
console.log(JSON.stringify({{ href: scope.getElementById('navFaq').href }}));
"""
    href = _run_probe(body, tmp_path)["href"]
    assert href == expected
    # The real guard, stated once rather than implied by seven expectations: a
    # fragment a browser can resolve carries no colon. Without this line the
    # composite could return through any future contract change and every
    # assertion above would still be about query strings.
    assert ":" not in href.partition("#")[2]


def test_absolute_links_are_left_alone(tmp_path):
    """Only hash links are rewritten; a real path is already unambiguous."""

    body = """
const win = { location: { pathname: '/demo-studio', search: '?lang=en',
                          href: 'https://example.test/demo-studio?lang=en' } };
const surface = load(win);
const scope = makeScope('demo-studio', 'zh');
surface.apply(contractFor('#home:faq'), scope);
console.log(JSON.stringify({ showcase: scope.getElementById('navShowcase').href }));
"""
    assert _run_probe(body, tmp_path)["showcase"] == "/demo-studio/showcase"


def test_aria_current_survives_only_on_the_page_it_names(tmp_path):
    """The old test asked whether an href contained the last path segment.

    On a tenant home page that segment is the slug and every href begins with
    it, so the answer was yes for every link on the page.
    """

    body = """
const win = { location: { pathname: '/demo-studio/showcase', search: '',
                          href: 'https://example.test/demo-studio/showcase' } };
const surface = load(win);
const scope = makeScope('demo-studio', 'zh');
scope.getElementById('navShowcase').setAttribute('aria-current', 'page');
scope.getElementById('navTimetable').setAttribute('aria-current', 'page');
surface.apply(contractFor('#home:faq'), scope);
console.log(JSON.stringify({
  showcase: scope.getElementById('navShowcase').getAttribute('aria-current'),
  timetable: scope.getElementById('navTimetable').getAttribute('aria-current'),
}));
"""
    result = _run_probe(body, tmp_path)
    assert result["showcase"] == "page"
    assert result["timetable"] is None


def test_every_id_the_shell_drives_exists_in_a_template():
    """A name in the id list that no page defines is a rule nobody runs.

    `footPrincipal` and `heroRegister` sat in this file for three releases
    without existing anywhere, which is how the four footers drifted apart
    unnoticed.
    """

    source = SURFACE_JS.read_text(encoding="utf-8")
    named = set(re.findall(r"#((?:nav|mnav|foot|hero)[A-Z][A-Za-z]*)", source))
    named |= set(re.findall(r"'((?:nav|mnav|foot|hero)[A-Z][A-Za-z]*)'", source))
    markup = "\n".join(rendered_template(TEMPLATE_DIR, name) for name in PAGES)
    defined = set(re.findall(r'id="((?:nav|mnav|foot|hero)[A-Z][A-Za-z]*)"', markup))
    assert named <= defined, f"public-surface.js drives ids no page defines: {sorted(named - defined)}"


def test_every_page_declares_its_tenant_so_hash_links_can_be_resolved():
    """Without the slug on <body> the away-from-home rewrite does nothing."""

    for name in PAGES:
        source = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        assert 'data-tenant-slug="{{TENANT_SLUG}}"' in source, name


def test_the_home_page_never_leaves_its_header_behind_the_loading_mask():
    """The mask is only lifted by apply(); the failure branch has to reach it.

    The notice this branch shows says the page is displaying what it can, which
    was untrue of the header: it stayed hidden for the life of the page.
    """

    source = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    catch_block = source.split("publicSurface.fetch(API)", 1)[1].split("});", 1)[0]
    assert "clearLoading()" in catch_block
    assert "refreshPublicSurfaceContract()" in catch_block
    assert "surfaceSettled=true" in catch_block.replace(" ", "")


def test_pages_wait_for_the_authoritative_contract_before_drawing_a_header():
    """A locally guessed header that is corrected a moment later reads as a bug."""

    for name in NAV_PAGES:
        source = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        assert "surfaceSettled" in source, name


def test_the_nav_call_to_action_is_more_specific_than_the_plain_nav_link():
    """`.navlinks a` outranks `.navcta`, so the pill was drawn with `padding:4px 0`.

    The label is studio-authored and can be long, so it also has to stay on one
    line inside a bar that is only as tall as one line.
    """

    source = (PROJECT_ROOT / "backend/frontend/assets/public-shell.css").read_text(encoding="utf-8")
    assert re.search(r"\.navlinks\s+a\.navcta\s*\{", source)
    assert not re.search(r"(?m)^\s*\.navcta\s*[{:]", source)
    cta_rule = re.search(r"\.navlinks\s+a\.navcta\s*\{([^}]*)\}", source).group(1)
    assert "white-space" in cta_rule and "nowrap" in cta_rule
    assert "text-overflow" in cta_rule


def test_public_nav_brand_and_menu_have_a_non_overflowing_flex_contract():
    """A logo plus name must yield space to the menu on narrow viewports.

    ``flex-shrink:0`` on the brand combined with a shrinkable menu button
    pushed the latter beyond a 375px viewport on timetable and showcase.
    Keep the invariant in all three public shells so a future template edit
    cannot reintroduce the same mobile defect in only one document.
    """

    source = (PROJECT_ROOT / "backend/frontend/assets/public-shell.css").read_text(encoding="utf-8")
    brand = re.search(r"(?m)^\.brand\s*\{([^}]*)\}", source)
    menu = re.search(r"(?m)^\.menu-btn\s*\{([^}]*)\}", source)
    assert brand and menu
    brand_rule = brand.group(1).replace(" ", "")
    menu_rule = menu.group(1).replace(" ", "")
    assert "min-width:0" in brand_rule
    # Desktop brand is content-sized, never growing, with a hard cap. The old
    # fixed 25% basis clamped the studio name at EVERY width — a wide monitor
    # still showed "Let's Pai…" because the box, not the space, was the limit.
    # fitNavigation() measures the brand's full content width now, so the box
    # only has to bound the pathological case.
    assert "flex:01auto" in brand_rule
    assert "max-width:50%" in brand_rule
    assert re.search(r"@media\s*\(max-width:900px\)[\s\S]*?\.brand\s*\{\s*flex:1 1 auto", source)
    assert "flex:00var(--tap-min)" in menu_rule
    for name in NAV_PAGES:
        assert "overflow-x:hidden" not in (TEMPLATE_DIR / name).read_text(encoding="utf-8"), name


def test_home_courses_collapse_before_phone_width():
    """The four-column course grid must not create a 320px page overflow."""

    source = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    mobile_blocks = re.findall(r"@media\s*\(max-width:520px\)\s*\{([^}]*)\}", source, re.S)
    mobile = next((block for block in mobile_blocks if "course-grid" in block), "")
    assert mobile
    assert re.search(r"\.course-grid\s*\{[^}]*grid-template-columns\s*:\s*1fr", mobile)


def test_the_four_pages_offer_the_same_entries():
    """FAQ used to exist only in the home page's footer.

    Four hand-maintained copies of one list is four chances to drift, and they
    had: the timetable page linked to itself with no id, so the switch could
    not hide it, and the register page's studio name used a different id from
    every other page's.
    """

    footers = {}
    for name in PAGES:
        page = rendered_template(TEMPLATE_DIR, name)
        footers[name] = set(re.findall(r'id="(foot(?:Showcase|Courses|Timetable|Gallery|Faq|Student|Register))"', page))
        assert 'id="footName"' in page, f"{name} names the studio by a different id"
    expected = {"footShowcase", "footCourses", "footTimetable", "footGallery",
                "footFaq", "footStudent", "footRegister"}
    for name, ids in footers.items():
        assert ids == expected, f"{name} footer offers {sorted(ids)}"

    headers = {}
    for name in NAV_PAGES:
        page = rendered_template(TEMPLATE_DIR, name)
        headers[name] = set(re.findall(r'id="((?:nav|mnav)[A-Z][A-Za-z]*)"', page))
    assert len(set(map(frozenset, headers.values()))) == 1, headers


def test_the_entry_lists_have_exactly_one_source():
    """A page that writes its own entries can drift from the others again."""

    for name in PAGES:
        source = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        assert "<!--@shell:footer-links-->" in source, name
        assert 'id="footShowcase"' not in source, f"{name} still hand-writes footer entries"
    for name in NAV_PAGES:
        source = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        assert "<!--@shell:nav-links-->" in source and "<!--@shell:mnav-links-->" in source, name
        assert 'id="navShowcase"' not in source, f"{name} still hand-writes header entries"


def test_a_studio_cannot_write_a_nav_entry_the_bar_cannot_hold():
    """One studio's English course label is 74 characters. The bar is one line.

    The heading on the page keeps the whole sentence; only the entry is cut,
    and the server and the browser have to cut it identically or a contract
    failure would visibly change the wording.
    """

    import importlib

    api_v1 = importlib.import_module("studiosaas.api_v1")
    long_en = "Oil Painting, Acrylic Painting, Oil Soft Pastel, Acrylic Marker, Watercolour"
    long_zh = "艺术形式与课程安排表格很长很长"
    assert api_v1._clip_nav_label(long_en, "en") == "Oil Painting, Acrylic P…"
    assert api_v1._clip_nav_label(long_zh, "zh") == "艺术形式与课程安排…"
    assert api_v1._clip_nav_label("Timetable", "en") == "Timetable"
    # The pill has the least room and the most padding, so it gets less.
    assert api_v1._clip_nav_label("原创油画 × 私人定制", "zh", api_v1.CTA_LABEL_LIMIT) == "原创油画 ×…"
    assert api_v1._clip_nav_label("Original Personalised Oil Painting", "en",
                                  api_v1.CTA_LABEL_LIMIT) == "Original Personal…"


def test_the_browser_clips_a_nav_entry_the_same_way_the_server_does(tmp_path):
    """Two implementations of one rule; a parity check is what keeps them one."""

    import importlib

    api_v1 = importlib.import_module("studiosaas.api_v1")
    long_en = "Oil Painting, Acrylic Painting, Oil Soft Pastel, Acrylic Marker, Watercolour"
    long_zh = "艺术形式与课程安排表格很长很长"
    body = f"""
const win = {{ location: {{ pathname: '/demo-studio', search: '', href: 'https://example.test/demo-studio' }} }};
const surface = load(win);
const contract = surface.resolve({{ slug: 'demo-studio', brand: {{ localizedCopy: {{
  courses_label: {{ zh: {json.dumps(long_zh)}, en: {json.dumps(long_en)} }} }} }} }});
console.log(JSON.stringify(contract.modules.courses.label));
"""
    label = _run_probe(body, tmp_path)
    assert label["en"] == api_v1._clip_nav_label(long_en, "en")
    assert label["zh"] == api_v1._clip_nav_label(long_zh, "zh")


def test_css_never_clips_before_the_contract_does(tmp_path):
    """Two truncations produced an ellipsis inside an ellipsis.

    `16ch` is roughly 8em, narrower than the ten Chinese characters the
    contract already allows, so the browser cut a label the server had already
    cut. The contract is the limit; these values are a safety net for a label
    that somehow arrives unclipped.
    """

    source = (PROJECT_ROOT / "backend/frontend/assets/public-shell.css").read_text(encoding="utf-8")
    for selector in (r"\.navlinks\s+a\s*\{", r"\.navlinks\s+a\.navcta\s*\{"):
        rule = re.search(selector + r"([^}]*)\}", source).group(1)
        width = re.search(r"max-width:\s*([0-9.]+)(ch|em|px)", rule)
        assert width, f"shared public shell {selector} has no max-width"
        assert width.group(2) == "em"
        assert float(width.group(1)) >= 11


def test_the_call_to_action_is_shorter_than_the_rest_of_the_bar(tmp_path):
    """Server and browser have to agree, or a contract failure rewords the pill."""

    import importlib

    api_v1 = importlib.import_module("studiosaas.api_v1")
    slogan_zh, slogan_en = "原创油画 × 私人定制", "Original Personalised Oil Painting"
    body = f"""
const win = {{ location: {{ pathname: '/demo-studio', search: '', href: 'https://example.test/demo-studio' }} }};
const surface = load(win);
const contract = surface.resolve({{ slug: 'demo-studio', brand: {{ localizedCopy: {{
  primary_cta: {{ zh: {json.dumps(slogan_zh)}, en: {json.dumps(slogan_en)} }},
  courses_label: {{ zh: {json.dumps(slogan_zh)}, en: {json.dumps(slogan_en)} }} }} }} }});
console.log(JSON.stringify({{ cta: contract.modules.register.label,
                              section: contract.modules.courses.label }}));
"""
    result = _run_probe(body, tmp_path)
    assert result["cta"]["zh"] == api_v1._clip_nav_label(slogan_zh, "zh", api_v1.CTA_LABEL_LIMIT)
    assert result["cta"]["en"] == api_v1._clip_nav_label(slogan_en, "en", api_v1.CTA_LABEL_LIMIT)
    # A section entry keeps the roomier limit.
    assert len(result["section"]["en"]) > len(result["cta"]["en"])


BRAND_SHIM = """
function brandScope(withImg) {
  const made = [];
  function el(tag, cls) {
    const store = {};
    const classes = new Set(cls ? [cls] : []);
    const children = [];
    const self = {
      tagName: tag,
      style: {},
      dataset: {},
      textContent: '',
      children,
      classList: {
        add: (name) => classes.add(name),
        remove: (name) => classes.delete(name),
        contains: (name) => classes.has(name),
      },
      addEventListener: () => {},
      getAttribute: (name) => (name in store ? store[name] : null),
      setAttribute: (name, value) => { store[name] = String(value); },
      removeAttribute: (name) => { delete store[name]; },
      set src(value) { store.src = String(value); },
      get src() { return store.src || ''; },
      set alt(value) { store.alt = String(value); },
      get alt() { return store.alt || ''; },
      querySelector: (selector) => {
        if (selector === 'img') return children.find((c) => c.tagName === 'IMG') || null;
        if (selector === '.bn') return children.find((c) => c.isBn) || null;
        return null;
      },
    };
    made.push(self);
    return self;
  }
  const brand = el('A', 'brand');
  const img = el('IMG');
  const bn = el('SPAN');
  bn.isBn = true;
  bn.textContent = 'Template Name';
  brand.children.push(img, bn);
  return {
    brand, img, bn,
    doc: { querySelectorAll: (selector) => (selector === '.navrow .brand' ? [brand] : []) },
  };
}
"""


def test_the_brand_lockup_shows_the_logo_or_the_full_name_never_a_stub(tmp_path):
    """Logo present: the wordmark IS the name, the text hides, and the name
    survives on the link's aria-label. Logo absent (or a platform default
    mark): the full text name shows. Timetable used to render both and cut
    the text to "Let's…"; index and showcase never showed the logo at all.
    """

    body = """
const win = { location: { pathname: '/demo-studio', search: '', href: 'https://example.test/demo-studio' } };
const surface = load(win);
const withLogo = brandScope();
surface.applyBrandLockup({ name: "Let's Paint Studio", logo_url: '/media/wordmark.png' }, withLogo.doc);
const noLogo = brandScope();
noLogo.brand.classList.add('has-logo');
surface.applyBrandLockup({ name: "Let's Paint Studio" }, noLogo.doc);
const platformMark = brandScope();
surface.applyBrandLockup({ name: "Let's Paint Studio", logo_url: '/logo.png' }, platformMark.doc);
console.log(JSON.stringify({
  logoShown: withLogo.img.style.display,
  logoClass: withLogo.brand.classList.contains('has-logo'),
  logoAria: withLogo.brand.getAttribute('aria-label'),
  logoSrc: withLogo.img.src,
  plainClass: noLogo.brand.classList.contains('has-logo'),
  plainHidden: noLogo.img.style.display,
  plainName: noLogo.bn.textContent,
  markClass: platformMark.brand.classList.contains('has-logo'),
}));
"""
    result = _run_probe("\n" + BRAND_SHIM + body, tmp_path)
    assert result["logoShown"] == "block"
    assert result["logoClass"] is True
    assert result["logoAria"] == "Let's Paint Studio"
    assert result["logoSrc"] == "/media/wordmark.png"
    # No logo: the stale has-logo class is withdrawn and the full name shows.
    assert result["plainClass"] is False
    assert result["plainHidden"] == "none"
    assert result["plainName"] == "Let's Paint Studio"
    # The platform's own marks are never a tenant logo.
    assert result["markClass"] is False


def test_the_lockup_rule_lives_in_css_once():
    """`.brand.has-logo .bn` hiding the text is what makes "logo replaces
    name" a rule instead of three page-local display toggles."""

    css = re.sub(r"\s+", "", (PROJECT_ROOT / "backend/frontend/assets/public-shell.css").read_text(encoding="utf-8"))
    assert ".brand.has-logo.bn{display:none;}" in css or ".brand.has-logo.bn{display:none}" in css
    # The logo is sized by height, keeps its aspect ratio, and is bounded:
    # a fixed square is what turned an 8:1 wordmark into a smudge.
    img_rule = re.search(r"(?m)^\.brand img\s*\{([^}]*)\}", (PROJECT_ROOT / "backend/frontend/assets/public-shell.css").read_text(encoding="utf-8"))
    assert img_rule
    flat = img_rule.group(1).replace(" ", "")
    assert "height:40px" in flat
    assert "width:auto" in flat
    assert "max-width:140px" in flat
    assert "object-fit:contain" in flat


def test_the_three_nav_pages_share_one_brand_structure_and_one_lockup_call():
    """index/showcase/timetable each carry logo + text in `.brand`, and each
    hands the decision to the shared applyBrandLockup — a page deciding for
    itself is how the three headers diverged in the first place."""

    for name in NAV_PAGES:
        page = rendered_template(TEMPLATE_DIR, name)
        brand = re.search(r'<a class="brand"[^>]*>([\s\S]*?)</a>', page)
        assert brand, f"{name} has no .brand link in its header"
        assert "<img" in brand.group(1), f"{name} brand carries no logo slot"
        assert 'class="bn"' in brand.group(1), f"{name} brand carries no text name"
        assert "applyBrandLockup(" in page, f"{name} does not call the shared brand lockup"
        # No page-local logo reveal survives: the shared rule is the only one.
        assert not re.search(r"(?:tenantLogo|brandLogo)\W[\s\S]{0,120}?style\.display\s*=\s*'block'", page), (
            f"{name} still toggles the logo on its own")


def test_a_language_switch_re_measures_the_header(tmp_path):
    """UI-05: switching 中 → EN rewrites every nav label wider, but the clamp
    classes were measured against the Chinese widths, so every link truncated
    on a monitor with room to spare.

    The re-measure hooks the shared click surface (`data-set-lang` on the
    home page, `data-language` on showcase/timetable), and the state machine
    is re-entered through settleNavigation → fitNavigation, whose fitsWith()
    starts from resetStates() on every rung — a static shape this test pins
    because no headless run can measure real layout.
    """

    source = SURFACE_JS.read_text(encoding="utf-8")
    handler = re.search(r"addEventListener\('click',[\s\S]{0,600}?\}\);", source)
    assert handler, "public-surface.js has no shared click listener"
    block = handler.group(0)
    assert "[data-set-lang],[data-language]" in block
    assert "settleNavigation()" in block
    assert "fonts?.ready" in block, "the re-measure must wait for late-loading glyphs"
    # The rungs are only trustworthy if every measurement starts clean.
    fits_with = re.search(r"const fitsWith = \(state\) => \{([\s\S]*?)\};", source)
    assert fits_with and "resetStates()" in fits_with.group(1)
    # And the brand is measured by need (scrollWidth through the overflow
    # clip), not by the box it was allotted — an ellipsis is not a fit.
    fits_current = re.search(r"const fitsCurrentState = \(\) => \{([\s\S]*?)\n    \};", source)
    assert fits_current and "scrollWidth" in fits_current.group(1)


def test_public_nav_uses_one_wide_shell_and_four_measurement_rungs():
    """Desktop public navigation must share the same measurable contract.

    The production browser defect was not horizontal overflow; the home page
    kept its links at 1440px while the showcase and timetable silently chose
    the hamburger.  Pin the contract before changing the templates so this
    regression cannot be hidden by a page-local CSS patch.
    """

    shared = PROJECT_ROOT / "backend/frontend/assets/public-shell.css"
    assert shared.is_file(), "public navigation has no shared stylesheet"
    css = re.sub(r"\s+", "", shared.read_text(encoding="utf-8"))
    assert ".navrow" in css
    assert "max-width:1600px" in css

    surface = SURFACE_JS.read_text(encoding="utf-8")
    rung_order = re.search(
        r"nav-compact.*?nav-tight", surface, re.S
    )
    assert rung_order and "brand-name-hidden" in surface, (
        "fitNavigation must measure full -> brand-name-hidden -> nav-compact -> nav-tight"
    )

    for name in NAV_PAGES:
        source = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        assert '/assets/public-shell.css?v=__APP_VERSION__' in source, name
        assert not re.search(
            r"(?m)^\s*\.navrow\s*\{[^}]*width\s*:\s*min\(1180px",
            source,
        ), f"{name} still owns a conflicting 1180px nav width"
