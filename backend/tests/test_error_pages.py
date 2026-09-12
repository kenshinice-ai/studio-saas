"""A browser gets a page; a program gets JSON.

Every error this application produced was `{"error": "not_found"}`, including
the one a person sees after mistyping an address in the URL bar. The product
sells "the system is running and you can see its state"; its own error page
being one line of unstyled JSON argues the opposite.

The obvious fix — rewrite `@app.errorhandler(404)` — would have changed almost
nothing: `/nope` does not reach the handler, it reaches an explicit
`api_error('Not found', 404)` inside the tenant catch-all, and there are 48
such call sites. The negotiation lives in `api_error` so all of them inherit
it, and these assertions are about that shared exit rather than about any one
route.

Nor can the house website answer this. `/` is a tenant catch-all: the moment
the house claims the root, every `pwestudio.online/<studio-name>` stops
resolving.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = {"Sec-Fetch-Dest": "document"}


@pytest.mark.parametrize("path", ["/nope", "/not/a/page", "/lets-paint-showcase/nope"])
def test_a_browser_navigation_gets_a_page(client, path: str) -> None:
    response = client.get(path, headers=DOCUMENT)
    assert response.status_code == 404
    assert response.headers["Content-Type"].startswith("text/html")
    body = response.get_data(as_text=True)
    assert "<!doctype html>" in body.lower()
    assert "not_found" in body, "the machine-readable code is still on the page"
    # It has to say what to do next, not only what went wrong.
    assert 'href="/studio"' in body and 'href="/manual/"' in body
    assert "noindex" in body, "a 404 must not be indexed"


def test_the_page_carries_no_external_request(client) -> None:
    """It also answers when /assets is what failed."""

    body = client.get("/nope", headers=DOCUMENT).get_data(as_text=True)
    for attribute in ('<script', 'src="/assets', 'href="/assets', "http://", "https://"):
        assert attribute not in body, f"the error page reaches out for {attribute}"


@pytest.mark.parametrize("headers", [
    {},                                        # curl, no headers
    {"Sec-Fetch-Dest": "empty"},               # fetch()
    {"Accept": "application/json"},
])
def test_a_program_still_gets_json(client, headers: dict) -> None:
    response = client.get("/nope", headers=headers)
    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found", "message": "Not found"}


def test_an_api_path_stays_json_even_from_a_browser(client) -> None:
    """A /v1 address typed into the bar is still the API's to answer."""

    response = client.get("/v1/nope", headers=DOCUMENT)
    assert response.status_code == 404
    assert response.get_json()["error"] == "not_found"


def test_the_language_follows_the_address(client) -> None:
    english = client.get("/nope", headers=DOCUMENT).get_data(as_text=True)
    chinese = client.get("/zh/nope", headers=DOCUMENT).get_data(as_text=True)
    assert 'lang="en"' in english and 'lang="zh-CN"' in chinese
    # Both languages are on both pages; only the order changes.
    for body in (english, chinese):
        assert "这个地址不存在" in body and "This address does not exist." in body


def test_the_path_is_escaped_not_reflected(client) -> None:
    """The page prints the address that failed, which is attacker-controlled."""

    body = client.get("/<script>alert(1)</script>", headers=DOCUMENT).get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


def test_the_contract_covers_every_exit_not_one_handler() -> None:
    """Guard against someone 'simplifying' this back into the 404 handler."""

    source = (REPOSITORY_ROOT / "backend/studiosaas/errors.py").read_text(encoding="utf-8")
    assert "_navigating_browser" in source and "def api_error" in source
    body = source[source.index("def api_error"):]
    assert "_navigating_browser()" in body[:body.index("\ndef _navigating_browser")], (
        "api_error no longer negotiates; the other 47 call sites just went back "
        "to answering a browser with JSON"
    )
