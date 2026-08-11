"""Contracts for the Platform Admin workspace refactor.

These assertions deliberately pin the information architecture and its state
language before the visual implementation grows.  They do not replace browser
verification; they prevent a future edit from silently returning to the old
long-canvas or payment-implying copy.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONSOLE = PROJECT_ROOT / "super-admin.html"
I18N = PROJECT_ROOT / "backend/frontend/assets/admin-i18n.js"
API_V1 = PROJECT_ROOT / "backend/studiosaas/api_v1.py"


def test_platform_workspaces_have_explicit_active_workspace_contract() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    for workspace in ("overview", "tenants", "plans", "audit"):
        assert f'data-workspace="{workspace}"' in html
        assert f'data-workspace-nav="{workspace}"' in html
    assert 'id="workspaceContext"' in html
    assert 'id="lastRefreshLabel"' in html
    assert "function setActiveWorkspace" in html
    assert "window.addEventListener('hashchange'" in html


def test_platform_admin_uses_the_three_column_workbench_contract() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    for element_id in ("platformWorkspaceShell", "platformRail", "attentionQueue", "workspaceInspector", "attentionShortcut"):
        assert f'id="{element_id}"' in html
    assert 'data-platform-rail data-workspace-nav="overview"' in html
    assert "function renderAttentionQueue" in html
    assert "function openTenantInspector" in html
    assert "function renderWorkspaceInspector" in html
    assert "function openAuditInspector" in html


def test_platform_admin_uses_full_width_shell_and_center_edit_workspace() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    assert "max-width: none" in html
    assert 'id="platformEditWorkspace"' in html
    assert "function openWorkspaceEditor" in html
    assert "function closeWorkspaceEditor" in html
    assert "workspace-editor-footer" in html
    assert "renderEditorInspector" in html


def test_platform_admin_mobile_navigation_is_a_drawer_and_actions_are_hierarchical() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    assert 'id="platformMobileNavToggle"' in html
    assert 'id="platformMobileNavScrim"' in html
    assert "is-mobile-open" in html
    assert "View is the default path" in html
    assert "addActionButton(actions, 'View', 'btn-secondary btn-sm', () => openPlanInspector(p));" in html


def test_platform_inspector_keeps_support_mode_separate_and_reason_based() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    inspector = html[html.index("function renderTenantInspector") : html.index("function openTenantInspector")]
    assert "Support Mode" in inspector
    assert "Audited and reason-based" in html
    assert "Start Support Mode" in html
    assert 'id="m_supportReason"' in html


def test_platform_workspace_scrolls_clear_the_sticky_header() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    assert ".workspace-section" in html
    assert "scroll-margin-top: calc(var(--workspace-header-offset)" in html
    assert "--workspace-header-offset" in html


def test_support_mode_reason_has_field_level_validation_contract() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    assert 'id="m_supportReason"' in html
    assert "aria-required=\"true\"" in html
    assert 'id="supportReasonError"' in html
    assert "setSupportReasonError" in html
    assert "focus()" in html[html.index("setSupportReasonError") :]


def test_subscription_copy_does_not_claim_a_payment_gateway_failure() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    dictionary = I18N.read_text(encoding="utf-8")
    assert "Subscription past due" in html
    assert "订阅已逾期" in dictionary
    assert "Payment issue" not in html


def test_workspace_partial_state_is_persistent_not_toast_only() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    assert 'id="workspaceDataState"' in html
    assert 'id="workspaceRetryBtn"' in html
    assert "partialFailures" in html
    assert "workspaceDataState" in html[html.index("async function refresh") :]
    assert "#workspaceRetryBtn[hidden]" in html


def test_detail_surfaces_have_a_mobile_safe_drawer_contract() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    assert "detail-overlay" in html
    assert "detail-modal" in html
    assert "openAuditDetail" in html
    assert "tab-strip" in html
    assert "aria-label', 'Tenant detail sections'" in html


def test_platform_audit_detail_includes_actor_and_metadata() -> None:
    source = API_V1.read_text(encoding="utf-8")
    start = source.index('def admin_audit_logs')
    block = source[start : source.index('@api_v1.route("/students"', start)]
    assert "a.metadata" in block
    assert "u.email AS actor_email" in block
    assert "LEFT JOIN users u" in block
