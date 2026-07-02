"""Configuration helpers for the StudioSaaS multi-tenant layer."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class StudioSaaSConfig:
    """Runtime settings required by the StudioSaaS v1 API."""

    database_url: str
    public_base_domain: str


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
