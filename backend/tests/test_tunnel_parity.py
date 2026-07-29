"""Contract tests for local/Cloudflare release parity verification."""

import pytest

from scripts.verify_tunnel_parity import verify_parity


def _health(**overrides):
    payload = {
        "ok": True,
        "db": "ok",
        "service": "PWE Studio SaaS API",
        "version": "v1",
        "appVersion": "8.0.1",
        "mode": "saas",
        "showProducerCredit": True,
    }
    payload.update(overrides)
    return payload


def test_tunnel_parity_accepts_one_deep_healthy_release() -> None:
    """Matching deep-health documents are a valid tunnel handoff."""

    verify_parity(_health(), _health(), expected_app_version="8.0.1", expected_mode="saas")


@pytest.mark.parametrize(
    ("public_override", "message"),
    [
        ({"appVersion": "7.9.9"}, "appVersion mismatch"),
        ({"db": "error"}, "did not confirm PostgreSQL"),
        ({"mode": "standalone"}, "mode mismatch"),
        ({"showProducerCredit": False}, "not the same release"),
    ],
)
def test_tunnel_parity_rejects_stale_or_inconsistent_public_state(public_override, message) -> None:
    """A healthy HTTP response is insufficient when identity or DB differs."""

    with pytest.raises(ValueError, match=message):
        verify_parity(
            _health(),
            _health(**public_override),
            expected_app_version="8.0.1",
            expected_mode="saas",
        )
