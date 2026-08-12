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
        # reproducing the query exactly. `/slug#home:faq` against `/slug?lang=en`
        # is a different URL, so the browser reloaded and dropped `lang`.
        ("/demo-studio", "?lang=en", "/demo-studio?lang=en#home:faq"),
        ("/demo-studio/", "?lang=en", "/demo-studio/?lang=en#home:faq"),
        ("/demo-studio", "?utm_source=wechat", "/demo-studio?utm_source=wechat#home:faq"),
        ("/demo-studio", "", "/demo-studio#home:faq"),
        # Away from home the link has to name the home page. The visitor's
        # language travels with them; a page-local filter does not.
        ("/demo-studio/showcase", "?lang=en&category=abc", "/demo-studio?lang=en#home:faq"),
        ("/demo-studio/showcase", "", "/demo-studio#home:faq"),
        ("/demo-studio/timetable", "?lang=zh", "/demo-studio?lang=zh#home:faq"),
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
    assert _run_probe(body, tmp_path)["href"] == expected


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
    markup = "\n".join((TEMPLATE_DIR / name).read_text(encoding="utf-8") for name in PAGES)
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

    for name in NAV_PAGES:
        source = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        assert re.search(r"\.navlinks\s+a\.navcta\s*\{", source), name
        assert not re.search(r"(?m)^\s*\.navcta\s*[{:]", source), f"{name} still has a bare .navcta rule"
        cta_rule = re.search(r"\.navlinks\s+a\.navcta\s*\{([^}]*)\}", source).group(1)
        assert "white-space" in cta_rule and "nowrap" in cta_rule, name
        assert "text-overflow" in cta_rule, name
