"""Append-only traces for each agent step."""

import json
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "traces.jsonl"
_LOCK = threading.Lock()
_MAX_LINES = 400
_DROP_KEYS = {
    "password",
    "prompt",
    "document_text",
    "text",
    "excerpt",
    "raw_text",
    "token",
    "api_key",
}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _clean(value, depth=0):
    if depth > 2:
        return "..."
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in _DROP_KEYS:
                continue
            cleaned[str(key)] = _clean(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_clean(item, depth + 1) for item in list(value)[:8]]
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return value
    text = str(value)
    if len(text) <= 160:
        return text
    return text[:160] + "..."


class Trace:
    def __init__(self, name, actor, route, meta):
        self.id = uuid.uuid4().hex[:12]
        self.name = name
        self.actor = actor or "anonymous"
        self.route = route or ""
        self.meta = _clean(meta or {})
        self.started = time.perf_counter()
        self.started_at = _now()
        self.spans = []
        self.status = "ok"
        self.error = None

    @contextmanager
    def span(self, name, **attributes):
        started = time.perf_counter()
        record = {
            "name": name,
            "status": "ok",
            "attributes": _clean(attributes),
            "error": "",
        }
        try:
            yield record
        except Exception as exc:
            record["status"] = "error"
            record["error"] = str(exc)[:300]
            self.status = "error"
            self.error = record["error"]
            raise
        finally:
            record["duration_ms"] = round((time.perf_counter() - started) * 1000, 1)
            self.spans.append(record)

    def finish(self):
        if self.status == "ok":
            if any(span["status"] == "error" for span in self.spans):
                self.status = "error"
            elif any(span["status"] == "blocked" for span in self.spans):
                self.status = "blocked"
        record = {
            "trace_id": self.id,
            "name": self.name,
            "actor": self.actor,
            "route": self.route,
            "started_at": self.started_at,
            "duration_ms": round((time.perf_counter() - self.started) * 1000, 1),
            "status": self.status,
            "error": self.error or "",
            "meta": self.meta,
            "spans": self.spans,
        }
        _append(record)
        return record


@contextmanager
def trace(name, actor="", route="", **meta):
    """Record one request. Spans added on the yielded trace are stored when it ends."""
    current = Trace(name, actor, route, meta)
    try:
        yield current
    except Exception as exc:
        current.status = "error"
        current.error = str(exc)[:300]
        raise
    finally:
        current.finish()


def _append(record):
    line = json.dumps(record, ensure_ascii=False)
    with _LOCK:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if LOG_PATH.exists():
            existing = [
                item for item in LOG_PATH.read_text(encoding="utf-8").splitlines() if item.strip()
            ]
        existing.append(line)
        LOG_PATH.write_text("\n".join(existing[-_MAX_LINES:]) + "\n", encoding="utf-8")


def _load():
    if not LOG_PATH.exists():
        return []
    rows = []
    with _LOCK:
        raw = LOG_PATH.read_text(encoding="utf-8").splitlines()
    for line in raw:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.reverse()
    return rows


def _span_line(span):
    parts = [
        span.get("name") or "step",
        span.get("status") or "ok",
        f"{span.get('duration_ms', 0)} ms",
    ]
    attributes = span.get("attributes") or {}
    for key, value in attributes.items():
        parts.append(f"{key}={value}")
    if span.get("error"):
        parts.append(span["error"])
    return " · ".join(str(part) for part in parts)


def recent_traces(limit=25):
    """Newest traces first, with a one-line label for each span."""
    prepared = []
    for row in _load()[:limit]:
        item = dict(row)
        item["span_lines"] = [_span_line(span) for span in row.get("spans") or []]
        prepared.append(item)
    return prepared


def trace_summary():
    rows = _load()
    count = len(rows)
    errors = sum(1 for row in rows if row.get("status") == "error")
    blocked = sum(1 for row in rows if row.get("status") == "blocked")
    durations = [row.get("duration_ms") or 0 for row in rows]
    mean = round(sum(durations) / count, 1) if count else 0
    return {
        "count": count,
        "errors": errors,
        "blocked": blocked,
        "ok": count - errors - blocked,
        "mean_ms": mean,
    }
