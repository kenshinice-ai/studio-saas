"""Tenant workspace file generation for StudioSaaS."""

from __future__ import annotations

import json
import os
import re
import tempfile
from html import escape
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


def _atomic_write_text(path: Path, content: str) -> None:
    """Replace a generated file without exposing a partially written page."""

    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise WorkspaceError(f"Could not update generated workspace file '{path.name}'.") from exc


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
        "{{TENANT_NAME}}": escape(name, quote=True),
        "{{TENANT_NAME_JSON}}": json.dumps(name, ensure_ascii=False),
    }
    # Hand-customised workspace files (e.g. a bespoke portal) list themselves
    # in tenants/<slug>/.keep-local, one filename per line; those are never
    # overwritten by template regeneration.
    keep_local: set[str] = set()
    keep_local_path = workspace_dir / ".keep-local"
    if keep_local_path.is_file():
        keep_local = {
            line.strip()
            for line in keep_local_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
    for template_file in template_dir.iterdir():
        if not template_file.is_file():
            continue
        if template_file.name in keep_local:
            continue
        content = template_file.read_text(encoding="utf-8")
        for token, value in replacements.items():
            content = content.replace(token, value)
        _atomic_write_text(workspace_dir / template_file.name, content)

    metadata = {
        "slug": slug,
        "name": name,
        "workspace_path": f"tenants/{slug}",
    }
    _atomic_write_text(
        workspace_dir / "tenant.json",
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    )
    return metadata["workspace_path"]
