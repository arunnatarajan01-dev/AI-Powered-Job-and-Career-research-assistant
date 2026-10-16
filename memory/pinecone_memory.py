"""Long-term resume memory.

Each signed-in account can keep one scan per candidate name. Scanning that
name again replaces the stored result. The embedding lives in Pinecone.
"""

import base64
import gzip
import hashlib
import json
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_DIMENSION = 384
_NAMESPACE = "scans"
_PAYLOAD_LIMIT = 30000
_DIR = Path(__file__).resolve().parent.parent / "data" / "long_term"
_ACCOUNTS = _DIR / "accounts"
_index = None
_index_ready = False
_LOCK = threading.Lock()


def vector_id_for(email):
    """Stable id for the account index."""
    normalized = (email or "").strip().lower()
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _name_key(name):
    collapsed = " ".join((name or "").strip().lower().split())
    return collapsed or "unknown candidate"


def scan_id_for(email, candidate_name):
    """One vector id per account and candidate. The same name overwrites that vector."""
    account = (email or "").strip().lower()
    if not account:
        return ""
    return hashlib.sha256(f"{account}|{_name_key(candidate_name)}".encode("utf-8")).hexdigest()


def save_user_scan(email, result):
    """Store this scan under the candidate name, replacing an older scan of that name."""
    account = (email or "").strip().lower()
    if not account or not result:
        return ""
    display = (result.get("candidate_name") or "").strip() or "Unknown candidate"
    stored = dict(result)
    stored["candidate_name"] = display
    vector_id = scan_id_for(account, display)
    key = _name_key(display)
    scanned_at = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        _migrate_legacy(account)
        _write_local(vector_id, stored)
        catalog = _read_index(account)
        catalog["candidates"][key] = {
            "name": display,
            "vector_id": vector_id,
            "scanned_at": scanned_at,
        }
        catalog["latest"] = key
        _write_index(account, catalog)
    try:
        _upsert(vector_id, account, stored)
    except Exception as exc:
        print(f"Warning: Pinecone long-term memory was not updated: {exc}")
    return vector_id


def list_candidates(email):
    """Candidate names stored for this account, in alphabetical order."""
    account = (email or "").strip().lower()
    if not account:
        return []
    with _LOCK:
        _migrate_legacy(account)
        catalog = _read_index(account)
    rows = list(catalog["candidates"].values())
    rows.sort(key=lambda row: (row.get("name") or "").lower())
    return rows


def load_user_scan(email, candidate_name=None):
    """Return one stored scan. With no name, return the most recent scan."""
    account = (email or "").strip().lower()
    if not account:
        return None
    with _LOCK:
        _migrate_legacy(account)
        entry = _entry_for(account, candidate_name)
    if not entry:
        return None
    local = _read_local(entry["vector_id"])
    if local is not None:
        return local
    try:
        restored = _fetch_payload(entry["vector_id"])
    except Exception as exc:
        print(f"Warning: Pinecone long-term memory could not be read: {exc}")
        return None
    if restored is not None:
        _write_local(entry["vector_id"], restored)
    return restored


def load_candidate_scan(email, candidate_name):
    """Return the scan stored for this candidate name."""
    if not (candidate_name or "").strip():
        return None
    return load_user_scan(email, candidate_name)


def delete_candidate_scan(email, candidate_name):
    """Remove one candidate's scan. Returns True when a record was deleted."""
    account = (email or "").strip().lower()
    key = _name_key(candidate_name)
    if not account or not key:
        return False
    with _LOCK:
        _migrate_legacy(account)
        catalog = _read_index(account)
        found_key, entry = _match_entry(catalog, key, candidate_name)
        if entry is None:
            return False
        catalog["candidates"].pop(found_key, None)
        if catalog.get("latest") == found_key:
            if catalog["candidates"]:
                catalog["latest"] = max(
                    catalog["candidates"],
                    key=lambda item: catalog["candidates"][item].get("scanned_at") or "",
                )
            else:
                catalog["latest"] = ""
        _write_index(account, catalog)
        path = _DIR / f"{entry['vector_id']}.json"
        if path.exists():
            path.unlink()
        vector_id = entry["vector_id"]
    try:
        _delete_vector(vector_id)
    except Exception as exc:
        print(f"Warning: Pinecone scan could not be deleted: {exc}")
    return True


def _match_entry(catalog, key, candidate_name):
    candidates = catalog["candidates"]
    if key in candidates:
        return key, candidates[key]
    asked = (candidate_name or "").strip().lower()
    for item_key, row in candidates.items():
        if (row.get("name") or "").strip().lower() == asked or _name_key(row.get("name")) == key:
            return item_key, row
    return None, None


def _entry_for(account, candidate_name):
    catalog = _read_index(account)
    if candidate_name:
        _key, entry = _match_entry(catalog, _name_key(candidate_name), candidate_name)
        return entry
    latest = catalog["candidates"].get(catalog.get("latest") or "")
    if latest:
        return latest
    if not catalog["candidates"]:
        return None
    return max(catalog["candidates"].values(), key=lambda row: row.get("scanned_at") or "")


def _index_path(email):
    return _ACCOUNTS / f"{vector_id_for(email)}.json"


def _empty_index():
    return {"latest": "", "candidates": {}}


def _read_index(email):
    path = _index_path(email)
    if not path.exists():
        return _empty_index()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_index()
    if not isinstance(data, dict):
        return _empty_index()
    data.setdefault("latest", "")
    if not isinstance(data.get("candidates"), dict):
        data["candidates"] = {}
    return data


def _write_index(email, catalog):
    _ACCOUNTS.mkdir(parents=True, exist_ok=True)
    _index_path(email).write_text(json.dumps(catalog), encoding="utf-8")


def _migrate_legacy(email):
    """Move the older one-scan file into the candidate catalog."""
    if _index_path(email).exists():
        return
    legacy_id = vector_id_for(email)
    legacy = _read_local(legacy_id)
    if not legacy:
        return
    display = (legacy.get("candidate_name") or "").strip() or "Unknown candidate"
    vector_id = scan_id_for(email, display)
    if vector_id != legacy_id:
        _write_local(vector_id, legacy)
        legacy_path = _DIR / f"{legacy_id}.json"
        if legacy_path.exists():
            legacy_path.unlink()
    _write_index(email, {
        "latest": _name_key(display),
        "candidates": {
            _name_key(display): {
                "name": display,
                "vector_id": vector_id,
                "scanned_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    })


def _write_local(vector_id, result):
    _DIR.mkdir(parents=True, exist_ok=True)
    path = _DIR / f"{vector_id}.json"
    path.write_text(json.dumps(result, default=str), encoding="utf-8")


def _read_local(vector_id):
    path = _DIR / f"{vector_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: stored resume scan could not be read: {exc}")
        return None
    return data if isinstance(data, dict) else None


def _profile_text(result):
    skills = ", ".join(result.get("skill_names") or [])
    summary = result.get("summary") or ""
    excerpt = result.get("experience_excerpt") or ""
    name = result.get("candidate_name") or ""
    return f"{name}. Skills: {skills}. {summary} {excerpt}"[:4000]


def _embed(text):
    """Use the loaded matcher when it is ready. Do not block the scan on a model download."""
    from models import bert_matcher

    model = bert_matcher._model
    if model and model != "FALLBACK":
        values = model.encode([text or ""], show_progress_bar=False)[0]
        vector = [float(item) for item in values]
        if len(vector) == _DIMENSION:
            return vector
    return _hash_embed(text)


def _hash_embed(text):
    digest = hashlib.sha256((text or "").encode("utf-8")).digest()
    raw = []
    while len(raw) < _DIMENSION:
        digest = hashlib.sha256(digest).digest()
        raw.extend(digest)
    vector = [(byte - 128) / 128 for byte in raw[:_DIMENSION]]
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _pack(result):
    """Gzip the dashboard fields so they can ride in Pinecone metadata."""
    body = {
        key: value
        for key, value in result.items()
        if key not in ("resume_text", "sections")
    }
    encoded = base64.b64encode(
        gzip.compress(json.dumps(body, default=str).encode("utf-8"))
    ).decode("ascii")
    if len(encoded) > _PAYLOAD_LIMIT:
        return ""
    return encoded


def _unpack(payload):
    if not payload:
        return None
    try:
        data = json.loads(gzip.decompress(base64.b64decode(payload)).decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _pinecone_key():
    return os.getenv("PINECONE_API_KEY", "").strip()


def _index_client():
    global _index, _index_ready
    if _index_ready:
        return _index
    key = _pinecone_key()
    if not key:
        return None
    from pinecone import Pinecone, ServerlessSpec

    name = os.getenv("PINECONE_INDEX", "resume-scans").strip() or "resume-scans"
    pc = Pinecone(api_key=key)
    if not pc.has_index(name):
        pc.create_index(
            name=name,
            dimension=_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=os.getenv("PINECONE_CLOUD", "aws"),
                region=os.getenv("PINECONE_REGION", "us-east-1"),
            ),
            timeout=20,
        )
    _index = pc.Index(name)
    _index_ready = True
    return _index


def _upsert(vector_id, email, result):
    index = _index_client()
    if index is None:
        print("Pinecone is not configured. Set PINECONE_API_KEY to store persistent embeddings.")
        return
    metadata = {
        "email": email,
        "filename": (result.get("filename") or "")[:200],
        "candidate_name": (result.get("candidate_name") or "")[:200],
        "ats_percentage": float((result.get("ats") or {}).get("percentage") or 0),
        "summary": (result.get("summary") or "")[:500],
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
    payload = _pack(result)
    if payload:
        metadata["payload"] = payload
    index.upsert(
        vectors=[{
            "id": vector_id,
            "values": _embed(_profile_text(result)),
            "metadata": metadata,
        }],
        namespace=_NAMESPACE,
        show_progress=False,
        timeout=20,
    )


def _delete_vector(vector_id):
    index = _index_client()
    if index is None or not vector_id:
        return
    index.delete(ids=[vector_id], namespace=_NAMESPACE)


def _fetch_payload(vector_id):
    index = _index_client()
    if index is None:
        return None
    fetched = index.fetch(ids=[vector_id], namespace=_NAMESPACE, timeout=20)
    vectors = getattr(fetched, "vectors", None) or {}
    record = vectors.get(vector_id) if isinstance(vectors, dict) else None
    if record is None:
        return None
    if isinstance(record, dict):
        metadata = record.get("metadata") or {}
    else:
        metadata = getattr(record, "metadata", None) or {}
    return _unpack(metadata.get("payload"))
