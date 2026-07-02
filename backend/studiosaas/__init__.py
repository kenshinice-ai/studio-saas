"""StudioSaaS v1 package.

This package holds the multi-tenant SaaS layer that is being introduced beside
the original single-studio Let's Paint CMS. The legacy app remains runnable
while v1 modules are built out behind explicit routes and migration scripts.
"""

from .api_v1 import api_v1, api_v1_by_slug

__all__ = ["api_v1", "api_v1_by_slug"]
