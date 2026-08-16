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


def test_auth_me_binds_user_context_before_membership_rls_query() -> None:
    """The post-login membership read must run with the session user's RLS context."""

    source = (ROOT / "backend" / "studiosaas" / "api_v1.py").read_text()
    start = source.index('@api_v1.route("/auth/me"')
    end = source.find("\n# ─", start)
    if end == -1:
        end = len(source)
    auth_me = source[start:end]

    assert "_bind_user_session(conn, str(user_id))" in auth_me
    assert auth_me.index("_bind_user_session(conn, str(user_id))") < auth_me.index(
        "FROM memberships m"
    )
