"""Tenant workspace file generation for StudioSaaS."""

from __future__ import annotations

import json
import re
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
RESERVED_SLUGS = {
    "api",
    "v1",
    "register",
    "super-admin",
    "studio-admin",
    "parent-portal",
    "manifest.json",
    "manifest-student.json",
    "sw.js",
    "vendor",
    "photos",
    "portfolio",
    "logo.png",
    "logo-light.png",
    "icon-192.png",
    "icon-512.png",
    "apple-touch-icon.png",
    "favicon.ico",
}


class WorkspaceError(RuntimeError):
    """Raised when a tenant workspace cannot be generated safely."""


def validate_tenant_slug(slug: str) -> None:
    """Validate a slug before using it as a URL segment or folder name."""

    if not SLUG_RE.match(slug):
        raise WorkspaceError("Tenant slug must be lowercase letters, numbers, or hyphens.")
    if slug in RESERVED_SLUGS:
        raise WorkspaceError(f"Tenant slug '{slug}' is reserved.")


def ensure_tenant_workspace(app_root: str | Path, slug: str, name: str) -> str:
    """Create or refresh the filesystem workspace for one tenant.

    Returns:
        Relative workspace path, for storing on the tenant record.
    """

    validate_tenant_slug(slug)
    root = Path(app_root)
    template_dir = root / "tenant-template"
    tenants_dir = root / "tenants"
    workspace_dir = tenants_dir / slug
    if not template_dir.is_dir():
        raise WorkspaceError(f"Tenant template directory is missing: {template_dir}")

    workspace_dir.mkdir(parents=True, exist_ok=True)
    replacements = {
        "{{TENANT_SLUG}}": slug,
        "{{TENANT_NAME}}": name,
    }
    for template_file in template_dir.iterdir():
        if not template_file.is_file():
            continue
        content = template_file.read_text(encoding="utf-8")
        for token, value in replacements.items():
            content = content.replace(token, value)
        (workspace_dir / template_file.name).write_text(content, encoding="utf-8")

    metadata = {
        "slug": slug,
        "name": name,
        "workspace_path": f"tenants/{slug}",
    }
    (workspace_dir / "tenant.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata["workspace_path"]
