"""Configuration helpers for the StudioSaaS multi-tenant layer."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class StudioSaaSConfig:
    """Runtime settings required by the StudioSaaS v1 API."""

    database_url: str
    public_base_domain: str


def studiosaas_mode() -> str:
    """Return the runtime delivery mode: ``"saas"`` (default) or ``"standalone"``.

    The environment is read on every call (no per-process cache) so tests can
    flip modes with a plain ``monkeypatch.setenv``; the lookup is a dict read
    and never on a hot path.
    """

    return os.environ.get("STUDIOSAAS_MODE", "").strip().lower() or "saas"


def is_standalone() -> bool:
    """Whether this process runs as the single-tenant PWE Studio Edition."""

    return studiosaas_mode() == "standalone"


def show_producer_credit() -> bool:
    """Whether tenant-facing footers show the Paradise Production attribution.

    The contractual attribution is enabled by default only for PWE Studio
    Edition. SaaS tenant pages remain tenant-first and do not inherit producer
    branding. An Edition agreement that includes paid attribution removal can
    explicitly set ``STUDIOSAAS_SHOW_PRODUCER_CREDIT=0``.

    Raises:
        RuntimeError: If the override is present but not a supported boolean.
    """

    raw_value = os.environ.get("STUDIOSAAS_SHOW_PRODUCER_CREDIT")
    if raw_value is None or not raw_value.strip():
        return is_standalone()

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(
        "STUDIOSAAS_SHOW_PRODUCER_CREDIT must be one of "
        "1/true/yes/on or 0/false/no/off."
    )


def load_config() -> StudioSaaSConfig:
    """Load StudioSaaS settings from environment variables.

    Raises:
        RuntimeError: If the PostgreSQL database URL is not configured.
    """

    database_url = (
        os.environ.get("STUDIOSAAS_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if not database_url:
        raise RuntimeError(
            "StudioSaaS database is not configured. Set STUDIOSAAS_DATABASE_URL "
            "to a PostgreSQL connection string before using /v1 tenant APIs."
        )

    public_base_domain = os.environ.get("STUDIOSAAS_PUBLIC_BASE_DOMAIN", "").strip()
    return StudioSaaSConfig(
        database_url=database_url,
        public_base_domain=public_base_domain,
    )
