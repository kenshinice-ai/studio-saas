"""Tenant surface generation and routing tests."""

import json
import shutil
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


def test_existing_tenants_render_all_four_surfaces(client):
    """Current pilot tenants must expose portal, CMS, register, and Studio Admin."""

    for slug in EXISTING_TENANTS:
        for suffix in ("", "/cms", "/register", "/studio-admin"):
            response = client.get(f"/{slug}{suffix}")
            assert response.status_code == 200, f"{slug}{suffix or '/'}"
            assert "text/html" in response.content_type
