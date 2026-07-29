"""Regression checks for the PWE Studio product-home brand contract."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_HOME = REPOSITORY_ROOT / "product-home.html"


def _product_home_source() -> str:
    """Return the product-home source and fail clearly if it is unavailable."""

    return PRODUCT_HOME.read_text(encoding="utf-8")


def test_product_home_uses_the_canonical_pwe_palette() -> None:
    """Keep the marketing gateway on the generated PWE family palette."""

    source = _product_home_source().lower()
    required_colours = {
        "#0e1729",
        "#16233d",
        "#22355a",
        "#f5b335",
        "#a16207",
        "#f7f5f2",
    }
    retired_colours = {
        "#15312e",
        "#49635f",
        "#173f3a",
        "#0e2b28",
        "#dce9df",
        "#f7f3eb",
        "#fffdf8",
        "#d7a93d",
        "#c9684b",
    }

    for colour in required_colours:
        assert colour in source
    for colour in retired_colours:
        assert colour not in source
    assert '<meta name="theme-color" content="#0e1729">' in source


def test_product_home_uses_the_approved_sales_story() -> None:
    """Anchor the gateway copy to the current sales narrative and boundaries."""

    source = _product_home_source()

    assert "Put administration behind the scenes. Keep creativity in front." in source
    assert "Backed by Let’s Paint Studio" in source
    assert "Studio at AUD 99/month is the recommended plan." in source
    assert "One-time setup is quoted at AUD 299–999" in source
    assert "PWE Studio does not silently transmit or store the form." in source
    assert "PWE Studio · v8.0.1" in source
    assert "/customer-resources/Release_Notes_v8.0.1.html" in source
