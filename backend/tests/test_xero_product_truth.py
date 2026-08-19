"""The CMS must describe Xero's current preview boundary, not the roadmap."""

from pathlib import Path
import json

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PANEL = PROJECT_ROOT / "legacy-root" / "src" / "panels" / "integrations.jsx"
I18N = PROJECT_ROOT / "backend/frontend/assets/cms-i18n.js"


def test_xero_panel_is_explicit_preview_and_transport_gates_mutations():
    panel = PANEL.read_text(encoding="utf-8")

    assert "Xero 预接入（Preview）" in panel
    assert "state.transportAvailable === true" in panel
    assert "const preview = !transportAvailable" in panel
    assert "不会向 Xero 发送任何数据" in panel
    assert "canManage && !preview" in panel
    assert "{preview ?" in panel

    # These were the v10.6.3 customer-facing claims that made a queue and a
    # schema look like a live provider connection.
    assert "自动推送到 Xero，不用再录第二遍" not in panel
    assert "自动推送" not in panel
    assert "不用再录第二遍" not in panel
    assert "Xero 直连" not in panel


def test_xero_preview_copy_has_english_dictionary_entries():
    panel = PANEL.read_text(encoding="utf-8")
    i18n = I18N.read_text(encoding="utf-8")
    expected = {
        "Xero 预接入（Preview）",
        "预览状态 · 不发送数据",
        "Xero 预接入说明",
        "当前版本尚未开放生产推送",
        "Xero transport 尚未上线；不会向 Xero 发送任何数据。",
    }
    for phrase in expected:
        assert phrase in panel, phrase
        assert f"['{phrase}'" in i18n, phrase


def test_xero_preview_mapper_uses_document_dto_and_preserves_original_tax_rate():
    from studiosaas.services import xero

    document = {
        "document": {
            "id": "invoice-1", "kind": "invoice", "number": "INV-0001",
            "status": "issued", "currency": "AUD",
        },
        "recipient": {"displayName": "Snapshot Payer", "email": "payer@example.test"},
        "supplier": {"legalName": "Studio Pty Ltd"},
        "lines": [{
            "description": "GST line", "quantity": "1.00", "unitPriceCents": 10000,
            "taxRateBp": 875, "netCents": 10000, "taxCents": 875, "totalCents": 10875,
            "sourceKind": "tuition",
        }],
        "totals": {"subtotalCents": 10000, "taxCents": 875, "totalCents": 10875},
        "paymentSummary": {"amountPaidCents": 0, "amountCreditedCents": 0, "balanceCents": 10875},
    }
    prepared = xero.prepare_document_export(document)
    assert prepared["stage"] == "preview"
    assert prepared["transportAvailable"] is False
    assert prepared["object"]["kind"] == "invoice"
    assert prepared["object"]["number"] == "INV-0001"
    assert prepared["object"]["revision"]
    assert len(prepared["object"]["hash"]) == 64
    assert prepared["lines"][0]["taxRateBp"] == 875
    assert prepared["lines"][0]["taxRate"] == "8.75%"
    assert "Snapshot Payer" in json.dumps(prepared, ensure_ascii=False)


def test_xero_preview_mapper_rejects_live_record_reconstruction_and_no_transport():
    from studiosaas.services import xero

    with pytest.raises(xero.XeroError, match="InvoiceDocument DTO"):
        xero.prepare_document_export({"id": "live-invoice", "account_name": "Live payer"})
    # X3: the transport is real now; the mapper's refusal to reconstruct a
    # live record is unchanged — pushes read the issued DTO, never raw rows.
    assert xero.TRANSPORT_AVAILABLE is True
