"""Job Match Pro adapter. Uses a live Actor only when one is configured."""

import os

from jobs.providers.base import CatalogProvider, apify_job_limit, apify_token


class JobMatchProProvider(CatalogProvider):
    key = "job_match_pro"
    label = "Job Match Pro"
    catalog_name = "job_match_pro.json"
    actor_env = "JOB_MATCH_PRO_APIFY_ACTOR"
    default_actor = ""

    def build_input(self, location, posted_within, keyword):
        return {
            "keywords": keyword or "software engineer",
            "location": location,
            "postedWithin": posted_within,
            "maxResults": apify_job_limit(),
        }

    def search(self, location, posted_within, keyword="software engineer"):
        if apify_token() and os.getenv(self.actor_env, "").strip():
            return super().search(location, posted_within, keyword)
        catalog = self._from_catalog(location, posted_within)
        catalog["message"] = (
            f"{self.label} is using its local catalog. Set APIFY_API_TOKEN and "
            f"{self.actor_env} to run a live Actor."
        )
        return catalog
