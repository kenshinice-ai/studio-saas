#!/usr/bin/env python3
"""Validate the complete PWE Studio / Paradise Production delivery kit.

Use ``--write-manifest`` after intentional regeneration. Without the flag the
script validates the checked-in manifest as well as file presence, dimensions,
SVG safety boundaries and canonical family colours.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
MANIFEST = ROOT / "asset-manifest.json"
TOKENS = ROOT / "brand-tokens.json"
CANONICAL_COLORS = {
    "family_navy": "#0E1729",
    "family_amber": "#F5B335",
    "accessible_amber_text": "#A16207",
    "warm_paper": "#F7F5F2",
}

REQUIRED_FILES = (
    "README.md",
    "BRAND_ARCHITECTURE.md",
    "brand-tokens.json",
    "brand-identity.html",
    "logo/lockup-A-navy.svg",
    "logo/lockup-B-navy.svg",
    "logo/lockup-C-navy.svg",
    "logo/symbol-navy.svg",
    "logo/png/web/app-icon-192.png",
    "logo/png/web/app-icon-512.png",
    "logo/png/web/apple-touch-icon-180.png",
    "pwe-studio/svg/pwe-mark.svg",
    "pwe-studio/svg/pwe-logo.svg",
    "pwe-studio/png/pwe-logo-800.png",
    "pwe-studio/pwa/icon-192.png",
    "pwe-studio/pwa/icon-512.png",
    "pwe-studio/pwa/apple-touch-icon.png",
    "source/build_assets.py",
    "source/build_raster_exports.py",
    "source/validate_assets.py",
)

EXACT_RASTER_SIZES = {
    "logo/png/web/app-icon-192.png": (192, 192),
    "logo/png/web/app-icon-512.png": (512, 512),
    "logo/png/web/app-icon-maskable-192.png": (192, 192),
    "logo/png/web/app-icon-maskable-512.png": (512, 512),
    "logo/png/web/apple-touch-icon-180.png": (180, 180),
    "logo/png/web/favicon-64.png": (64, 64),
    "logo/png/web/avatar-256.png": (256, 256),
    "logo/png/web/avatar-512.png": (512, 512),
    "logo/png/web/avatar-light-256.png": (256, 256),
    "logo/png/web/avatar-light-512.png": (512, 512),
    "pwe-studio/png/pwe-logo-800.png": (800, 320),
    "pwe-studio/png/pwe-logo-on-navy-800.png": (800, 320),
    "pwe-studio/pwa/icon-192.png": (192, 192),
    "pwe-studio/pwa/icon-512.png": (512, 512),
    "pwe-studio/pwa/apple-touch-icon.png": (180, 180),
}

# Paradise lockups are the one documented editable-source exception. Runtime
# and PWE vector artwork must remain font-independent.
NO_LIVE_TEXT_GLOBS = (
    "pwe-studio/svg/*.svg",
    "pwe-studio/pwa/*.svg",
    "logo/symbol-*.svg",
    "logo/app-icon*.svg",
    "logo/avatar*.svg",
    "logo/favicon.svg",
)


def sha256(path: Path) -> str:
    """Return a lowercase SHA-256 digest for ``path``."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    """Build a deterministic manifest record for one delivery file."""
    relative = path.relative_to(ROOT).as_posix()
    record: dict[str, Any] = {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    if path.suffix.lower() == ".png":
        with Image.open(path) as image:
            record["dimensions"] = [image.width, image.height]
    return record


def build_manifest() -> dict[str, Any]:
    """Return the deterministic manifest payload."""
    files = [
        path
        for path in sorted(ROOT.rglob("*"))
        if path.is_file()
        and path != MANIFEST
        and "__pycache__" not in path.parts
        and path.suffix.lower() != ".pyc"
    ]
    return {
        "schema_version": 1,
        "family": "PWE Studio / Paradise Production",
        "files": [file_record(path) for path in files],
    }


def validate() -> list[str]:
    """Return all validation failures without hiding later problems."""
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required asset: {relative}")

    try:
        tokens = json.loads(TOKENS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read brand tokens: {exc}")
    else:
        colors = tokens.get("colors", {})
        for key, expected in CANONICAL_COLORS.items():
            actual = colors.get(key)
            if actual != expected:
                errors.append(f"token {key}: expected {expected}, got {actual!r}")

    for relative, expected in EXACT_RASTER_SIZES.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing dimension-controlled export: {relative}")
            continue
        try:
            with Image.open(path) as image:
                actual = (image.width, image.height)
        except OSError as exc:
            errors.append(f"cannot open raster {relative}: {exc}")
            continue
        if actual != expected:
            errors.append(f"{relative}: expected {expected}, got {actual}")

    for pattern in NO_LIVE_TEXT_GLOBS:
        for path in ROOT.glob(pattern):
            content = path.read_text(encoding="utf-8").lower()
            if "<text" in content:
                errors.append(f"font-dependent live text is not allowed in {path.relative_to(ROOT)}")
            if "<svg" not in content or "viewbox=" not in content:
                errors.append(f"invalid SVG envelope: {path.relative_to(ROOT)}")

    for path in ROOT.glob("logo/lockup-*.svg"):
        if "<text" not in path.read_text(encoding="utf-8").lower():
            errors.append(
                f"editable Paradise lockup unexpectedly lost live text: {path.relative_to(ROOT)}"
            )

    if not MANIFEST.is_file():
        errors.append("asset-manifest.json is missing; run with --write-manifest")
    else:
        try:
            checked_in = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read asset manifest: {exc}")
        else:
            expected = build_manifest()
            if checked_in != expected:
                errors.append("asset-manifest.json is stale; run with --write-manifest")

    repo_license = REPO / "BRAND_ASSET_LICENSE.md"
    if not repo_license.is_file():
        errors.append("repository BRAND_ASSET_LICENSE.md is missing")

    return errors


def main() -> None:
    """Optionally refresh the manifest, then validate the complete kit."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="refresh asset-manifest.json before validation",
    )
    args = parser.parse_args()

    if args.write_manifest:
        MANIFEST.write_text(
            json.dumps(build_manifest(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    errors = validate()
    if errors:
        raise SystemExit("Brand asset validation failed:\n- " + "\n- ".join(errors))

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    print(
        f"Brand asset validation passed: {len(manifest['files'])} files, "
        f"{len(EXACT_RASTER_SIZES)} exact raster dimensions."
    )


if __name__ == "__main__":
    main()
