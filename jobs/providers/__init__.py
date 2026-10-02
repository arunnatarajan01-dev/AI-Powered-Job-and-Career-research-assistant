"""Independent adapters for authorized job sources."""

from jobs.providers.linkedin import LinkedInProvider
from jobs.providers.naukri import NaukriProvider

__all__ = ["LinkedInProvider", "NaukriProvider"]
