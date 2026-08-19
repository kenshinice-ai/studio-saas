"""Tenant-wide operational setting contracts for the daily roster."""

import importlib
from types import SimpleNamespace


api_v1 = importlib.import_module("studiosaas.api_v1")


class _Cursor:
    """Capture SQL parameters for the focused endpoint test."""

    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))


class _Connection:
    """Minimal connection context used by update_operational_settings."""

    def __init__(self):
        self.cursor_instance = _Cursor()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True


def test_default_class_time_requires_a_real_hhmm(app, monkeypatch):
    """Malformed defaults fail before any tenant setting can be changed."""

    for _m in (api_v1.tenant, api_v1._shared):
        monkeypatch.setattr(_m, "connect", lambda: (_ for _ in ()).throw(AssertionError("no DB")))
    with app.test_request_context(json={"defaultClassTime": "25:90"}):
        response, status = api_v1.update_operational_settings.__wrapped__()
    assert status == 400
    assert "real time" in response.get_json()["message"]


def test_default_class_time_is_saved_without_brand_publication(app, monkeypatch):
    """The operational value writes one JSON key and emits an audit event."""

    connection = _Connection()
    audit = []
    for _m in (api_v1.tenant, api_v1._shared):
        monkeypatch.setattr(_m, "connect", lambda: connection)
    monkeypatch.setattr(
        api_v1.tenant,
        "_tenant_context",
        lambda _conn: SimpleNamespace(tenant_id="tenant-1"),
    )
    monkeypatch.setattr(api_v1.tenant, "_audit_request", lambda *_args, **kwargs: audit.append(kwargs))

    with app.test_request_context(json={"defaultClassTime": "14:30"}):
        response = api_v1.update_operational_settings.__wrapped__()

    assert response.get_json() == {"ok": True, "defaultClassTime": "14:30"}
    assert connection.committed is True
    assert connection.cursor_instance.calls[0][1] == ("14:30", "tenant-1")
    assert audit[0]["action"] == "operations.default_class_time_updated"
