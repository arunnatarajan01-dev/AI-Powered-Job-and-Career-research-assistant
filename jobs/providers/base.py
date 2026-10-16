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


def is_all_locations(query):
    """True for the default filter that keeps every Indian location."""
    return (query or "").strip().lower() in {"all location", "all locations", "india"}


def provider_location(query):
    """Location string sent to a job source. Blank and All location search India."""
    text = (query or "").strip()
    if not text or is_all_locations(text):
        return "India"
    if "india" not in text.lower():
        return f"{text}, India"
    return text


def location_matches(job_location, query):
    """True when the job city matches the searched location, including common aliases."""
    if is_all_locations(query):
        return True
    needle = (query or "").strip().lower()
    needle = re.sub(r",?\s*\bindia\b\s*$", "", needle).strip()
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


_SECTION_LABELS = (
    "Roles & Responsibilities",
    "Roles and Responsibilities",
    "Years of experience",
    "Job match score",
    "Work Experience",
    "Job description",
    "Job highlights",
    "Early Applicant",
    "Employment Type",
    "Industry Type",
    "Role Category",
    "Key Skills",
    "Keyskills",
    "Department",
    "Education",
    "Location",
    "*NOTE*",
    "UG:",
    "PG:",
    "Role:",
)


def _plain_text(value):
    """Turn a description into readable text, including HTML from a provider."""
    text = str(value or "")
    text = re.sub(r"(?i)<\s*br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</\s*(p|div|h[1-6]|li|tr)\s*>", "\n", text)
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
    return "\n".join(line for line in lines if line)[:8000]


_HEADINGS_WITH_BODY = (
    "Job highlights",
    "Job match score",
    "Early Applicant",
    "Keyskills",
    "Key Skills",
    "Work Experience",
    "Job description",
    "Education",
)


def format_job_description(value):
    """Put posting sections and keywords on separate lines with space between them."""
    text = _plain_text(value)
    if not text:
        return ""
    text = re.sub(r",(?=\S)", ", ", text)
    text = re.sub(r"\)\s+(?=[A-Z])", ")\n\n", text)
    for label in _SECTION_LABELS:
        pattern = re.compile(rf"(?<=\S)\s+({re.escape(label)})(?=$|[\s:\-])")
        text = pattern.sub(r"\n\n\1", text)
    for label in _HEADINGS_WITH_BODY:
        pattern = re.compile(rf"({re.escape(label)})[ \t]+(?![-:])(\S)")
        text = pattern.sub(r"\1\n\n\2", text)
    text = re.sub(
        r"(Roles\s*&\s*Responsibilities\s*-)\s+",
        r"\1\n\n",
        text,
        flags=re.IGNORECASE,
    )
    marker = "Roles & Responsibilities"
    split_at = text.find(marker)
    if split_at >= 0:
        head, tail = text[:split_at], text[split_at:]
        tail = re.sub(
            r",\s+(?=(?:UI Automation|API Testing|SoapUI|Cross-browser|Security|Performance)\b)",
            "\n",
            tail,
        )
        text = head + tail
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def experience_bounds(item, description=""):
    """Return the inclusive years a posting asks for, or None when it does not say."""
    if isinstance(item, dict):
        raw_low = item.get("experience_min")
        raw_high = item.get("experience_max")
        if raw_low in (None, ""):
            raw_low = item.get("experienceMin")
            raw_high = item.get("experienceMax")
        if raw_low not in (None, ""):
            try:
                low = int(raw_low)
                high = int(raw_high or low)
            except (TypeError, ValueError):
                low = high = None
            if low is not None:
                return min(low, high), max(low, high)
    text = description or ""
    ranged = re.search(
        r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*\+?\s*(?:years|yrs)",
        text,
        re.IGNORECASE,
    )
    if ranged:
        low, high = int(ranged.group(1)), int(ranged.group(2))
        return min(low, high), max(low, high)
    plus = re.search(r"(\d+)\+\s*(?:years|yrs)", text, re.IGNORECASE)
    if plus:
        return int(plus.group(1)), 25
    single = re.search(r"(\d+)\s*(?:years|yrs)", text, re.IGNORECASE)
    if single:
        year = int(single.group(1))
        return year, year
    return None


def experience_label(bounds):
    if not bounds:
        return ""
    low, high = bounds
    if low == high:
        return f"{low} yrs"
    return f"{low} - {high} yrs"


def _workplace_blob(item, description=""):
    if not isinstance(item, dict):
        return str(description or "").lower()
    return " ".join(
        str(part or "")
        for part in (
            item.get("location"),
            item.get("title"),
            item.get("employment_type"),
            item.get("employmentType"),
            item.get("workplaceType"),
            item.get("workType"),
            item.get("workMode"),
            description,
        )
    ).lower()


def is_remote_job(item, description=""):
    if isinstance(item, dict) and item.get("remote") in (True, "true", "yes", 1, "1"):
        return True
    blob = _workplace_blob(item, description)
    return any(token in blob for token in ("remote", "work from home", "work-from-home", "wfh"))


def is_hybrid_job(item, description=""):
    if isinstance(item, dict) and str(item.get("workplaceType") or item.get("workMode") or "").lower() == "hybrid":
        return True
    return bool(re.search(r"\bhybrid\b", _workplace_blob(item, description)))


def posting_text(description, location, years_label):
    """Keep a structured posting as-is. Give short snippets the same section spacing."""
    formatted = format_job_description(description)
    if re.search(r"job highlights|job description", formatted, re.IGNORECASE):
        return formatted
    parts = ["Job highlights", formatted or "Details were not included in this posting."]
    if years_label:
        parts.extend(["", "Work Experience", years_label])
    if location:
        parts.extend(["", "Location", location])
    parts.extend(["", "Job description", formatted or "Details were not included in this posting."])
    return "\n".join(parts)


_JOB_BOARDS = (
    "linkedin.com",
    "naukri.com",
    "indeed.com",
    "foundit.in",
    "mployee.me",
    "shine.com",
    "glassdoor.",
)

# Career sites for companies in the local catalogs, plus common employers.
COMPANY_CAREER_PAGES = {
    "kaveri digital": "https://www.naukri.com/kaveri-digital-jobs",
    "metrostack": "https://www.naukri.com/metrostack-jobs",
    "deccan soft": "https://www.naukri.com/deccan-soft-jobs",
    "westline": "https://www.naukri.com/westline-jobs",
    "northwind analytics": "https://www.linkedin.com/jobs/search/?keywords=Northwind%20Analytics",
    "harbor systems": "https://www.linkedin.com/jobs/search/?keywords=Harbor%20Systems",
    "lattice works": "https://www.linkedin.com/jobs/search/?keywords=Lattice%20Works",
    "bluepeak": "https://www.linkedin.com/jobs/search/?keywords=Bluepeak",
    "indus cloud": "https://www.linkedin.com/jobs/search/?keywords=Indus%20Cloud",
    "sable labs": "https://www.linkedin.com/jobs/search/?keywords=Sable%20Labs",
    "rivermark": "https://in.indeed.com/jobs?q=Rivermark&l=Bengaluru",
    "coral bay": "https://in.indeed.com/jobs?q=Coral%20Bay&l=Mumbai",
    "nimbus grid": "https://in.indeed.com/jobs?q=Nimbus%20Grid&l=Hyderabad",
    "paperlane": "https://in.indeed.com/jobs?q=Paperlane&l=Pune",
    "aster peak": "https://www.foundit.in/search/aster-peak-jobs",
    "saffron labs": "https://www.foundit.in/search/saffron-labs-jobs",
    "monsoon systems": "https://www.foundit.in/search/monsoon-systems-jobs",
    "brightpath": "https://www.mployee.me/job-match-pro",
    "koel systems": "https://www.mployee.me/job-match-pro",
    "fieldnote": "https://www.mployee.me/job-match-pro",
    "google": "https://www.google.com/about/careers/applications/",
    "meta": "https://www.metacareers.com/jobs",
    "microsoft": "https://careers.microsoft.com/",
    "amazon": "https://www.amazon.jobs/",
    "netflix": "https://jobs.netflix.com/",
    "adobe": "https://careers.adobe.com/",
    "ibm": "https://www.ibm.com/careers",
    "oracle": "https://careers.oracle.com/",
    "uber": "https://www.uber.com/us/en/careers/",
    "spotify": "https://www.lifeatspotify.com/jobs",
    "salesforce": "https://careers.salesforce.com/en/jobs/",
    "tesla": "https://www.tesla.com/careers",
    "airbnb": "https://careers.airbnb.com/",
}


def _http_url(value):
    text = str(value or "").strip()
    if text.startswith("//"):
        text = "https:" + text
    if text.lower().startswith(("http://", "https://")):
        return text
    return ""


def _is_job_board(url):
    host = url.lower()
    return any(token in host for token in _JOB_BOARDS)


def _company_page(url):
    """Keep a company career page. Skip a single job posting."""
    url = _http_url(url)
    if not url:
        return ""
    lower = url.lower()
    if not _is_job_board(url):
        base = url.rstrip("/")
        if re.search(r"/(careers|jobs|career)(/|$)", lower):
            return base
        return base + "/careers"
    if "jobs-careers" in lower or re.search(r"/careers(/|$)", lower):
        return url.split("?")[0]
    if "linkedin.com/company/" in lower:
        base = url.split("?")[0].rstrip("/")
        if not base.endswith("/jobs"):
            return base + "/jobs"
        return base
    return ""


def _known_career_page(company):
    name = re.sub(r"\s+", " ", str(company or "").strip().lower())
    if not name:
        return ""
    direct = COMPANY_CAREER_PAGES.get(name)
    if direct:
        return direct
    for key, url in COMPANY_CAREER_PAGES.items():
        if len(key) >= 4 and re.search(rf"\b{re.escape(key)}\b", name):
            return url
    return ""


def career_page_url(item, company):
    """Company career page when the posting or a known employer site has one."""
    if not isinstance(item, dict):
        item = {}
    for key in (
        "career_url",
        "careerUrl",
        "companyCareersUrl",
        "careersUrl",
        "companyUrl",
        "company_url",
        "companyWebsite",
        "company_website",
        "companyLinkedinUrl",
        "website",
    ):
        page = _company_page(item.get(key))
        if page:
            return page
    nested = item.get("company")
    if isinstance(nested, dict):
        for key in ("careerUrl", "companyUrl", "url", "website"):
            page = _company_page(nested.get(key))
            if page:
                return page
    for key in ("applyUrl", "externalApplyLink", "apply_url", "externalApplyUrl"):
        url = _http_url(item.get(key))
        if url and not _is_job_board(url):
            return url
    return _known_career_page(company)


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
    return format_job_description(raw)


def _employment_type(item):
    employment = (
        item.get("employment_type")
        or item.get("employmentType")
        or item.get("contractType")
    )
    if not employment and isinstance(item.get("employmentTypes"), list):
        employment = ", ".join(str(part) for part in item["employmentTypes"] if part)
    return str(employment or "Full-time").strip()


def _normalize(raw, provider_key):
    jobs = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        company = item.get("company") or item.get("companyName") or "Unknown company"
        location = _location_text(item).strip()
        description = _description_text(item)
        bounds = experience_bounds(item, description)
        years_label = experience_label(bounds)
        jobs.append({
            "id": str(item.get("id") or item.get("jobId") or title),
            "title": title,
            "company": str(company).strip(),
            "location": location,
            "posted_days_ago": _posted_days_ago(item),
            "employment_type": _employment_type(item),
            "description": posting_text(description, location, years_label),
            "experience_min": bounds[0] if bounds else None,
            "experience_max": bounds[1] if bounds else None,
            "experience_label": years_label,
            "remote": is_remote_job(item, description),
            "hybrid": is_hybrid_job(item, description),
            "provider": provider_key,
            "career_url": career_page_url(item, company),
        })
    return jobs


def apply_search_filters(jobs, experience=None, remote_only=False, work_mode=None):
    """Keep jobs that fit the selected years, work mode, and remote-only choice."""
    mode = (work_mode or "").strip().lower()
    selected = []
    for job in jobs:
        if remote_only and not job.get("remote"):
            continue
        if mode == "remote" and not job.get("remote"):
            continue
        if mode == "hybrid" and not job.get("hybrid"):
            continue
        if mode == "onsite" and (job.get("remote") or job.get("hybrid")):
            continue
        if experience is not None:
            low = job.get("experience_min")
            high = job.get("experience_max")
            if low is None or high is None or not (low <= experience <= high):
                continue
        selected.append(job)
    return selected


def _filter_jobs(jobs, location, posted_within):
    return [
        job for job in jobs
        if location_matches(job["location"], location) and within_window(job["posted_days_ago"], posted_within)
    ]


def apify_job_limit():
    """Cap live provider results. APIFY_JOB_LIMIT stays between 1 and 50."""
    limit = os.getenv("APIFY_JOB_LIMIT", "15").strip() or "15"
    try:
        return max(1, min(int(limit), 50))
    except ValueError:
        return 15


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
                raw = run_actor(
                    self.actor_id(),
                    self.build_input(provider_location(location), posted_within, keyword),
                    token,
                )
                jobs = [
                    job for job in _normalize(raw, self.key)
                    if location_matches(job["location"], location)
                ]
                return {
                    "provider": self.key,
                    "label": self.label,
                    "mode": "apify",
                    "message": f"Results from the {self.label} Apify Actor {self.actor_id()}.",
                    "jobs": jobs,
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
