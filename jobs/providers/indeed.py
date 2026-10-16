"""Indeed job-source adapter. Runs through Apify, then the local catalog."""

from jobs.providers.base import CatalogProvider, apify_job_limit

DATE_POSTED = {
    "today": "1",
    "week": "7",
    "month": "30",
}


class IndeedProvider(CatalogProvider):
    key = "indeed"
    label = "Indeed"
    catalog_name = "indeed.json"
    actor_env = "INDEED_APIFY_ACTOR"
    default_actor = "jobsapi/indeed-jobs-search-scraper"

    def build_input(self, location, posted_within, keyword):
        return {
            "mode": "search",
            "keywords": keyword or "software engineer",
            "country": "in",
            "location": location,
            "maxItems": apify_job_limit(),
            "maxPages": 1,
            "includeDetails": True,
            "datePosted": DATE_POSTED.get(posted_within, "7"),
        }
