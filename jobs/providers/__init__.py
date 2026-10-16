"""Independent adapters for authorized job sources."""

from jobs.providers.foundit import FounditProvider
from jobs.providers.indeed import IndeedProvider
from jobs.providers.job_match_pro import JobMatchProProvider
from jobs.providers.linkedin import LinkedInProvider
from jobs.providers.naukri import NaukriProvider

__all__ = [
    "FounditProvider",
    "IndeedProvider",
    "JobMatchProProvider",
    "LinkedInProvider",
    "NaukriProvider",
]
