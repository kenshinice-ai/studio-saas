"""UI acceptance matrix runner (REL-06).

Reads backend/scripts/ui_matrix.yaml (pages × widths × languages × actions),
drives a real Chromium via Playwright, and produces:

  <out>/screenshots/<page>__w<width>__<lang>.png     one per combination
  <out>/assertions.json                              every assertion, pass or fail

Usage:

  .venv/bin/python backend/scripts/ui_matrix.py [--base http://127.0.0.1:8100]
      [--config backend/scripts/ui_matrix.yaml] [--out ui_matrix_out]
      [--only <page-name>]

Exit codes: 0 all assertions pass · 1 assertion failures (see assertions.json)
· 2 Playwright/PyYAML not installed (this tool is DELIBERATELY not part of
verify_local.sh — the release gate must never depend on a browser download).

Two assertion sets:

* the nav/brand contract from public-surface.js fitNavigation() — labels are
  never clipped, the brand name only disappears when a logo replaces it, and
  the page never scrolls horizontally;
* the CMS density contract — a page's top-level block count stays under its
  budget, and a selected tab is never scrolled out of its own strip.

The second one exists because the 2026-09-03 density work's whole result is
rendered NUMBERS (the dashboard from 10 top-level blocks to 7, the settings
strip's selected tab from cut off to visible), and nothing in the repository
was watching them. A regression there is invisible to every other gate.

CMS pages sit behind a login, so they name a `role` and the runner signs in
over HTTP first. The password is read from the same 0600 file
capture_manual_shots.py uses — never a flag, never an environment variable.
Without that file the CMS pages are SKIPPED with a message, and the public
pages still run.

This is "measure the rendered page, not the code" made repeatable.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "ui_matrix.yaml"

INSTALL_GUIDE = """\
ui_matrix.py needs PyYAML and Playwright, which are intentionally NOT part of
requirements-dev.txt (verify_local.sh must never depend on a browser download).

Install into the project venv, once:

    .venv/bin/python -m pip install pyyaml playwright
    .venv/bin/python -m playwright install chromium

Then start the app (default base URL http://127.0.0.1:8100) and re-run.
"""

# The CMS contract. Same shape as the nav one: a list of
# {assertion, target, ok, detail}.
CMS_ASSERTIONS_JS = """
(options) => {
  const results = [];
  const push = (assertion, target, ok, detail) =>
    results.push({ assertion, target, ok, detail });
  const visible = (el) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };

  const doc = document.documentElement;
  push('no-horizontal-scroll', 'documentElement',
       doc.scrollWidth <= window.innerWidth + 1,
       `scrollWidth=${doc.scrollWidth} innerWidth=${window.innerWidth}`);

  // Every CMS panel roots at `.anim` — the product's own anchor. Counting its
  // direct children is what turned "the dashboard feels cluttered" into a
  // number, so it is the number worth guarding.
  // Most CMS panels root at `.anim` — the product's own anchor. Counting its
  // direct children is what turned "the dashboard feels cluttered" into a
  // number, so it is the number worth guarding. Two pages (billing, finance)
  // root elsewhere; there the block budget simply does not apply, and the
  // remaining assertions still do. A missing panel is not a failure — an
  // assertion that fires on a page it was never written for teaches people to
  // ignore the gate.
  const panel = document.querySelector('.anim');
  if (panel && options.maxBlocks) {
    const blocks = [...panel.children].filter(visible);
    push('top-level-blocks', '.anim',
         blocks.length <= options.maxBlocks,
         `${blocks.length} blocks, budget ${options.maxBlocks}`);
  }

  // Exactly one panel showing, and it is the one the selected tab controls.
  const tabs = [...document.querySelectorAll('[role="tab"]')].filter(visible);
  if (tabs.length) {
    const panels = [...document.querySelectorAll('[role="tabpanel"]')].filter(visible);
    push('one-panel-visible', '[role="tabpanel"]', panels.length === 1,
         `${panels.length} visible tabpanels`);

    const selected = tabs.filter(t => t.getAttribute('aria-selected') === 'true');
    push('one-tab-selected', '[role="tab"]', selected.length === 1,
         `${selected.length} selected tabs`);

    // A strip that scrolls must scroll to the tab you picked; otherwise a deep
    // link lands on a page where nothing looks chosen.
    if (selected.length === 1) {
      const strip = selected[0].parentElement;
      const view = strip.getBoundingClientRect(), tab = selected[0].getBoundingClientRect();
      push('selected-tab-in-view', selected[0].textContent.trim(),
           tab.left >= view.left - 1 && tab.right <= view.right + 1,
           `tab [${Math.round(tab.left)}, ${Math.round(tab.right)}] ` +
           `strip [${Math.round(view.left)}, ${Math.round(view.right)}]`);
    }
  }

  // Anything a thumb is meant to hit has to be hittable.
  const small = [...document.querySelectorAll('button, [role="tab"], a[role="button"]')]
    .filter(visible)
    .filter(el => { const r = el.getBoundingClientRect(); return r.height < 44 - 0.5; })
    .map(el => `${(el.textContent || '').trim().slice(0, 14) || el.getAttribute('aria-label') || '?'}` +
               `@${Math.round(el.getBoundingClientRect().height)}px`);
  push('touch-target-44px', 'button', small.length === 0,
       small.length ? small.slice(0, 6).join(', ') : 'all >= 44px');

  return results;
}
"""


# One evaluate() per page: returns a list of {assertion, target, ok, detail}.
NAV_BRAND_ASSERTIONS_JS = """
(selectors) => {
  const results = [];
  const push = (assertion, target, ok, detail) =>
    results.push({ assertion, target, ok, detail });

  // 1. The page itself must not scroll horizontally.
  const doc = document.documentElement;
  push(
    'no-horizontal-scroll', 'documentElement',
    doc.scrollWidth <= window.innerWidth + 1,
    `scrollWidth=${doc.scrollWidth} innerWidth=${window.innerWidth}`
  );

  const row = document.querySelector(selectors.navrow);
  const links = document.querySelector(selectors.navlinks);
  const brand = document.querySelector(selectors.brand);
  if (!row || !links || !brand) {
    push('nav-elements-present', selectors.navrow,
         Boolean(row && links && brand),
         `navrow=${Boolean(row)} navlinks=${Boolean(links)} brand=${Boolean(brand)}`);
    return results;
  }
  push('nav-elements-present', selectors.navrow, true, 'navrow, navlinks and brand all found');

  // 2. Every visible nav entry renders its whole label.
  for (const entry of links.children) {
    const style = getComputedStyle(entry);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    const label = (entry.textContent || '').trim().slice(0, 40) || '<no text>';
    push(
      'nav-label-not-clipped', label,
      entry.scrollWidth <= entry.clientWidth + 1,
      `scrollWidth=${entry.scrollWidth} clientWidth=${entry.clientWidth}`
    );
  }

  // 3. The brand: its name either fits or is deliberately hidden behind a logo.
  const logo = brand.querySelector('img');
  const logoVisible = Boolean(logo) && getComputedStyle(logo).display !== 'none';
  const nameHiddenState = row.classList.contains('brand-name-hidden');
  if (nameHiddenState) {
    push(
      'brand-name-hidden-only-with-logo', selectors.brand,
      logoVisible,
      logoVisible ? 'logo visible, name intentionally dropped'
                  : 'name hidden but NO visible logo replaces it'
    );
  } else {
    push(
      'brand-not-clipped', selectors.brand,
      brand.scrollWidth <= brand.clientWidth + 1,
      `scrollWidth=${brand.scrollWidth} clientWidth=${brand.clientWidth}`
    );
  }
  return results;
}
"""


def load_config(path: Path) -> dict:
    import yaml  # guarded in main()

    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or "pages" not in config:
        sys.exit(f"config {path} must be a mapping with a 'pages' list")
    return config


def run_actions(page, actions: list) -> None:
    for action in actions or []:
        if not isinstance(action, dict) or len(action) != 1:
            sys.exit(f"bad action (want one-key mapping): {action!r}")
        verb, arg = next(iter(action.items()))
        if verb == "click":
            page.click(arg)
        elif verb == "fill":
            selector, value = arg
            page.fill(selector, str(value))
        elif verb == "wait":
            page.wait_for_timeout(int(arg))
        else:
            sys.exit(f"unknown action verb: {verb!r} (know: click, fill, wait)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://127.0.0.1:8100",
                        help="base URL of a RUNNING app (default %(default)s)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=Path("ui_matrix_out"),
                        help="output root; a UTC-stamped run directory is created inside")
    parser.add_argument("--only", help="run only the page with this name")
    args = parser.parse_args()

    try:
        import yaml  # noqa: F401
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        print(f"missing dependency: {exc.name}", file=sys.stderr)
        print(INSTALL_GUIDE, file=sys.stderr)
        return 2

    config = load_config(args.config)
    defaults = config.get("defaults") or {}

    # Sign in once per role that any page asks for. Reusing
    # capture_manual_shots' helpers keeps one implementation of "read the 0600
    # file, POST /v1/auth/login, keep the cookie" rather than a second copy
    # that drifts. A missing credentials file is not a crash: the CMS pages are
    # skipped and the public ones still run, so this stays useful on a machine
    # that has never seeded the showcase.
    roles = {spec.get("role") for spec in config["pages"] if spec.get("role")}
    sessions: dict[str, str] = {}
    skipped_roles: dict[str, str] = {}
    if roles:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from capture_manual_shots import ROLE_EMAIL, login, read_demo_password
            password = read_demo_password()
            for role in sorted(roles):
                try:
                    sessions[role] = login(args.base, ROLE_EMAIL[role], password)
                except Exception as exc:            # noqa: BLE001 — reported, not raised
                    skipped_roles[role] = str(exc)
            del password
        except SystemExit as exc:
            for role in roles:
                skipped_roles[role] = str(exc)
        for role, why in skipped_roles.items():
            print(f"SKIP pages needing role {role!r}: {why}", file=sys.stderr)
    default_widths = defaults.get("widths") or [375, 768, 1280]
    default_langs = defaults.get("languages") or ["default"]
    height = int(defaults.get("height") or 900)
    default_selectors = defaults.get("selectors") or {}

    pages = config["pages"]
    if args.only:
        pages = [p for p in pages if p.get("name") == args.only]
        if not pages:
            sys.exit(f"no page named {args.only!r} in {args.config}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.out / stamp
    shots_dir = run_dir / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    failures = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for spec in pages:
            name = spec.get("name") or spec["path"].strip("/").replace("/", "_")
            role = spec.get("role")
            if role and role not in sessions:
                continue                            # 已在上面报告过原因
            widths = spec.get("widths") or default_widths
            languages = spec.get("languages") or default_langs
            selectors = {**default_selectors, **(spec.get("selectors") or {})}
            for width in widths:
                for lang in languages:
                    url = args.base.rstrip("/") + spec["path"]
                    if lang != "default":
                        url += ("&" if "?" in url else "?") + f"lang={lang}"
                    context = browser.new_context(
                        viewport={"width": int(width), "height": height})
                    if role:
                        host = args.base.split("//", 1)[-1].split(":")[0].split("/")[0]
                        context.add_cookies([{"name": "session", "value": sessions[role],
                                              "domain": host, "path": "/"}])
                    page = context.new_page()
                    combo = {"page": name, "width": int(width), "language": lang, "url": url}
                    try:
                        page.goto(url, wait_until="load", timeout=20000)
                        # fitNavigation settles via requestAnimationFrame after
                        # async content lands; give it a beat before measuring.
                        page.wait_for_timeout(600)
                        run_actions(page, spec.get("actions"))
                        shot = shots_dir / f"{name}__w{width}__{lang}.png"
                        page.screenshot(path=str(shot), full_page=True)
                        if spec.get("assert_cms"):
                            # The CMS mounts React after load; give it the same
                            # beat the panels need before the first paint.
                            page.wait_for_timeout(2200)
                            options = {"maxBlocks": int(spec.get("max_blocks", 8))}
                            for entry in page.evaluate(CMS_ASSERTIONS_JS, options):
                                record = {**combo, **entry}
                                results.append(record)
                                if not entry["ok"]:
                                    failures += 1
                                    print(f"FAIL {name} w{width} {lang}: "
                                          f"{entry['assertion']} [{entry['target']}] {entry['detail']}")
                        if spec.get("assert_nav", True):
                            for entry in page.evaluate(NAV_BRAND_ASSERTIONS_JS, selectors):
                                record = {**combo, **entry}
                                results.append(record)
                                if not entry["ok"]:
                                    failures += 1
                                    print(f"FAIL {name} w{width} {lang}: "
                                          f"{entry['assertion']} [{entry['target']}] {entry['detail']}")
                    except Exception as exc:  # a page that cannot load is a failed assertion, not a crash
                        failures += 1
                        results.append({**combo, "assertion": "page-loads", "target": spec["path"],
                                        "ok": False, "detail": str(exc)})
                        print(f"FAIL {name} w{width} {lang}: page-loads {exc}")
                    finally:
                        context.close()
        browser.close()

    report = {
        "base": args.base,
        "config": str(args.config),
        "ranAt": stamp,
        "total": len(results),
        "failures": failures,
        "results": results,
    }
    (run_dir / "assertions.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(results)} assertions, {failures} failed")
    print(f"screenshots : {shots_dir}")
    print(f"assertions  : {run_dir / 'assertions.json'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
