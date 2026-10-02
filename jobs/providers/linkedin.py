"""LinkedIn job-source adapter. Runs through Apify."""

import os

from jobs.providers.base import CatalogProvider

DATE_POSTED = {
    "today": "r86400",
    "week": "r604800",
    "month": "r2592000",
}


class LinkedInProvider(CatalogProvider):
    key = "linkedin"
    label = "LinkedIn"
    catalog_name = "linkedin.json"
    actor_env = "LINKEDIN_APIFY_ACTOR"
    default_actor = "valig/linkedin-jobs-scraper"

    def build_input(self, location, posted_within, keyword):
        limit = os.getenv("APIFY_JOB_LIMIT", "15").strip() or "15"
        try:
            max_items = max(1, min(int(limit), 50))
        except ValueError:
            max_items = 15
        return {
            "keywords": keyword or "software engineer",
            "location": location,
            "datePosted": DATE_POSTED.get(posted_within, "r604800"),
            "limit": max_items,
        }
