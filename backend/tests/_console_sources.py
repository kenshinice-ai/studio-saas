"""Console page source for static tests, after the v10.11.0 externalisation.

The two consoles' JS moved verbatim from inline <script> blocks to
/assets/studio-admin.js and /assets/super-admin.js. A static test that asserts
"the page contains X" means the page as the browser experiences it — markup
plus its script — so this helper returns exactly that concatenation. Tests
that parse HTML structure (i18n coverage's ConsoleCopy) keep reading the bare
file on purpose: for them, script is noise.
"""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_PAGE_ASSET = {
    "studio-admin.html": REPOSITORY_ROOT / "backend/frontend/assets/studio-admin.js",
    "super-admin.html": REPOSITORY_ROOT / "backend/frontend/assets/super-admin.js",
}


def console_page_source(path) -> str:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    asset = _PAGE_ASSET.get(path.name)
    if asset is not None:
        text += "\n" + asset.read_text(encoding="utf-8")
    return text
