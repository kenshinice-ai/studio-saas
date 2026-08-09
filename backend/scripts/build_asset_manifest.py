#!/usr/bin/env python3
"""Build or verify the SHA-256 manifest for shared frontend assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "assets"
MANIFEST_PATH = ASSET_ROOT / "asset-manifest.json"


def manifest_payload() -> dict[str, object]:
    """Return a deterministic inventory excluding the manifest itself."""

    assets = {
        path.relative_to(ASSET_ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(ASSET_ROOT.rglob("*"))
        if path.is_file() and path != MANIFEST_PATH
    }
    if not assets:
        raise RuntimeError(f"No frontend assets found under {ASSET_ROOT}")
    return {"schema": 1, "algorithm": "sha256", "assets": assets}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the committed manifest is stale.")
    args = parser.parse_args()
    expected = json.dumps(manifest_payload(), indent=2, sort_keys=True) + "\n"
    if args.check:
        actual = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.is_file() else ""
        if actual != expected:
            print("ERROR: frontend asset manifest is missing or stale.")
            return 1
        print(f"verified {MANIFEST_PATH.relative_to(ASSET_ROOT.parent.parent)}")
        return 0
    MANIFEST_PATH.write_text(expected, encoding="utf-8")
    print(f"built {MANIFEST_PATH.relative_to(ASSET_ROOT.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
