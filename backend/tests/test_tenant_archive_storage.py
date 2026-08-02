"""Archiving must refuse before it starts when it has nowhere to write.

Production archived nothing for as long as the feature existed: `backend/archives`
is excluded from the build context on purpose (mutable legal-retention data must
not ride inside an image), so the path did not exist when Docker created the
named volume mounted over it — and a volume whose mountpoint Docker has to
create itself is owned by root, while the application runs as uid 10001. Every
attempt died with `PermissionError` halfway through `archive_tenant`, surfacing
as a bare "Internal Server Error" toast *after* the operator had typed the slug
to confirm a destructive action.

The Dockerfile now creates the directory before the chown so a fresh volume is
seeded with the right owner. These tests cover the other half: the service must
notice an unwritable archive root and say so, rather than starting work it
cannot finish.
"""

from __future__ import annotations

import os

import pytest

from studiosaas.services.tenant_archive import (
    TenantArchiveError,
    _archive_base,
    _archive_root,
    _ensure_archive_base,
)


def test_archive_base_follows_configuration(app, tmp_path):
    """An operator can move the retention volume without patching code."""

    target = tmp_path / "somewhere-else"
    with app.app_context():
        app.config["ARCHIVE_DIR"] = str(target)
        try:
            assert _archive_base() == target.resolve()
            assert _archive_root("dance-dance").parent == target.resolve()
        finally:
            app.config.pop("ARCHIVE_DIR", None)


def test_archive_base_is_created_when_missing(app, tmp_path):
    target = tmp_path / "archives" / "tenants"
    with app.app_context():
        app.config["ARCHIVE_DIR"] = str(target)
        try:
            assert _ensure_archive_base() == target.resolve()
            assert target.is_dir()
        finally:
            app.config.pop("ARCHIVE_DIR", None)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_unwritable_archive_root_raises_a_usable_error(app, tmp_path):
    """The production failure, reproduced: a root the app user cannot write."""

    parent = tmp_path / "volume"
    parent.mkdir()
    target = parent / "tenants"
    parent.chmod(0o500)          # readable and traversable, not writable
    try:
        with app.app_context():
            app.config["ARCHIVE_DIR"] = str(target)
            try:
                with pytest.raises(TenantArchiveError) as caught:
                    _ensure_archive_base()
            finally:
                app.config.pop("ARCHIVE_DIR", None)
    finally:
        parent.chmod(0o700)

    message = str(caught.value)
    assert str(target) in message, "the error must name the path an operator has to fix"
    assert "volume" in message.lower(), "the error must point at the mount, not the code"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_existing_but_read_only_archive_root_is_rejected(app, tmp_path):
    """mkdir(exist_ok=True) succeeds on a read-only directory — writing does not."""

    target = tmp_path / "tenants"
    target.mkdir()
    target.chmod(0o500)
    try:
        with app.app_context():
            app.config["ARCHIVE_DIR"] = str(target)
            try:
                with pytest.raises(TenantArchiveError, match="not writable"):
                    _ensure_archive_base()
            finally:
                app.config.pop("ARCHIVE_DIR", None)
    finally:
        target.chmod(0o700)
