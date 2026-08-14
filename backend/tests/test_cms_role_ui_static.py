"""Static regression guards for role-dependent CMS copy and actions."""

from pathlib import Path
from _cms_sources import cms_source_text


ROOT = Path(__file__).resolve().parents[2]


def test_non_financial_roles_do_not_receive_revenue_kpi_copy() -> None:
    """The CMS must hide financial semantics, not merely replace values with zero."""

    source = cms_source_text()
    assert "const canViewFinancialAnalytics = [...ownerRoles,'manager'].includes(actorRole);" in source
    assert "canViewFinancialAnalytics\n            ? {l:'历史总营收'" in source
    assert ": {l:'本月出勤'" in source
    assert "canViewFinancialAnalytics ? '经营真账（估算）' : '教学出勤'" in source
