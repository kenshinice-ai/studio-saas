"""Progressive-enhancement contract for the Living Studio System homepage."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOME = (ROOT / "product-home.html").read_text(encoding="utf-8")
LOADER_PATH = ROOT / "backend/frontend/assets/product-spatial.js"
THREE_SOURCE_PATH = ROOT / "backend/frontend/src/product-spatial-three.js"
THREE_BUNDLE_PATH = ROOT / "backend/frontend/assets/product-spatial-three.js"
POSTER_PATH = ROOT / "backend/frontend/assets/living-studio-system-poster.webp"
LIGHT_POSTER_PATH = ROOT / "backend/frontend/assets/living-studio-system-poster-light.webp"
CSS_PATH = ROOT / "backend/frontend/assets/product-home.css"
MANIFEST_PATH = ROOT / "backend/frontend/assets/asset-manifest.json"


def test_the_story_has_one_core_and_exactly_four_semantic_surfaces() -> None:
    assert "One system · Four connected surfaces" in HOME
    assert "一个系统 · 四个相连界面" in HOME
    assert HOME.count('class="surface-chapter"') == 4
    assert sorted(re.findall(r'data-system-chapter="([0-3])"', HOME)) == ["0", "1", "2", "3"]
    for anchor in ("surface-portal", "surface-register", "surface-cms", "surface-admin"):
        assert f'id="{anchor}"' in HOME


def test_spatial_rendering_is_an_enhancement_not_the_content_layer() -> None:
    assert '<body class="product-home">' in HOME
    assert 'src="/assets/product-spatial.js?v=__APP_VERSION__"' in HOME
    assert 'data-three-module="/assets/product-spatial-three.js?v=__APP_VERSION__"' in HOME
    assert 'id="livingSystemCanvas" aria-hidden="true"' in HOME
    assert 'id="livingSystemThree" aria-hidden="true"' in HOME
    assert HOME.count('src="/assets/living-studio-system-poster.webp?v=__APP_VERSION__"') == 2
    assert HOME.count('srcset="/assets/living-studio-system-poster-light.webp?v=__APP_VERSION__"') == 2
    # Product links are ordinary anchors outside Canvas. No renderer owns a
    # navigation or form contract.
    for destination in (
        "/lets-paint-showcase",
        "/lets-paint-showcase/register",
        "/lets-paint-showcase/cms",
        "/lets-paint-showcase/studio-admin",
    ):
        assert f'href="{destination}"' in HOME


def test_the_loader_gates_three_on_motion_data_device_and_webgl2() -> None:
    source = LOADER_PATH.read_text(encoding="utf-8")
    for contract in (
        "prefers-reduced-motion: reduce",
        "motionQuery.addEventListener('change'",
        "connection.saveData",
        "min-width: 900px",
        "window.innerWidth >= 900",
        "desktopQuery.addEventListener('change'",
        "prefers-color-scheme: light",
        "getContext('webgl2'",
        "failIfMajorPerformanceCaveat: true",
        "await import(moduleUrl)",
        "WEBGL_lose_context",
    ):
        assert contract in source, f"the progressive gate lost {contract}"
    assert "https://" not in source and "http://" not in source


def test_the_three_scene_caps_pixel_density_and_pauses_offscreen() -> None:
    source = THREE_SOURCE_PATH.read_text(encoding="utf-8")
    assert "Math.min(window.devicePixelRatio || 1, 2)" in source
    assert "new ResizeObserver" in source
    assert "new IntersectionObserver" in source
    assert "renderer.setAnimationLoop" in source
    assert "webglcontextlost" in source
    assert "powerPreference: 'high-performance'" in source
    assert "PALETTES" in source and "theme === 'light'" in source
    assert "MeshPhysicalMaterial" in source and "transmission" in source
    assert "TextureLoader" in source and "shadowMap.enabled = true" in source


def test_the_optional_bundle_and_poster_stay_inside_the_page_budget() -> None:
    # Three is downloaded only on the capable path; compressed size is the
    # network cost the product budget names, not the source map or npm package.
    assert len(gzip.compress(THREE_BUNDLE_PATH.read_bytes(), compresslevel=9)) <= 300_000
    assert POSTER_PATH.stat().st_size <= 350_000
    assert LIGHT_POSTER_PATH.stat().st_size <= 350_000


def test_three_and_esbuild_are_release_pinned() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["devDependencies"]["esbuild"] == "0.25.12"
    assert package["devDependencies"]["three"] == "0.185.1"
    build = (ROOT / "backend/scripts/build_product_spatial.sh").read_text(encoding="utf-8")
    assert 'PINNED_ESBUILD="0.25.12"' in build
    assert 'PINNED_THREE="0.185.1"' in build
    assert "--bundle" in build and "--format=esm" in build and "--minify" in build


def test_every_new_runtime_asset_is_hash_manifested() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["assets"]
    for relative in (
        "living-studio-system-poster.webp",
        "living-studio-system-poster-light.webp",
        "product-home.css",
        "product-spatial.js",
        "product-spatial-three.js",
    ):
        path = ROOT / "backend/frontend/assets" / relative
        assert relative in manifest
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[relative]


def test_the_server_stamps_and_serves_the_spatial_assets(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "__APP_VERSION__" not in body
    for relative, content_type in (
        ("product-home.css", "text/css"),
        ("product-spatial.js", "text/javascript"),
        ("product-spatial-three.js", "text/javascript"),
        ("living-studio-system-poster.webp", "image/webp"),
        ("living-studio-system-poster-light.webp", "image/webp"),
    ):
        match = re.search(rf'/assets/{re.escape(relative)}\?v=[^"\s]+', body)
        assert match, f"the home page did not stamp {relative}"
        asset = client.get(match.group(0))
        assert asset.status_code == 200
        assert asset.headers["Content-Type"].startswith(content_type)
        assert asset.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_responsive_and_reduced_motion_states_are_explicit() -> None:
    source = CSS_PATH.read_text(encoding="utf-8")
    for query in (
        "@media (max-width: 1180px)",
        "@media (max-width: 980px)",
        "@media (max-width: 880px)",
        "@media (max-width: 760px)",
        "@media (max-width: 560px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert query in source
    assert ".system-story-grid" in source
    assert ".system-stage-controls" in source
