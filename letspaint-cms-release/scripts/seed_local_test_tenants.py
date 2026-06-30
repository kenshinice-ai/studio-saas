#!/usr/bin/env python3
"""Seed local StudioSaaS test tenants.

Creates two tenants from the legacy sample fixture:

- `lets-paint-studio` -> Let's Paint Studio
- `lets-play-piano` -> Let's Play Piano
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "scripts" / "import_lets_paint_json.py"
SAMPLE = ROOT / "testdata" / "legacy_database_sample.json"


def run_import(slug: str, name: str) -> None:
    """Run the legacy importer for one local tenant."""

    subprocess.run(
        [sys.executable, str(IMPORTER), str(SAMPLE), slug, name],
        check=True,
        cwd=ROOT,
    )


def main() -> int:
    """Seed all local test tenants."""

    run_import("lets-paint-studio", "Let's Paint Studio")
    run_import("lets-play-piano", "Let's Play Piano")
    print("Seeded local tenants: lets-paint-studio, lets-play-piano")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
