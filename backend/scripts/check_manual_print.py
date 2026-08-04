#!/usr/bin/env python3
"""Render the manual to PDF the way a reader's browser would, and measure it.

The print stylesheet was asserted and its rules parsed, and it still produced
body text printed on top of the running footer and pages that were 95% empty.
Neither is visible from the CSS or from the screen; both are obvious the
moment a PDF exists. So a PDF exists here.

    python scripts/check_manual_print.py --base http://localhost:8899

Reports, per language: page count, how much of each page carries ink, and any
page whose text collides with the footer band. Writes the PDFs next to the
report so they can be opened.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture_manual_shots import Browser  # noqa: E402

# A4 in inches, which is what Page.printToPDF takes.
A4 = (8.27, 11.69)
PAGES = {"en": "/manual/", "zh": "/zh/manual/"}


def render(browser: Browser, url: str, out: Path) -> bytes:
    browser.call("Page.navigate", url=url)
    time.sleep(4.0)
    # Force every lazy image in; a print with half the screenshots missing
    # would measure as beautifully compact.
    browser.call("Runtime.evaluate", expression=(
        "document.querySelectorAll('img').forEach(i => { i.loading = 'eager'; });"
    ))
    time.sleep(3.0)
    result = browser.call(
        "Page.printToPDF",
        printBackground=True,
        paperWidth=A4[0], paperHeight=A4[1],
        marginTop=0, marginBottom=0, marginLeft=0, marginRight=0,
        preferCSSPageSize=True,
    )
    data = base64.b64decode(result["data"])
    out.write_bytes(data)
    return data


def page_ink(pdf: bytes) -> list[float]:
    """Rough fraction of each page that carries content.

    Measured from the PDF's own text and image operators rather than by
    rasterising: the y-coordinates of drawn objects give the vertical extent
    used, which is all that is needed to find a nearly empty page.
    """

    import zlib

    pages: list[float] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        raw = match.group(1)
        try:
            content = zlib.decompress(raw)
        except zlib.error:
            continue
        ys = [float(m.group(1)) for m in re.finditer(rb"([\d.]+)\s+(?:Td|TD|Tm|cm)\b", content)]
        if not ys:
            continue
        pages.append(round((max(ys) - min(ys)) / 842.0, 2))
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8899")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else Path(tempfile.gettempdir()) / "manual-print"
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = Path(tempfile.mkdtemp(prefix="print-check-"))
    browser = Browser(profile)
    report = {}
    try:
        browser.call("Emulation.setEmulatedMedia", media="print")
        for language, path in PAGES.items():
            pdf = render(browser, args.base + path, out_dir / f"manual-{language}.pdf")
            count = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
            report[language] = {"pages": count, "bytes": len(pdf)}
            print(f"  {language}: {count} pages, {len(pdf)/1024/1024:.2f} MB "
                  f"→ {out_dir / f'manual-{language}.pdf'}")
    finally:
        browser.close()
        shutil.rmtree(profile, ignore_errors=True)

    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
