"""Error responses for StudioSaaS — JSON for the API, a page for a browser.

Every error in this application came out as `{"error": "not_found"}`, including
a browser typing an address into the bar. There are 48 call sites; changing
them one at a time is 48 chances to miss one, so the negotiation happens here
and all of them inherit it. `Sec-Fetch-Dest: document` is the signal — it is
sent by every current browser on a navigation and by nothing else — with the
`Accept` header as the fallback for clients that do not send it. Anything
under an API prefix stays JSON regardless.

The page cannot be a template that loads assets: it also answers requests that
never resolved to a tenant, and an error page that depends on the thing that
failed is not an error page. backend/frontend/error.html is self-contained.
"""

from __future__ import annotations

import secrets
from html import escape
from http import HTTPStatus
from typing import Any

from flask import Response, current_app, jsonify, request


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


def api_error(
    message: str,
    status: int = 400,
    *,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> tuple[Any, int]:
    """Return the canonical API error body.

    The public contract always includes ``{"error": code, "message": text}``;
    a caller may add structured ``details`` for an actionable conflict such as
    a plan-change confirmation gate. Internal 500 details remain hidden unless
    Flask is running in debug mode.
    """

    code = error or ERROR_BY_STATUS.get(status, "invalid_request")
    safe_message = str(message or "")
    if status >= 500 and not current_app.debug and "reference" not in safe_message:
        safe_message = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "Server error"
    if not safe_message:
        safe_message = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "Request failed"
    body: dict[str, Any] = {"error": code, "message": safe_message}
    if details is not None:
        body["details"] = details
    if _navigating_browser():
        return _error_page(code, status, safe_message), status
    return jsonify(body), status


# Paths whose callers are always programs. A fetch() from the console sends
# `Sec-Fetch-Dest: empty`, so this is belt and braces — but a deep link into
# /v1/... typed by hand should still answer in the API's own language.
API_PREFIXES = ("/v1/", "/api/", "/_legacy/api/")


def _navigating_browser() -> bool:
    """True when a person is looking at this, rather than a program reading it."""

    try:
        path = request.path
    except RuntimeError:          # outside a request context
        return False
    if path.startswith(API_PREFIXES):
        return False
    destination = request.headers.get("Sec-Fetch-Dest")
    if destination:
        return destination == "document"
    accept = request.headers.get("Accept", "")
    return "text/html" in accept and "application/json" not in accept


# 语言跟地址走，和公开页一致：/zh/… 是中文，其余英文优先。两种语言都在页面上，
# 顺序决定谁在第一屏。
_COPY = {
    404: {
        "title": "找不到这个地址",
        "headline_zh": "这个地址不存在",
        "body_zh": "链接可能拼错了，或者这个页面已经搬走。工作室的公开地址是 "
                   "pwestudio.online/工作室名。",
        "headline_en": "This address does not exist.",
        "body_en": "The link may be mistyped, or the page has moved. A studio's "
                   "public address is pwestudio.online/its-name.",
    },
    403: {
        "title": "没有权限",
        "headline_zh": "这个页面需要权限",
        "body_zh": "你登录的账号看不到这一页。换一个账号，或者请工作室管理员授权。",
        "headline_en": "You do not have access to this page.",
        "body_en": "Sign in with another account, or ask the studio owner to grant it.",
    },
    410: {
        "title": "地址已停用",
        "headline_zh": "这个地址已经停用",
        "body_zh": "它曾经属于一个工作室，现在不再提供服务。",
        "headline_en": "This address has been retired.",
        "body_en": "It belonged to a studio that is no longer served here.",
    },
}
_DEFAULT_COPY = {
    "title": "出错了",
    "headline_zh": "服务器上出了点问题",
    "body_zh": "这不是你操作的问题。稍后再试；如果一直这样，把这个地址发给我们。",
    "headline_en": "Something went wrong on our side.",
    "body_en": "This is not something you did. Try again shortly, and send us "
               "this address if it keeps happening.",
}

_TEMPLATE_CACHE: dict[str, str] = {}


def _error_page(code: str, status: int, message: str) -> Response:
    from pathlib import Path

    template = _TEMPLATE_CACHE.get("page")
    if template is None:
        source = Path(__file__).resolve().parents[1] / "frontend" / "error.html"
        template = source.read_text(encoding="utf-8")
        _TEMPLATE_CACHE["page"] = template

    copy = _COPY.get(status, _DEFAULT_COPY)
    chinese_first = request.path.startswith("/zh/")
    page = template
    for token, value in {
        "__LANG__": "zh-CN" if chinese_first else "en",
        "__TITLE__": copy["title"],
        "__STATUS__": f"{status} · {code}",
        "__HEADLINE_ZH__": copy["headline_zh"],
        "__BODY_ZH__": copy["body_zh"],
        "__HEADLINE_EN__": copy["headline_en"],
        "__BODY_EN__": copy["body_en"],
        "__CTA_ZH__": "回到首页",
        "__CTA_EN__": "Product home",
        "__HELP_ZH__": "使用手册",
        "__HELP_EN__": "Manual",
        "__PATH__": escape(request.path),
    }.items():
        page = page.replace(token, value)
    response = Response(page, mimetype="text/html; charset=utf-8")
    response.headers["Cache-Control"] = "no-store"
    return response


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
        """A fault the operator cannot act on, plus a way to find it.

        Hiding the detail from the response is right — it can carry a query,
        a path or a value. But "Internal Server Error" on its own leaves the
        person in front of the screen with nothing to report and nobody able
        to find their incident in a log holding thousands of lines. A short
        reference, logged beside the traceback, costs nothing and turns a
        support message into a `grep`.
        """

        reference = secrets.token_hex(3)
        current_app.logger.exception("unhandled error [ref %s]", reference)
        return api_error(f"Server error. Quote reference {reference} when reporting this.", 500)
