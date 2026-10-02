"""Naukri job-source adapter. Runs through Apify."""

import os

from jobs.providers.base import CatalogProvider

FRESHNESS = {
    "today": "1d",
    "week": "7d",
    "month": "30d",
}


class NaukriProvider(CatalogProvider):
    key = "naukri"
    label = "Naukri"
    catalog_name = "naukri.json"
    actor_env = "NAUKRI_APIFY_ACTOR"
    default_actor = "k1ra/naukri-jobs-scraper"

    def build_input(self, location, posted_within, keyword):
        limit = os.getenv("APIFY_JOB_LIMIT", "15").strip() or "15"
        try:
            max_items = max(1, min(int(limit), 50))
        except ValueError:
            max_items = 15
        return {
            "keywords": keyword or "software engineer",
            "location": location,
            "platform": "naukri",
            "freshness": FRESHNESS.get(posted_within, "7d"),
            "maxResults": max_items,
            "includeDescription": True,
        }
