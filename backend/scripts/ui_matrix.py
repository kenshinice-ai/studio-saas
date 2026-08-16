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

The assertions encode the nav/brand contract from public-surface.js
fitNavigation(): labels are never clipped, the brand name only disappears
when a logo is there to replace it, and the page never scrolls horizontally.
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
