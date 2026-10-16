"""Application counts kept with each candidate resume in long-term memory."""

import json
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from memory.pinecone_memory import scan_id_for

_ZONE = ZoneInfo("Asia/Kolkata")
_LOCK = threading.Lock()
_STORE = Path(__file__).resolve().parent.parent / "data" / "long_term" / "applications"


def _today():
    return datetime.now(_ZONE).date()


def _path(email, candidate):
    vector_id = scan_id_for(email, candidate)
    if not vector_id:
        return None
    return _STORE / f"{vector_id}.json"


def _read(email, candidate):
    path = _path(email, candidate)
    if path is None or not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    dates = payload.get("applied_on") if isinstance(payload, dict) else None
    if not isinstance(dates, list):
        return []
    return [str(item) for item in dates if item]


def _write(email, candidate, resume, applied_on):
    path = _path(email, candidate)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "candidate": candidate,
                "resume": resume or "",
                "applied_on": applied_on[-500:],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def application_counts(email, candidate, today=None):
    """Counts for today, yesterday, and the seven days before yesterday."""
    day = today or _today()
    yesterday = day - timedelta(days=1)
    week_start = day - timedelta(days=8)
    week_end = day - timedelta(days=2)
    counts = {"today": 0, "yesterday": 0, "last_week": 0}
    if not (email and candidate):
        return counts
    with _LOCK:
        applied_on = _read(email, candidate)
    for item in applied_on:
        try:
            applied = date.fromisoformat(item)
        except ValueError:
            continue
        if applied == day:
            counts["today"] += 1
        elif applied == yesterday:
            counts["yesterday"] += 1
        elif week_start <= applied <= week_end:
            counts["last_week"] += 1
    return counts


def record_application(email, candidate, resume="", on_date=None):
    """Store one Apply click for this candidate resume and return the new counts."""
    if not (email and candidate):
        return application_counts(email, candidate)
    day = on_date or _today()
    with _LOCK:
        applied_on = _read(email, candidate)
        applied_on.append(day.isoformat())
        _write(email, candidate, resume, applied_on)
    return application_counts(email, candidate)
