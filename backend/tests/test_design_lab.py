"""The design lab and the design spec are generated, and stay generated.

`docs/design/theme-proposal.html` is why this file exists. It is 1009 lines of
hand-written design reference showing eight themes in light and dark, and since
v8.3.0 the dark half of it has been wrong — it still shows the inverted
surfaces that release replaced. Nothing failed. A design reference nobody
regenerates becomes a picture of a product that used to exist, and it is most
convincing exactly when it is most out of date.

So both artefacts are regenerated here and compared byte for byte, and the
JavaScript solver the lab uses to re-solve while a slider moves is compared
token for token against the Python it was ported from.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DESIGN = REPOSITORY_ROOT / "docs" / "design"
LAB = DESIGN / "lab.html"
SPEC = DESIGN / "Design_System.md"
SOLVER = DESIGN / "solver.js"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, DESIGN / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


palette_gen = _load("palette_gen")


# ── the artefacts are what the generator produces ───────────────────────────

def test_the_lab_is_not_stale() -> None:
    build_lab = _load("build_lab")
    assert LAB.read_text(encoding="utf-8") == build_lab.render(), (
        "docs/design/lab.html differs from build_lab.py — run "
        "`python3 docs/design/build_lab.py`"
    )


def test_the_spec_is_not_stale() -> None:
    build_spec = _load("build_spec")
    assert SPEC.read_text(encoding="utf-8") == build_spec.render(), (
        "docs/design/Design_System.md differs from build_spec.py — run "
        "`python3 docs/design/build_spec.py`"
    )


def test_the_lab_carries_every_theme_mode_and_every_component() -> None:
    build_lab = _load("build_lab")
    rows = build_lab.theme_rows()
    expected = sum(len(t.get("modes", palette_gen.MODES_DEFAULT)) for t in palette_gen.THEMES)
    assert len(rows) == expected
    # The console must be present but marked, so nobody reads the lab as a
    # menu of themes a studio can pick.
    assert rows["platform-console:light"]["internal"] is True
    assert all(not row["internal"] for key, row in rows.items()
               if not key.startswith("platform-console"))
    assert sum(len(items) for _, items in build_lab.COMPONENTS) >= 40


def test_the_lab_asserts_the_same_pairs_the_build_does() -> None:
    """A lab with a softer standard than the build is a lab that lies."""

    build_lab = _load("build_lab")
    assert [tuple(p) for p in build_lab.LAB_PAIRS] == [tuple(c) for c in palette_gen.CHECKS]


def test_the_lab_never_offers_a_mode_a_theme_does_not_ship() -> None:
    """The first cut reported `arcade-lime:light — all clear` while showing
    its dark palette, because the lookup fell back to the only mode it had."""

    source = LAB.read_text(encoding="utf-8")
    assert "function syncModeButtons()" in source
    assert "button.disabled = !offered" in source


def test_the_lab_tunes_inputs_and_never_hexes() -> None:
    """The sliders exist to move hue and saturation. A lab that let you nudge a
    hex is a fifth hand-built palette inside a week — which is what
    theme-proposal.html became."""

    build_lab = _load("build_lab")
    source = LAB.read_text(encoding="utf-8")
    for field in ("hue", "sat", "sec_off", "sec_sat", "ink_hue", "accent_hue"):
        assert f"['{field}'," in source, f"no slider for {field}"
    # Nothing in the spec payload may be an output colour.
    for spec in build_lab.spec_inputs():
        for key, value in spec.items():
            if key == "anchors":
                continue
            assert not (isinstance(value, str) and value.startswith("#")), (
                f"{spec['key']}.{key} is a hex — sliders must move inputs"
            )


# ── the two solvers agree ───────────────────────────────────────────────────

NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed; the JS solver cannot be checked")
def test_the_javascript_solver_matches_the_python(tmp_path: Path) -> None:
    """Two implementations of one algorithm, held together by measurement.

    The lab re-solves in JavaScript so a slider can move at 60fps. That is a
    drift risk, and this is the same answer used for presets.py: compare every
    token of every theme-mode, and a divergence in the fortieth binary-search
    step is a test failure rather than a surprise six months on.

    It has already earned its keep: the first run disagreed on one token, and
    the JS was right — `disabled_text_color` was reading the paper hue in
    Python while every other text token read the ink family, which was
    invisible until a theme split the two.
    """

    specs = tmp_path / "specs.json"
    expected = tmp_path / "expected.json"
    specs.write_text(json.dumps([dict(t) for t in palette_gen.THEMES]), encoding="utf-8")
    expected.write_text(json.dumps({
        f"{t['key']}:{mode}": palette_gen.build(t, mode == "dark")
        for t in palette_gen.THEMES
        for mode in t.get("modes", palette_gen.MODES_DEFAULT)
    }), encoding="utf-8")

    script = f"""
      const {{ build }} = require({str(SOLVER)!r});
      const specs = require({str(specs)!r});
      const py = require({str(expected)!r});
      let drift = [], checked = 0;
      for (const t of specs) {{
        for (const mode of (t.modes || ['light', 'dark'])) {{
          const js = build(t, mode === 'dark');
          for (const [k, v] of Object.entries(py[t.key + ':' + mode])) {{
            checked++;
            if (js[k] !== v) drift.push(`${{t.key}}:${{mode}} ${{k}} js=${{js[k]}} py=${{v}}`);
          }}
        }}
      }}
      console.log(JSON.stringify({{ checked, drift }}));
    """
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report["checked"] > 600, "the parity check compared almost nothing"
    assert not report["drift"], "\n".join(report["drift"][:10])


@pytest.mark.skipif(NODE is None, reason="node is not installed; the JS solver cannot be checked")
def test_the_solvers_agree_on_inputs_no_theme_uses(tmp_path: Path) -> None:
    """A grid of synthetic hues and saturations.

    Comparing only the shipped themes checks the nine points the two
    implementations happen to have been written against. The lab's sliders
    reach everywhere in between, and that is exactly where a transliteration
    error hides — Python's round() is banker's rounding and JavaScript's is
    round-half-up, so the two disagree only when a channel lands on .5.
    """

    grid = [dict(key=f"g{i}", label="grid", hue=hue, sat=sat, sec_off=150, sec_sat=0.3,
                 harmony="grid", modes=["light", "dark"])
            for i, (hue, sat) in enumerate(
                [(h, s) for h in range(0, 360, 40) for s in (0.08, 0.3, 0.55, 0.75)])]
    specs = tmp_path / "grid.json"
    expected = tmp_path / "grid-expected.json"
    specs.write_text(json.dumps(grid), encoding="utf-8")
    expected.write_text(json.dumps({
        f"{t['key']}:{mode}": palette_gen.build(t, mode == "dark")
        for t in grid for mode in ("light", "dark")
    }), encoding="utf-8")

    script = f"""
      const {{ build }} = require({str(SOLVER)!r});
      const specs = require({str(specs)!r});
      const py = require({str(expected)!r});
      let drift = [], checked = 0;
      for (const t of specs) for (const mode of ['light', 'dark']) {{
        const js = build(t, mode === 'dark');
        for (const [k, v] of Object.entries(py[t.key + ':' + mode])) {{
          checked++;
          if (js[k] !== v) drift.push(`hue=${{t.hue}} sat=${{t.sat}} ${{mode}} ${{k}} js=${{js[k]}} py=${{v}}`);
        }}
      }}
      console.log(JSON.stringify({{ checked, drift }}));
    """
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report["checked"] > 2000
    assert not report["drift"], "\n".join(report["drift"][:10])


def test_the_stale_hand_written_proposal_is_labelled_as_such() -> None:
    """theme-proposal.html predates v8.3.0 and shows the inverted dark
    surfaces that release replaced. It is kept as a record of what was
    proposed, and it has to say so, or it reads as current."""

    proposal = DESIGN / "theme-proposal.html"
    if not proposal.exists():
        pytest.skip("the proposal has been removed")
    head = proposal.read_text(encoding="utf-8")[:2000]
    assert "SUPERSEDED" in head, (
        "theme-proposal.html shows pre-v8.3.0 dark surfaces and does not say so"
    )
