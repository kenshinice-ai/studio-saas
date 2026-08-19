#!/usr/bin/env python3
"""Fail on duplicate keys in the i18n dictionaries.

`Object.fromEntries` keeps the LAST pair for a repeated key, silently. Both
dictionaries have shipped that defect: the CMS once rendered 已作废 as the
action word "Void" (10 duplicate keys), and the consoles once translated the
palette role "Support" with the help-desk word (13). The fix was manual both
times; this check makes the third time a red gate instead of a bug report.

Scans every `['key', …]` / `["key", …]` pair opener. Rule arrays start with a
regex literal, so they never match.
"""
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICTIONARIES = (
    ROOT / "backend/frontend/assets/cms-i18n.js",
    ROOT / "backend/frontend/assets/admin-i18n.js",
)

PAIR_KEY = re.compile(r"""\[\s*(?:'((?:[^'\\]|\\.)+)'|"((?:[^"\\]|\\.)+)")\s*,""")

failures = 0
for path in DICTIONARIES:
    text = path.read_text(encoding="utf-8")
    keys = Counter(m.group(1) or m.group(2) for m in PAIR_KEY.finditer(text))
    duplicates = {k: n for k, n in keys.items() if n > 1}
    if duplicates:
        failures += len(duplicates)
        print(f"{path.name}: {len(duplicates)} duplicate dictionary key(s):")
        for key, n in sorted(duplicates.items()):
            print(f"  {n}x  {key}")
    else:
        print(f"{path.name}: {sum(keys.values())} pairs, no duplicates")

sys.exit(1 if failures else 0)
