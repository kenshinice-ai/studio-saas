#!/usr/bin/env python3
"""Report every Chinese string still visible with the CMS set to English.

Untranslated UI has shipped from this repository four times, and the reason is
always the same: nothing fails. A missing dictionary entry renders the source
Chinese, the page works, the tests pass, and only a reader who does not speak
Chinese ever finds out. The manual's screenshot run is what finally surfaced
it — capturing every screen in English put the gaps on one contact sheet.

So the contact sheet is a command. It signs in, walks every tab, and lists the
text nodes that are still Chinese, with the tab each came from. Run it after
touching cms-app.jsx.

    python scripts/audit_cms_translation.py --base http://localhost:8899

Exits non-zero when anything is found, so it can gate a release.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture_manual_shots import (  # noqa: E402
    ROLE_EMAIL,
    SEED_LANGUAGE,
    SLUG,
    TAB,
    Browser,
    login,
    read_demo_password,
)

# Tab → the role that can see it. The audit is only meaningful for screens the
# account actually reaches; a tab that is absent is a permission boundary, not
# a translation gap.
SURFACES = [
    ("dashboard", None, "manager"),
    ("roster", TAB["roster"], "manager"),
    ("students", TAB["students"], "manager"),
    ("pending", TAB["pending"], "manager"),
    ("topup", TAB["topup"], "manager"),
    ("logs", TAB["logs"], "manager"),
    ("stats", TAB["stats"], "manager"),
]

COLLECT = """
(() => {
  const cjk = /[\\u4e00-\\u9fff]/;
  const found = new Map();
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walk.nextNode())) {
    const text = (node.nodeValue || '').replace(/\\s+/g, ' ').trim();
    if (text && cjk.test(text) && text.length < 80) {
      found.set(text, (found.get(text) || 0) + 1);
    }
  }
  // Attributes carry copy too — placeholders are the ones readers hit first.
  document.querySelectorAll('[placeholder], [title], [aria-label]').forEach((el) => {
    ['placeholder', 'title', 'aria-label'].forEach((name) => {
      const value = (el.getAttribute(name) || '').trim();
      if (value && cjk.test(value)) found.set(value, (found.get(value) || 0) + 1);
    });
  });
  return [...found.keys()];
})()
"""

# Deliberately Chinese: the language switch labels itself in both languages,
# because a reader who cannot read the current one still has to find it.
# Operating data — student names, course titles — is never translated either,
# but it does not appear here because it contains no Chinese in this tenant.
INTENTIONAL = {"中", "中文", "Language / 语言"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8899")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    password = read_demo_password()
    session = login(args.base, ROLE_EMAIL["manager"], password)

    profile = Path(tempfile.mkdtemp(prefix="i18n-audit-"))
    browser = Browser(profile)
    report: dict[str, list[str]] = {}
    try:
        browser.call("Emulation.setDeviceMetricsOverride",
                     width=1440, height=2400, deviceScaleFactor=1, mobile=False)
        browser.call("Network.enable")
        browser.call("Network.setCookie", name="session", value=session,
                     domain=args.base.split("//", 1)[1].split(":")[0], path="/")
        browser.call("Page.addScriptToEvaluateOnNewDocument",
                     source=SEED_LANGUAGE % ('"en"', '"en"'))
        for name, tab, _role in SURFACES:
            browser.call("Page.navigate", url=f"{args.base}/{SLUG}/cms")
            time.sleep(3.5)
            if tab:
                browser.call("Runtime.evaluate", returnByValue=True,
                             expression=_click(tab["en"]))
                time.sleep(2.0)
            found = browser.call("Runtime.evaluate", returnByValue=True,
                                 expression=COLLECT)["result"]["value"]
            report[name] = sorted(found)
    finally:
        browser.close()
        shutil.rmtree(profile, ignore_errors=True)

    unique = sorted({
        text for texts in report.values() for text in texts
        if text not in INTENTIONAL
    })
    if args.json:
        print(json.dumps({"byScreen": report, "unique": unique}, ensure_ascii=False, indent=1))
    else:
        for name, texts in report.items():
            print(f"\n{name}: {len(texts)}")
            for text in texts:
                print(f"    {text}")
        print(f"\n{len(unique)} distinct strings still Chinese in English mode"
              f"  ({len(INTENTIONAL)} intentional ones excluded)")
    return 1 if unique else 0


def _click(label: str) -> str:
    from capture_manual_shots import CLICK_TAB

    return CLICK_TAB % json.dumps(label)


if __name__ == "__main__":
    sys.exit(main())
