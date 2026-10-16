"""Foundit job-source adapter. Runs through Apify, then the local catalog."""

from jobs.providers.base import CatalogProvider, apify_job_limit

POSTED_DAYS = {
    "today": 1,
    "week": 7,
    "month": 30,
}


class FounditProvider(CatalogProvider):
    key = "foundit"
    label = "Foundit"
    catalog_name = "foundit.json"
    actor_env = "FOUNDIT_APIFY_ACTOR"
    default_actor = "memo23/foundit-jobs-scraper"

    def build_input(self, location, posted_within, keyword):
        return {
            "searchKeywords": keyword or "software engineer",
            "location": location,
            "country": "India",
            "postedWithinDays": POSTED_DAYS.get(posted_within, 7),
            "fetchDescriptions": True,
            "maxItems": apify_job_limit(),
        }
