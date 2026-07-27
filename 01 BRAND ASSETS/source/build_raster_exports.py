#!/usr/bin/env python3
"""Build exact-size Paradise Production raster exports from official artwork.

The supplied PNG filenames predate this repository and are 1024×1024 even
when their names contain ``512``. They remain untouched as delivery originals.
This script creates a normalized web/PWA set with dimensions encoded truthfully
in each filename. It fails loudly if an expected source is missing or changes
shape, avoiding a silent substitution of unrelated artwork.
"""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "logo" / "png"
OUTPUT = SOURCE / "web"

EXPORTS = {
    "app-icon-512.png": (
        ("app-icon-192.png", 192),
        ("app-icon-512.png", 512),
        ("apple-touch-icon-180.png", 180),
        ("favicon-64.png", 64),
    ),
    "app-icon-maskable-512.png": (
        ("app-icon-maskable-192.png", 192),
        ("app-icon-maskable-512.png", 512),
    ),
    "avatar-512.png": (
        ("avatar-256.png", 256),
        ("avatar-512.png", 512),
    ),
    "avatar-light-512.png": (
        ("avatar-light-256.png", 256),
        ("avatar-light-512.png", 512),
    ),
}


def main() -> None:
    """Create the normalized raster set and report every written file."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for source_name, targets in EXPORTS.items():
        source_path = SOURCE / source_name
        if not source_path.is_file():
            raise FileNotFoundError(f"Required official source is missing: {source_path}")

        with Image.open(source_path) as image:
            if image.width != image.height or image.width < 512:
                raise ValueError(
                    f"Expected a square source of at least 512px, got "
                    f"{image.width}x{image.height}: {source_path}"
                )
            for output_name, size in targets:
                output_path = OUTPUT / output_name
                image.resize((size, size), Image.Resampling.LANCZOS).save(
                    output_path,
                    optimize=True,
                )
                written.append(output_path)

    print(f"Wrote {len(written)} normalized Paradise raster exports:")
    for path in written:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
