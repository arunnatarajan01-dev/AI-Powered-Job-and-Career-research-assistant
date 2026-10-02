"""Shared contract for authorized job-source adapters."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from jobs.providers.apify_client import apify_token, run_actor

POSTED_WINDOWS = {
    "today": 0,
    "week": 7,
    "month": 30,
}

LOCATION_ALIASES = {
    "bengaluru": {"bengaluru", "bangalore"},
    "bangalore": {"bengaluru", "bangalore"},
    "mumbai": {"mumbai", "bombay"},
    "bombay": {"mumbai", "bombay"},
    "gurugram": {"gurugram", "gurgaon"},
    "gurgaon": {"gurugram", "gurgaon"},
    "delhi": {"delhi", "new delhi"},
    "new delhi": {"delhi", "new delhi"},
}

CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "job_feeds"


def location_matches(job_location, query):
    """True when the job city matches the searched location, including common aliases."""
    needle = (query or "").strip().lower()
    haystack = (job_location or "").strip().lower()
    if not needle or not haystack:
        return False
    names = set(LOCATION_ALIASES.get(needle, set()))
    names.add(needle)
    for token in needle.replace(",", " ").split():
        if len(token) < 3:
            continue
        names.update(LOCATION_ALIASES.get(token, set()))
        names.add(token)
    return any(name in haystack for name in names)


def within_window(days_ago, posted_within):
    limit = POSTED_WINDOWS.get(posted_within)
    if limit is None:
        return False
    try:
        age = int(days_ago)
    except (TypeError, ValueError):
        return False
    return 0 <= age <= limit


def _posted_days_ago(item):
    if "posted_days_ago" in item and item["posted_days_ago"] is not None:
        try:
            return int(item["posted_days_ago"])
        except (TypeError, ValueError):
            pass
    raw = (
        item.get("postedAt")
        or item.get("postedTimeAgo")
        or item.get("postedAgo")
        or item.get("datePosted")
        or item.get("postedDate")
        or ""
    )
    if isinstance(raw, (int, float)):
        return int(raw)
    text = str(raw).strip()
    if not text:
        return 0
    if text.lower() in {"today", "just now"} or "hour" in text.lower():
        return 0
    match = re.search(r"(\d+)\s*day", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - parsed).days)
    except ValueError:
        return 0


def _location_text(item):
    location = item.get("location") or ""
    if isinstance(location, list):
        return ", ".join(str(part) for part in location if part)
    if isinstance(location, dict):
        return location.get("linkedinText") or location.get("parsed") or ""
    if location:
        return str(location)
    places = item.get("locations") or []
    if isinstance(places, list):
        return ", ".join(str(part) for part in places if part)
    return ""


def _plain_text(value):
    """Turn a description into readable text, including HTML from a provider."""
    text = str(value or "")
    text = re.sub(r"(?i)<\s*br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</\s*p\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*li\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)[:6000]


def _description_text(item):
    raw = (
        item.get("description")
        or item.get("jobDescription")
        or item.get("descriptionText")
        or item.get("descriptionHtml")
        or item.get("descriptionSnippet")
        or item.get("snippet")
        or ""
    )
    return _plain_text(raw)


def _normalize(raw, provider_key):
    jobs = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        company = item.get("company") or item.get("companyName") or "Unknown company"
        description = _description_text(item)
        jobs.append({
            "id": str(item.get("id") or item.get("jobId") or title),
            "title": title,
            "company": str(company).strip(),
            "location": _location_text(item).strip(),
            "posted_days_ago": _posted_days_ago(item),
            "employment_type": str(
                item.get("employment_type")
                or item.get("employmentType")
                or item.get("contractType")
                or "Full-time"
            ).strip(),
            "description": description,
            "provider": provider_key,
        })
    return jobs


def _filter_jobs(jobs, location, posted_within):
    return [
        job for job in jobs
        if location_matches(job["location"], location) and within_window(job["posted_days_ago"], posted_within)
    ]


class CatalogProvider:
    """One job source. Live results run that source's Apify Actor."""

    key = ""
    label = ""
    catalog_name = ""
    actor_env = ""
    default_actor = ""

    def actor_id(self):
        return os.getenv(self.actor_env, self.default_actor).strip() or self.default_actor

    def build_input(self, location, posted_within, keyword):
        raise NotImplementedError

    def search(self, location, posted_within, keyword="software engineer"):
        token = apify_token()
        if token:
            try:
                raw = run_actor(self.actor_id(), self.build_input(location, posted_within, keyword), token)
                return {
                    "provider": self.key,
                    "label": self.label,
                    "mode": "apify",
                    "message": f"Results from the {self.label} Apify Actor {self.actor_id()}.",
                    "jobs": _normalize(raw, self.key),
                }
            except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
                catalog = self._from_catalog(location, posted_within)
                catalog["message"] = (
                    f"The {self.label} Apify run failed ({exc}). "
                    "Showing the local catalog for this location and date."
                )
                return catalog
        catalog = self._from_catalog(location, posted_within)
        catalog["message"] = (
            f"{self.label} is using its local catalog. Set APIFY_API_TOKEN to run the "
            f"{self.actor_id()} Actor."
        )
        return catalog

    def _from_catalog(self, location, posted_within):
        path = CATALOG_DIR / self.catalog_name
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            "provider": self.key,
            "label": self.label,
            "mode": "local_catalog",
            "message": "",
            "jobs": _filter_jobs(_normalize(raw, self.key), location, posted_within),
        }
