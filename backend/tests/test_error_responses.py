"""Canonical JSON error response checks."""


def _assert_error_shape(response):
    body = response.get_json()
    assert isinstance(body, dict)
    assert isinstance(body.get("error"), str)
    assert isinstance(body.get("message"), str)


def test_404_uses_error_message_shape(client):
    response = client.get("/missing-route")
    assert response.status_code == 404
    _assert_error_shape(response)


def test_401_uses_error_message_shape(client):
    response = client.get("/s/demo/v1/students")
    assert response.status_code == 401
    _assert_error_shape(response)


def test_400_uses_error_message_shape(client):
    response = client.post("/v1/auth/login", json={})
    assert response.status_code == 400
    _assert_error_shape(response)
