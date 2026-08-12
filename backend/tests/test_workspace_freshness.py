"""A studio's public shell must say what the studio is called today.

`tenants/<slug>/` is materialised: the name is written into <title>, into the
social-preview tags and into the structured data when the tenant is created.
Nothing rewrote those files afterwards, and the regeneration script says so in
its own docstring — it reads tenant.json, never the database. So a studio that
renamed itself six weeks ago was still serving its old name to every crawler
and every link unfurler, while the page a human opened looked correct because
the browser had asked /brand.

These assertions cover the two halves of the fix: publishing rewrites the
shell, and the head strings survive a boot-time regeneration that has no
database to ask.
"""

from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path

from studiosaas.workspaces import ensure_tenant_workspace, head_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_SOURCE = (PROJECT_ROOT / "backend/studiosaas/api_v1.py").read_text(encoding="utf-8")


def _workspace(tmp_path, name, head=None, slug="head-studio"):
    app_root = tmp_path / "app"
    if not app_root.exists():
        app_root.mkdir()
        shutil.copytree(PROJECT_ROOT / "tenant-template", app_root / "tenant-template")
    relative = ensure_tenant_workspace(app_root, slug, name, head)
    return app_root / relative


def test_head_falls_back_the_way_the_page_does():
    """The file and the script must agree, or a crawler reads a third answer."""

    assert head_values("Ruby's Studio") == {
        "title": "Ruby's Studio",
        "description": "Ruby's Studio — 课程报名、学员课时与记录查询。",
    }
    supplied = head_values("Ruby's Studio", {"title": "Oil painting in Carlton", "description": "Small classes."})
    assert supplied == {"title": "Oil painting in Carlton", "description": "Small classes."}
    # An empty override is not an override.
    assert head_values("Ruby's Studio", {"title": "  ", "description": ""})["title"] == "Ruby's Studio"


def test_api_composes_the_head_from_the_same_fields_as_the_portal():
    """applySeo() reads seo_title, then hero subtitle, then slogan."""

    api_v1 = importlib.import_module("studiosaas.api_v1")
    settings = {
        "slogan": {"zh": "用色彩表达情感", "en": "Colour, and what it says"},
        "hero_profile": {"subtitle": {"zh": "", "en": ""}},
        "website_profile": {},
    }
    assert api_v1._tenant_head("Mellow Pear Studio", settings) == {
        "title": "Mellow Pear Studio",
        "description": "用色彩表达情感",
    }

    settings["hero_profile"]["subtitle"] = {"zh": "从第一笔到第一幅", "en": "From first mark to first work"}
    assert api_v1._tenant_head("Mellow Pear Studio", settings)["description"] == "从第一笔到第一幅"

    settings["website_profile"] = {
        "seo_title": {"zh": "墨梨画室 · 卡尔顿", "en": "Mellow Pear · Carlton"},
        "seo_description": {"zh": "成人小班油画课", "en": "Small-group oil painting"},
    }
    assert api_v1._tenant_head("Mellow Pear Studio", settings) == {
        "title": "墨梨画室 · 卡尔顿",
        "description": "成人小班油画课",
    }


def test_a_rename_reaches_the_served_document(tmp_path):
    """The whole point: re-render, and the old name is gone from the file."""

    workspace = _workspace(tmp_path, "Ruby's Studio")
    before = (workspace / "index.html").read_text(encoding="utf-8")
    assert "Ruby&#x27;s Studio" in before

    workspace = _workspace(tmp_path, "Mellow Pear Studio")
    after = (workspace / "index.html").read_text(encoding="utf-8")
    assert "<title>Mellow Pear Studio</title>" in after
    assert "Ruby" not in after
    for marker in ('property="og:title" content="Mellow Pear Studio"',
                   'name="twitter:title" content="Mellow Pear Studio"'):
        assert marker in after


def test_the_seo_override_reaches_a_crawler_that_runs_no_scripts(tmp_path):
    """It used to exist only in JavaScript, which an unfurler never runs."""

    workspace = _workspace(
        tmp_path, "Mellow Pear Studio",
        {"title": "Oil painting classes in Carlton", "description": "Small adult groups, six to a table."},
    )
    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "<title>Oil painting classes in Carlton</title>" in html
    assert 'name="description" content="Small adult groups, six to a table."' in html
    assert "{{TENANT_HEAD" not in html


def test_regeneration_carries_the_head_rather_than_recomputing_it(tmp_path):
    """The boot script has no database, so anything it recomputes is a reset."""

    workspace = _workspace(tmp_path, "Mellow Pear Studio", {"title": "Oil painting classes in Carlton"})
    meta = json.loads((workspace / "tenant.json").read_text(encoding="utf-8"))
    assert meta["head"]["title"] == "Oil painting classes in Carlton"

    # Exactly what regenerate_tenant_workspaces.py does on every container boot.
    again = _workspace(tmp_path, meta["name"], meta["head"])
    assert "<title>Oil painting classes in Carlton</title>" in (again / "index.html").read_text(encoding="utf-8")

    script = (PROJECT_ROOT / "backend/scripts/regenerate_tenant_workspaces.py").read_text(encoding="utf-8")
    assert 'meta.get("head")' in script
    assert "ensure_tenant_workspace(PROJECT_ROOT, slug, name, head)" in script


def test_publishing_refreshes_the_workspace_after_the_commit():
    """Before the commit, a filesystem error would roll back a real publish."""

    assert "_refresh_tenant_workspace(tenant.slug" in API_SOURCE
    publish_tail = API_SOURCE.split('action="brand.published"', 1)[1].split("return jsonify", 1)[0]
    assert publish_tail.index("conn.commit()") < publish_tail.index("_refresh_tenant_workspace")


def test_deep_health_reports_a_shell_that_has_drifted_from_the_database():
    """Theme drift was found this way. Name drift went six weeks unnoticed."""

    assert 'body["workspaces"] = _workspace_drift(conn)' in API_SOURCE
    assert "def _workspace_drift(conn)" in API_SOURCE
    drift = API_SOURCE.split("def _workspace_drift(conn)", 1)[1].split("\n@api_v1", 1)[0]
    assert '"stale"' in drift and '"status": "drifted" if stale else "ok"' in drift


def test_the_home_page_no_longer_bakes_the_name_into_its_own_head():
    """A token the writer fills, so one place decides what a crawler reads."""

    source = (PROJECT_ROOT / "tenant-template/index.html").read_text(encoding="utf-8")
    assert "<title>{{TENANT_HEAD_TITLE}}</title>" in source
    for prop in ("og:title", "twitter:title"):
        assert f'property="{prop}" content="{{{{TENANT_HEAD_TITLE}}}}"' in source or \
               f'name="{prop}" content="{{{{TENANT_HEAD_TITLE}}}}"' in source
    head_block = source.split("</head>", 1)[0]
    assert 'content="{{TENANT_NAME}} — ' not in head_block
