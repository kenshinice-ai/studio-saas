"""Guard the release ledger and Brand source-of-truth decisions.

Version labels, packages, production and Brand documents drift independently.
These checks keep the repository's declared contract explicit without
pretending a source change has already been packaged or deployed.
"""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VERSION = (REPOSITORY_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_readme_separates_source_package_and_production() -> None:
    """A single 'current release' sentence must not collapse three states."""

    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    assert "Current production release:" not in readme
    for layer in ("Source", "Package", "Production"):
        assert f"| {layer} |" in readme
    assert f"`VERSION` = **{VERSION}**" in readme
    assert "/v1/health?deep=1" in readme
    assert "infer Production from `VERSION`" in readme
    assert "which is ahead of `main`" in readme
    assert "does not identify the deployed commit" in readme


def test_brand_compatibility_copy_matches_the_canonical_document() -> None:
    """The conventional path is a copy, never an independent Brand authority."""

    canonical = (REPOSITORY_ROOT / "docs/design/Brand_Identity.md").read_bytes()
    compatibility = (REPOSITORY_ROOT / "docs/brand-guidelines.md").read_bytes()
    assert compatibility == canonical


def test_brand_contract_keeps_the_approved_identity_constraints() -> None:
    """Protect the small set of Brand values with product-wide consequences."""

    brand = (REPOSITORY_ROOT / "docs/design/Brand_Identity.md").read_text(
        encoding="utf-8"
    )
    for marker in (
        "#0E1729",
        "#16233D",
        "#F5B335",
        "136 : 84 : 52",
        '"PingFang SC"',
        "Family Amber is an identity colour, not a general warning colour.",
        "docs/design/Brand_Identity.md` remains canonical",
    ):
        assert marker in brand


def test_brand_prompt_injection_defaults_to_the_canonical_document() -> None:
    """Compatibility tooling must read the authority, not a possibly stale copy."""

    script = (
        REPOSITORY_ROOT / ".agents/skills/brand/scripts/inject-brand-context.cjs"
    ).read_text(encoding="utf-8")
    assert 'DEFAULT_GUIDELINES_PATH = "docs/design/Brand_Identity.md"' in script
