"""Call an Apify Actor with the account API token. The token is never logged."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APIFY_RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def apify_token():
    """Return a usable token, ignoring empty and placeholder values."""
    value = os.getenv("APIFY_API_TOKEN", "").strip()
    if not value or value.startswith("your_"):
        return ""
    return value


def run_actor(actor_id, payload, token, timeout=180):
    """Run an Actor synchronously and return its dataset items."""
    actor = actor_id.strip().replace("/", "~")
    if not actor:
        raise ValueError("Apify actor id is missing.")
    request = Request(
        APIFY_RUN_URL.format(actor=actor) + f"?timeout={timeout}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:180]
        raise RuntimeError(f"Apify returned HTTP {exc.code}. {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Apify request failed: {exc.reason}") from exc
    if isinstance(body, dict):
        body = body.get("items") or body.get("data") or []
    if not isinstance(body, list):
        raise RuntimeError("Apify did not return a list of jobs.")
    return body
