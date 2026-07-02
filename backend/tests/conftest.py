"""Shared pytest fixtures for StudioSaaS backend tests."""

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(scope="session")
def app():
    """The Flask application (imported once per test session)."""

    import server

    server.app.config.update(TESTING=True)
    return server.app


@pytest.fixture()
def client(app):
    """A Flask test client."""

    return app.test_client()
