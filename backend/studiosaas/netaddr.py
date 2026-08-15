"""Which peers may be believed when they forward a client's address.

This lives in its own module because both the v1 API and the legacy app need
the same answer, and the first attempt had api_v1 import the helper from
`server`. That failed silently in production: server.py is the entry point, so
at runtime its module name is `__main__` and `from server import …` does not
resolve to the running module. The except-branch swallowed it, the old
localhost-only rule stayed in force, and the audit table went on recording the
Docker gateway for another release. A shared module cannot fail that way.
"""

from __future__ import annotations

import ipaddress
import os

# Loopback covers the cloudflared tunnel topology this code grew up on. The
# private ranges cover the current one: nginx runs on the host and proxies to a
# container port, so the peer the container sees is the Docker bridge gateway.
#
# Trusting a forwarded address from those ranges is only safe because the
# container port is published on 127.0.0.1 (deploy/aws/docker-compose.yml), which
# makes nginx the only thing that can reach it. A deployment that binds the port
# more widely MUST narrow this with STUDIOSAAS_TRUSTED_PROXIES.
DEFAULT_TRUSTED_PROXIES = (
    "127.0.0.1", "::1", "localhost",
    "172.16.0.0/12", "10.0.0.0/8", "192.168.0.0/16",
)

_NAMES: set[str] = set()
_NETS: list = []


def _load() -> None:
    global _NAMES, _NETS
    raw = os.environ.get("STUDIOSAAS_TRUSTED_PROXIES", "")
    entries = [item.strip() for item in raw.split(",") if item.strip()] or list(DEFAULT_TRUSTED_PROXIES)
    names, nets = set(), []
    for entry in entries:
        try:
            nets.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            names.add(entry)
    _NAMES, _NETS = names, nets


_load()


def is_trusted_proxy(addr: str | None) -> bool:
    """Whether a forwarding header from this peer may be believed."""

    if not addr:
        return False
    if addr in _NAMES:
        return True
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in net for net in _NETS)


def client_ip_from(remote_addr: str | None, headers) -> str:
    """Resolve the caller's address, honouring forwarding only from a trusted peer.

    A client that reaches the app directly cannot promote itself past the rate
    limiter by inventing a header, because its own address is not trusted.
    """

    ra = remote_addr or "unknown"
    if not is_trusted_proxy(ra):
        return ra
    forwarded = (
        headers.get("CF-Connecting-IP")
        or headers.get("X-Real-IP")
        or headers.get("X-Forwarded-For")
        or ra
    )
    return forwarded.split(",")[0].strip() or ra
