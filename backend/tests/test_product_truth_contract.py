"""Keep deferred provider work from becoming a customer-facing promise."""

from __future__ import annotations

from pathlib import Path

from studiosaas.services import xero


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CUSTOMER_VISIBLE_ROOTS = (
    PROJECT_ROOT / "legacy-root/src",
    PROJECT_ROOT / "backend/frontend/assets",
    PROJECT_ROOT / "docs/customer",
    PROJECT_ROOT / "customer-resources",
)

# Keep this list deliberately small. It protects explicit promises, not every
# mention of Xero in engineering notes or a future-facing explanation.
BANNED_LIVE_CLAIMS = (
    "xero 直连",
    "自动推送到 xero",
    "不用再录第二遍",
    "开启生产推送",
    "connected directly",
    "automatically pushed",
    "no duplicate entry",
    "typed twice",
    "one-way push",
)


def _customer_visible_text() -> str:
    parts: list[str] = []
    for root in CUSTOMER_VISIBLE_ROOTS:
        if root.is_file():
            parts.append(root.read_text(encoding="utf-8"))
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".jsx", ".js", ".html", ".md"}:
                parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def test_deferred_xero_has_no_explicit_live_claim_in_customer_surfaces():
    if xero.TRANSPORT_AVAILABLE:
        return
    visible = _customer_visible_text()
    for phrase in BANNED_LIVE_CLAIMS:
        assert phrase not in visible, f"deferred Xero claim leaked into customer surface: {phrase}"


def test_xero_status_contract_exposes_live_transport_fields():
    api_source = (PROJECT_ROOT / "backend/studiosaas/api_v1.py").read_text(encoding="utf-8")
    # X3: the transport exists, and the API must keep saying so explicitly —
    # the stage and the switch stay separate facts the UI renders honestly.
    assert xero.TRANSPORT_AVAILABLE is True
    assert xero.INTEGRATION_STAGE == "live"
    assert '"integrationStage": _xero.INTEGRATION_STAGE' in api_source
    assert '"transportAvailable": status.transport_available' in api_source


def test_customer_docs_describe_xero_as_gated_one_way_push():
    faq = (PROJECT_ROOT / "docs/customer/FAQ.md").read_text(encoding="utf-8").lower()
    runbook = (PROJECT_ROOT / "docs/customer/Demo_Runbook.md").read_text(encoding="utf-8").lower()
    # The honest claims after X3: pushing exists, is one-way, and is OFF
    # until the studio itself walks the gate. Nothing about reading back.
    assert "one-way push" in faq and "no data is sent to xero" in faq
    assert "demo company" in runbook and "no data is sent to xero" in runbook
