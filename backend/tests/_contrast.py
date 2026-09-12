"""One implementation of the WCAG contrast ratio, and one of `var()` resolution.

Six copies of `_luminance`/`contrast` had accumulated across the suite — one of
them using 0.04045 where the others use 0.03928, one rounding and the rest not.
Six copies is how a repository ends up with two answers to "is this legible".

The `var()` resolver exists because the interesting failures are never in a
token definition; they are in a *pair*. `--accent: var(--pwe-family-amber-text)`
is the correct swap for the light theme and reads as a passing assertion, but
the same token is also the **background** of the manual's numbered bullets,
where navy sits on top of it at 3.64:1. A test that string-matches the
definition cannot see that. A test that resolves both sides and divides can.
"""

from __future__ import annotations

import re

__all__ = ["contrast", "luminance", "resolve_var", "composite", "parse_colour",
           "at_rule_block"]


def _channels(value: str) -> tuple[float, float, float]:
    """Accept #rgb, #rrggbb, #rrggbbaa (alpha ignored) and rgb()/rgba()."""

    value = value.strip()
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        if len(digits) == 8:
            digits = digits[:6]
        if len(digits) != 6:
            raise ValueError(f"not a hex colour: {value!r}")
        return tuple(int(digits[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    match = re.match(r"rgba?\(([^)]*)\)", value)
    if not match:
        raise ValueError(f"not a colour this helper understands: {value!r}")
    parts = [p.strip() for p in re.split(r"[,/\s]+", match.group(1)) if p.strip()]
    return tuple(float(p.rstrip("%")) / (100 if p.endswith("%") else 255) for p in parts[:3])  # type: ignore[return-value]


def parse_colour(value: str) -> tuple[float, float, float, float]:
    """Return (r, g, b, alpha) with each channel in 0..1."""

    alpha = 1.0
    match = re.match(r"rgba?\(([^)]*)\)", value.strip())
    if match:
        parts = [p.strip() for p in re.split(r"[,/\s]+", match.group(1)) if p.strip()]
        if len(parts) >= 4:
            alpha = float(parts[3].rstrip("%")) / (100 if parts[3].endswith("%") else 1)
    elif value.strip().startswith("#") and len(value.strip()) == 9:
        alpha = int(value.strip()[7:9], 16) / 255
    red, green, blue = _channels(value)
    return red, green, blue, alpha


def composite(foreground: str, background: str) -> str:
    """Flatten a translucent colour onto an opaque one — `rgba(14,23,41,.34)`
    is not a colour until you say what is behind it, and every "border is
    3.9:1" comment in this repository that turned out to be wrong was written
    without doing this step."""

    f_r, f_g, f_b, alpha = parse_colour(foreground)
    b_r, b_g, b_b, _ = parse_colour(background)
    out = [f * alpha + b * (1 - alpha) for f, b in ((f_r, b_r), (f_g, b_g), (f_b, b_b))]
    return "#" + "".join(f"{round(c * 255):02x}" for c in out)


def luminance(value: str) -> float:
    channels = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        for c in _channels(value)
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(foreground: str, background: str) -> float:
    """WCAG 2.x ratio, rounded to two places. Translucent foregrounds are
    composited onto the background first."""

    if parse_colour(foreground)[3] < 1:
        foreground = composite(foreground, background)
    first, second = luminance(foreground), luminance(background)
    return round((max(first, second) + 0.05) / (min(first, second) + 0.05), 2)


_DECL = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;{}]+);")


def at_rule_block(css: str, prelude: str) -> str:
    """The balanced body of the at-rule whose prelude starts with `prelude`."""

    start = css.index(prelude)
    opening = css.index("{", start)
    depth = 0
    for position in range(opening, len(css)):
        depth += {"{": 1, "}": -1}.get(css[position], 0)
        if depth == 0:
            return css[opening + 1:position]
    raise ValueError(f"unbalanced at-rule: {prelude!r}")


def _declarations(css: str) -> dict[str, str]:
    return {name: value.strip() for name, value in _DECL.findall(css)}


def resolve_var(expression: str, *sources: str) -> str:
    """Follow `var(--a, fallback)` chains until a literal colour falls out.

    **The first source wins.** Callers pass the narrowest scope first — the
    light-theme block, then the base `:root`, then the shared token file — so
    that asking what `--accent` means under `prefers-color-scheme: light` does
    not accidentally pick up the value the print block sets 200 lines later.
    Merging the other way round is the bug this signature exists to prevent;
    it silently answers every question with the last theme in the file.
    """

    table: dict[str, str] = {}
    for source in reversed(sources):
        table.update(_declarations(source))
    seen: set[str] = set()
    value = expression.strip()
    while value.startswith("var("):
        inner = value[4:value.rindex(")")]
        name, _, fallback = inner.partition(",")
        name = name.strip()
        if name in seen:
            raise ValueError(f"var() cycle at {name}")
        seen.add(name)
        if name in table:
            value = table[name].strip()
        elif fallback.strip():
            value = fallback.strip()
        else:
            raise KeyError(f"{name} is not defined in any of the given stylesheets")
    return value
