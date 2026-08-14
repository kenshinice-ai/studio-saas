"""Static guards for the CMS browser authentication boundary."""

from pathlib import Path
from _cms_sources import cms_source_text


ROOT = Path(__file__).resolve().parents[2]


def test_cms_uses_server_session_not_browser_local_pin() -> None:
    """A reversible local PIN must not masquerade as account authentication."""

    source = cms_source_text()
    for removed_contract in (
        "PINScreen",
        "lp_pin_v1",
        "lp_pin_enabled",
        "lp_sess_v1",
        "savePin",
        "pinEnabled",
    ):
        assert removed_contract not in source
    assert "fetch('/v1/auth/me'" in source
    assert "fetch('/v1/auth/logout'" in source
    assert "确认退出登录？" in source
