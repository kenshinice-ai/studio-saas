"""JSON error response helpers for StudioSaaS HTTP APIs."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from flask import current_app, jsonify


ERROR_BY_STATUS = {
    400: "invalid_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    429: "rate_limited",
    500: "internal_server_error",
    503: "service_unavailable",
}


def api_error(message: str, status: int = 400, *, error: str | None = None) -> tuple[Any, int]:
    """Return the canonical API error body.

    The public contract is always ``{"error": code, "message": text}``.
    Internal 500 details are hidden unless Flask is running in debug mode.
    """

    code = error or ERROR_BY_STATUS.get(status, "invalid_request")
    safe_message = str(message or "")
    if status >= 500 and not current_app.debug:
        safe_message = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "Server error"
    if not safe_message:
        safe_message = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "Request failed"
    return jsonify({"error": code, "message": safe_message}), status


def register_error_handlers(app: Any) -> None:
    """Install JSON error handlers for common Flask/Werkzeug errors."""

    @app.errorhandler(400)
    def _bad_request(exc: Exception) -> tuple[Any, int]:
        return api_error(getattr(exc, "description", "Bad request"), 400)

    @app.errorhandler(401)
    def _unauthorized(exc: Exception) -> tuple[Any, int]:
        return api_error(getattr(exc, "description", "Authentication required."), 401)

    @app.errorhandler(403)
    def _forbidden(exc: Exception) -> tuple[Any, int]:
        return api_error(getattr(exc, "description", "Forbidden."), 403)

    @app.errorhandler(404)
    def _not_found(exc: Exception) -> tuple[Any, int]:
        return api_error(getattr(exc, "description", "Not found"), 404)

    @app.errorhandler(413)
    def _too_large(exc: Exception) -> tuple[Any, int]:
        return api_error(getattr(exc, "description", "Request body is too large."), 413)

    @app.errorhandler(429)
    def _rate_limited(exc: Exception) -> tuple[Any, int]:
        return api_error(getattr(exc, "description", "Rate limit exceeded."), 429)

    @app.errorhandler(500)
    def _internal_error(exc: Exception) -> tuple[Any, int]:
        return api_error(str(exc), 500)
