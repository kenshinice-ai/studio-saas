"""Tenant surface generation and routing tests."""

import json
import shutil
import subprocess
from pathlib import Path

from studiosaas.workspaces import ensure_tenant_workspace


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXISTING_TENANTS = (
    "lets-paint-studio",
    "lets-play-piano",
    "lets-play-game",
    "dance-dance",
)


def test_new_tenant_workspace_generates_public_surface_files(tmp_path):
    """Future tenants must get the file-backed portal/register/admin surfaces."""

    app_root = tmp_path / "app"
    app_root.mkdir()
    shutil.copytree(PROJECT_ROOT / "tenant-template", app_root / "tenant-template")

    workspace_path = ensure_tenant_workspace(
        app_root,
        "new-music-studio",
        "New Music Studio",
    )

    workspace = app_root / workspace_path
    assert (workspace / "index.html").is_file()
    assert (workspace / "register.html").is_file()
    assert (workspace / "studio-admin.html").is_file()

    metadata = json.loads((workspace / "tenant.json").read_text(encoding="utf-8"))
    assert metadata == {
        "slug": "new-music-studio",
        "name": "New Music Studio",
        "workspace_path": "tenants/new-music-studio",
    }
    for filename in ("index.html", "register.html", "studio-admin.html"):
        content = (workspace / filename).read_text(encoding="utf-8")
        assert "{{TENANT_" not in content
        assert "new-music-studio" in content
    register_html = (workspace / "register.html").read_text(encoding="utf-8")
    assert "/_legacy/register" not in register_html
    assert "customFields" in register_html
    assert "privacyConsent: true" in register_html
    assert 'data-language="zh"' in register_html
    assert 'data-language="en"' in register_html
    assert "pwe_lang_${TENANT_SLUG}" in register_html
    portal_html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "heroProfile" in portal_html
    assert "websiteProfile" in portal_html
    assert "visualTheme" in portal_html
    assert "localizedCopy" in portal_html
    assert "privacyConsent:true" in portal_html
    assert "manifest-portal.json" in portal_html
    assert 'id="main-content"' in portal_html
    assert "/assets/public-analytics.js" in portal_html


def test_workspace_escapes_tenant_name_for_html_and_javascript(tmp_path):
    """Names with punctuation must not break generated inline scripts or markup."""

    app_root = tmp_path / "app"
    app_root.mkdir()
    shutil.copytree(PROJECT_ROOT / "tenant-template", app_root / "tenant-template")
    workspace_path = ensure_tenant_workspace(
        app_root,
        "artists-and-friends",
        "Artist's <Friends> & Studio",
    )
    register_html = (app_root / workspace_path / "register.html").read_text(encoding="utf-8")
    assert "Artist&#x27;s &lt;Friends&gt; &amp; Studio Registration" in register_html
    assert "const TENANT_NAME = \"Artist's <Friends> & Studio\";" in register_html
    inline_script = register_html.rsplit("<script>", 1)[1].split("</script>", 1)[0]
    subprocess.run(
        ["node", "--check"],
        input=inline_script,
        text=True,
        check=True,
        capture_output=True,
    )


def test_existing_tenants_render_all_four_surfaces(client):
    """Current pilot tenants must expose portal, CMS, register, and Studio Admin."""

    for slug in EXISTING_TENANTS:
        for suffix in ("", "/cms", "/register", "/studio-admin"):
            response = client.get(f"/{slug}{suffix}")
            assert response.status_code == 200, f"{slug}{suffix or '/'}"
            assert "text/html" in response.content_type


def test_root_studio_admin_requires_explicit_tenant_selection(client):
    response = client.get("/studio-admin", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/super-admin#tenants")


def test_admin_surfaces_share_persistent_language_switch(client):
    for path in ("/super-admin", "/lets-paint-studio/studio-admin"):
        response = client.get(path)
        assert response.status_code == 200
        assert "/assets/admin-i18n.js" in response.get_data(as_text=True)

    javascript = (PROJECT_ROOT / "backend/frontend/assets/admin-i18n.js").read_text(
        encoding="utf-8"
    )
    assert "studiosaas_admin_language" in javascript
    assert "data-admin-language" in javascript
    assert "中文" in javascript
    assert "English" in javascript


def test_existing_register_surfaces_are_lightweight_lead_capture_pages(client):
    """Standalone register pages should no longer iframe the legacy registration app."""

    for slug in EXISTING_TENANTS:
        response = client.get(f"/{slug}/register")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "/_legacy/register" not in html
        assert f"/v1/public/${{encodeURIComponent(TENANT_SLUG)}}/registrations" in html
        assert "source: 'standalone_register'" in html
        assert "privacyConsent: true" in html
        assert 'id="publicationConsent"' in html
        assert "publicationConsent:" in html
        assert "Quick Registration" in html
        assert 'data-zh="提交报名"' in html
        assert "language: currentLanguage" in html


def test_portal_is_primary_registration_source(client):
    """The public website owns the primary registration CTA and source tag."""

    for slug in EXISTING_TENANTS:
        html = client.get(f"/{slug}").get_data(as_text=True)
        assert "source:'portal'" in html
        assert "privacyConsent:true" in html
        assert 'id="j-publication-consent"' in html
        assert "publicationConsent:publicationChecked" in html
        assert "utm_campaign" in html
        assert f'data-tenant-slug="{slug}"' in html
        assert "manifest-portal.json" in html
        assert "/assets/public-analytics.js" in html


def test_existing_portals_apply_published_visual_theme_and_localized_copy(client):
    """Every file-backed portal must consume the fields shown in Studio Admin."""

    for slug in EXISTING_TENANTS:
        html = client.get(f"/{slug}").get_data(as_text=True)
        assert "button-rounded" in html, slug
        assert "button-sharp" in html, slug
        assert "visual.button_style||visual.buttonStyle" in html, slug
        assert "localized.hero_title" in html, slug
        assert "localized.primary_cta" in html, slug
        assert "language: window.LANG || LANG" in html, slug


def test_studio_admin_is_brand_publication_only(client):
    """Studio Admin must not ship hidden duplicate operational sections."""

    html = client.get("/lets-paint-studio/studio-admin").get_data(as_text=True)
    assert 'id="saveDraftBtn"' in html
    assert 'id="publishSettingsBtn"' in html
    assert 'id="brandVersionList"' in html
    assert 'id="settingHeroTitleEn"' in html
    assert 'id="settingRegisterIntroEn"' in html
    assert 'id="settingHeroImageFile"' in html
    assert 'id="settingPrincipalImageFile"' in html
    assert 'id="tab-analytics"' in html
    for forbidden in (
        'id="section-students"',
        'id="section-attendance"',
        'id="section-courses"',
        'id="section-packages"',
        'id="section-registrations"',
        'id="section-portfolio"',
        'id="section-overview"',
        'id="section-advanced"',
    ):
        assert forbidden not in html
    assert "api('/dashboard')" not in html


def test_cms_exposes_role_scoped_navigation_and_owner_controls():
    """The built CMS must pair backend permissions with visible role boundaries."""

    javascript = (PROJECT_ROOT / "backend/frontend/assets/cms-app.js").read_text(encoding="utf-8")
    assert "front_desk" in javascript
    assert "allowedTabs" in javascript
    assert "只有 Owner 可以新增、停用或更改成员角色" in javascript
