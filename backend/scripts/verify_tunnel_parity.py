#!/usr/bin/env python3
"""Fail unless local and public deep-health responses describe one release."""

from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REQUIRED_EQUAL_FIELDS = ("service", "version", "appVersion", "mode", "showProducerCredit")


def fetch_health(base_url: str, timeout_seconds: float = 10) -> dict[str, Any]:
    """Fetch a deep health document with explicit transport/JSON errors."""

    url = f"{base_url.rstrip('/')}/v1/health?deep=1"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "PWE-Studio-Parity/8.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Health request returned HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Health request failed for {url}: {exc.reason}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Health response is not valid JSON: {url}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Health response must be a JSON object: {url}")
    return payload


def verify_parity(
    local: dict[str, Any],
    public: dict[str, Any],
    *,
    expected_app_version: str,
    expected_mode: str,
) -> None:
    """Validate readiness, database health and release identity."""

    for label, payload in (("local", local), ("public", public)):
        if payload.get("ok") is not True:
            raise ValueError(f"{label} health is not ready: ok={payload.get('ok')!r}")
        if payload.get("db") != "ok":
            raise ValueError(f"{label} deep health did not confirm PostgreSQL: db={payload.get('db')!r}")
        if payload.get("appVersion") != expected_app_version:
            raise ValueError(
                f"{label} appVersion mismatch: expected {expected_app_version!r}, "
                f"received {payload.get('appVersion')!r}"
            )
        if payload.get("mode") != expected_mode:
            raise ValueError(
                f"{label} mode mismatch: expected {expected_mode!r}, received {payload.get('mode')!r}"
            )
    mismatches = {
        field: (local.get(field), public.get(field))
        for field in REQUIRED_EQUAL_FIELDS
        if local.get(field) != public.get(field)
    }
    if mismatches:
        details = ", ".join(f"{field}={values!r}" for field, values in mismatches.items())
        raise ValueError(f"Local/public health responses are not the same release: {details}")


def parse_args() -> argparse.Namespace:
    """Parse strict parity expectations."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-base-url", required=True)
    parser.add_argument("--public-base-url", required=True)
    parser.add_argument("--expected-app-version", required=True)
    parser.add_argument("--expected-mode", default="saas", choices=("saas", "standalone"))
    return parser.parse_args()


def main() -> int:
    """Fetch both surfaces and print concise non-secret evidence."""

    args = parse_args()
    local = fetch_health(args.local_base_url)
    public = fetch_health(args.public_base_url)
    verify_parity(
        local,
        public,
        expected_app_version=args.expected_app_version,
        expected_mode=args.expected_mode,
    )
    print(
        "Tunnel parity verified: "
        f"appVersion={local['appVersion']}, mode={local['mode']}, db={local['db']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
