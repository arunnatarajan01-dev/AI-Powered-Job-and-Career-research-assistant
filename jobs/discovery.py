"""Run the selected provider adapters for one location and date window."""

from jobs.providers.base import POSTED_WINDOWS, apply_search_filters
from jobs.providers.foundit import FounditProvider
from jobs.providers.indeed import IndeedProvider
from jobs.providers.job_match_pro import JobMatchProProvider
from jobs.providers.linkedin import LinkedInProvider
from jobs.providers.naukri import NaukriProvider

PROVIDER_OPTIONS = (
    ("naukri", "Naukri"),
    ("linkedin", "LinkedIn"),
    ("indeed", "Indeed"),
    ("job_match_pro", "Job Match Pro"),
    ("foundit", "Foundit"),
)

PROVIDERS = {
    "naukri": NaukriProvider(),
    "linkedin": LinkedInProvider(),
    "indeed": IndeedProvider(),
    "job_match_pro": JobMatchProProvider(),
    "foundit": FounditProvider(),
}

POSTED_LABELS = (
    ("today", "Today"),
    ("week", "Last week"),
    ("month", "Last month"),
)

CITIES = (
    {"name": "Bengaluru", "lat": 12.9716, "lng": 77.5946},
    {"name": "Hyderabad", "lat": 17.3850, "lng": 78.4867},
    {"name": "Pune", "lat": 18.5204, "lng": 73.8567},
    {"name": "Mumbai", "lat": 19.0760, "lng": 72.8777},
    {"name": "Delhi", "lat": 28.6139, "lng": 77.2090},
    {"name": "Chennai", "lat": 13.0827, "lng": 80.2707},
    {"name": "Kolkata", "lat": 22.5726, "lng": 88.3639},
    {"name": "Ahmedabad", "lat": 23.0225, "lng": 72.5714},
    {"name": "Jaipur", "lat": 26.9124, "lng": 75.7873},
    {"name": "Noida", "lat": 28.5355, "lng": 77.3910},
)


WORK_MODES = ("remote", "hybrid", "onsite")


def parse_work_mode(value):
    """Return remote, hybrid, or onsite, or blank when the filter is not set."""
    text = str(value or "").strip().lower()
    if text in WORK_MODES:
        return text
    return ""


def parse_experience(value):
    """Return a year from 1 to 25, or None when the filter is not set."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        years = int(text)
    except ValueError:
        return None
    if 1 <= years <= 25:
        return years
    return None


def _provider_rank(provider):
    """Keep provider results in the same order as the jobs page."""
    order = [key for key, _label in PROVIDER_OPTIONS]
    try:
        return order.index(provider.key)
    except ValueError:
        return len(order)


def discover(
    provider_keys,
    location,
    posted_within,
    keyword="software engineer",
    experience=None,
    remote_only=False,
    work_mode=None,
):
    """Search each requested adapter. Unknown keys are skipped."""
    if posted_within not in POSTED_WINDOWS:
        posted_within = "week"
    role = (keyword or "software engineer").strip() or "software engineer"
    selected = []
    for key in provider_keys:
        provider = PROVIDERS.get(key)
        if provider is not None and provider not in selected:
            selected.append(provider)
    selected.sort(key=_provider_rank)
    bundles = [provider.search(location, posted_within, role) for provider in selected]
    for bundle in bundles:
        bundle["jobs"] = apply_search_filters(
            bundle.get("jobs") or [],
            experience=experience,
            remote_only=remote_only,
            work_mode=work_mode,
        )
    return bundles
