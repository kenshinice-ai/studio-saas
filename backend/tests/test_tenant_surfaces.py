"""Tenant surface generation and routing tests."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from studiosaas.workspaces import WorkspaceError, ensure_tenant_workspace, validate_tenant_slug


PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Read off disk rather than typed here. This tuple used to name four tenants;
# production had moved on to a different six, and the four local directories
# were stale generated copies nobody was serving. Deriving the list means
# archiving a workspace is a one-step change instead of a red suite, and a
# workspace that stops rendering still fails.
EXISTING_TENANTS = tuple(sorted(
    path.name for path in (PROJECT_ROOT / "tenants").iterdir()
    if (path / "index.html").is_file()
))


@pytest.mark.parametrize("slug", ["cms", "platform-admin"])
def test_control_plane_and_neutral_entry_slugs_are_reserved(slug):
    """A tenant workspace must never shadow a platform or neutral entry route."""

    with pytest.raises(WorkspaceError, match="reserved"):
        validate_tenant_slug(slug)


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
    # v8.9.0. The public timetable is a page, so a tenant that never opens
    # Studio Admin still has the file — the switch decides whether the endpoint
    # answers, not whether the shell exists.
    assert (workspace / "timetable.html").is_file()

    metadata = json.loads((workspace / "tenant.json").read_text(encoding="utf-8"))
    assert metadata == {
        "slug": "new-music-studio",
        "name": "New Music Studio",
        "workspace_path": "tenants/new-music-studio",
    }
    for filename in ("index.html", "register.html", "studio-admin.html", "timetable.html"):
        content = (workspace / filename).read_text(encoding="utf-8")
        assert "{{TENANT_" not in content
        assert "new-music-studio" in content
    register_html = (workspace / "register.html").read_text(encoding="utf-8")
    assert "/_legacy/register" not in register_html
    assert 'id="requiredCustomFields"' in register_html
    assert 'id="optionalCustomFields"' in register_html
    assert 'class="optional-details"' in register_html
    # Submission moved into /assets/public-register.js so the portal and the
    # register page cannot drift apart again; the page supplies the parts that
    # genuinely differ and the module owns privacyConsent.
    assert "/assets/public-register.js" in register_html
    assert "StudioSaaSPublicRegister.submit(" in register_html
    assert "source: 'standalone_register'" in register_html
    assert "privacyNoticeVersion: privacyNoticeVersion" in register_html
    assert 'data-language="zh"' in register_html
    assert 'data-language="en"' in register_html
    assert "pwe_lang_${TENANT_SLUG}" in register_html
    portal_html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "heroProfile" in portal_html
    assert "websiteProfile" in portal_html
    # The theme map and the light/dark decision moved to one shared module in
    # v8.9.0 — two inline copies had already drifted and a third was about to
    # be written. So the portal is checked for USING it, and the module is
    # checked for containing it (test_portal_theme_contract.py).
    assert "/assets/portal-brand.js" in portal_html
    assert "applyVisualTheme" in portal_html
    assert "localizedCopy" in portal_html
    assert "StudioSaaSPublicRegister.submit(" in portal_html
    assert "privacyNoticeVersion: state.privacyNoticeVersion" in portal_html
    assert "manifest-portal.json" in portal_html
    assert 'id="main-content"' in portal_html
    assert "/assets/public-analytics.js" in portal_html
    assert 'id="producerCredit" hidden' in portal_html
    assert "health.showProducerCredit" in portal_html


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
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="tenantSlug" type="text" required' in html
    assert "localStorage.getItem('studiosaas_tenant_slug')" not in html
    assert "Enter the studio URL slug to continue." in html


def test_root_cms_requires_explicit_tenant_selection(client):
    response = client.get("/cms", follow_redirects=False)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="tenantSlug" name="tenantSlug" required' in html
    assert "系统不会自动选择或恢复旧租户" in html
    assert 'href="/lets-paint-showcase/cms"' in html
    assert "localStorage" not in html


def test_admin_surfaces_share_persistent_language_switch(client):
    for path in (
        "/platform-admin",
        "/super-admin",
        "/lets-paint-studio/studio-admin",
    ):
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


def test_studio_admin_supports_curated_styles_custom_mode_and_undo(client):
    html = client.get("/lets-paint-studio/studio-admin").get_data(as_text=True)
    assert 'id="stylePresetSelect"' in html
    assert 'id="stylePresetPreview"' in html
    assert 'id="themePalettePreview"' in html
    assert 'class="brand-step"' in html
    assert 'id="undoPresetBtn"' in html
    assert 'id="settingThemeMuted"' in html
    assert 'id="settingThemeBorder"' in html
    assert "recommendedStyleId" in html
    assert "themeMode = 'custom'" in html
    assert "Improve colour contrast before publishing" in html


def test_existing_register_surfaces_are_lightweight_lead_capture_pages(client):
    """Standalone register pages should no longer iframe the legacy registration app."""

    for slug in EXISTING_TENANTS:
        response = client.get(f"/{slug}/register")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "/_legacy/register" not in html
        assert "/assets/public-register.js" in html
        assert "StudioSaaSPublicRegister.submit(" in html
        assert "source: 'standalone_register'" in html
        # The notice version is served by /brand rather than hard-coded here,
        # so a consent record always cites the text the visitor could read.
        assert "privacyNoticeVersion: privacyNoticeVersion" in html
        assert 'id="privacyDialog"' in html
        assert 'id="publicationConsent"' in html
        assert "publicationConsent:" in html
        assert "Quick Registration" in html
        assert 'data-zh="提交报名"' in html
        assert "language: currentLanguage" in html
        assert "/assets/brand-system.css" in html
        assert 'data-zh="报名已收到"' in html
        assert 'id="copyContactBtn"' in html
        assert 'class="next-step brand-status"' in html
        assert "document.getElementById('done').focus()" in html
        assert 'id="requiredCustomFields"' in html
        assert 'id="optionalCustomFields"' in html
        assert 'class="optional-details"' in html
        assert 'class="submit-bar"' in html


def test_portal_is_primary_registration_source(client):
    """The public website owns the primary registration CTA and source tag."""

    for slug in EXISTING_TENANTS:
        html = client.get(f"/{slug}").get_data(as_text=True)
        assert "StudioSaaSPublicRegister.submit(" in html
        assert "source: 'portal'" in html
        assert "privacyNoticeVersion: state.privacyNoticeVersion" in html
        assert 'id="j-publication-consent"' in html
        assert "publicationConsent: publicationChecked" in html
        # UTM capture moved into the shared module alongside the POST it
        # decorates, so both public forms attribute a campaign identically.
        assert "/assets/public-register.js" in html
        assert f'data-tenant-slug="{slug}"' in html
        assert "manifest-portal.json" in html
        assert "/assets/public-analytics.js" in html
        assert "/assets/brand-system.css" in html
        assert 'id="joinRequiredCustomFields"' in html
        assert 'id="joinOptionalCustomFields"' in html
        assert 'class="progressive"' in html
        assert 'class="join-submit"' in html


def test_shared_registration_renderer_splits_required_and_optional_fields():
    """Both public forms must use the same progressive-disclosure contract."""

    source = (PROJECT_ROOT / "backend/frontend/assets/public-register.js").read_text(
        encoding="utf-8"
    )
    assert "requiredContainer" in source
    assert "optionalContainer" in source
    assert "Array.isArray(opts.containers)" in source


def test_existing_portals_apply_published_visual_theme_and_localized_copy(client):
    """Every file-backed portal must consume the fields shown in Studio Admin."""

    for slug in EXISTING_TENANTS:
        html = client.get(f"/{slug}").get_data(as_text=True)
        # The palette — including the button/typeface classes — is applied by
        # /assets/portal-brand.js since v8.9.0, so the page is checked for
        # USING it rather than for containing it. The module's own contents are
        # pinned by test_portal_theme_contract.py.
        #
        # This assertion only moved because a regenerated workspace made it
        # fail: the materialised pages under tenants/ lag tenant-template until
        # regenerate_tenant_workspaces.py runs, which the deploy entrypoint
        # does on every boot. Worth remembering when a portal test passes
        # locally and the same code behaves differently after a release.
        assert "/assets/portal-brand.js" in html, slug
        assert "applyVisualTheme" in html, slug
        assert "localized.hero_title" in html, slug
        assert "localized.primary_cta" in html, slug
        assert "language: lang()" in html, slug
        # setCopy() used to guess a string's language by testing it for Han
        # characters, leaving one audience reading template sample copy.
        assert "function setCopy(" not in html, slug
        # Tenant-authored copy reaches this page from /brand, so the language
        # switch must write it as text. Rendering it as HTML made Studio Admin
        # a stored-XSS vector against every portal visitor.
        assert "el.textContent = nouns(copy)" in html, slug
        # Every innerHTML use in the portal clears a container; none of them
        # assigns copy. Nodes are built with createElement/textContent.
        # Comments are stripped first so prose about the old bug is not a hit.
        code = re.sub(r"/\*.*?\*/", "", html, flags=re.S)
        assignments = re.findall(r"\.innerHTML\s*=\s*([^;]+);", code)
        assert assignments, slug
        assert all(value.strip() in {"''", '""'} for value in assignments), (slug, assignments)


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
