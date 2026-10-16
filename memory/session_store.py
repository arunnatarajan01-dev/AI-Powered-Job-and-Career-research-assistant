"""SQLite memory for one signed-in browser session.

Rows stay until that session logs out. A new browser session uses a new id,
so it does not read the previous person's scan.
"""

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(
    os.getenv(
        "SESSION_MEMORY_DB",
        Path(__file__).resolve().parent.parent / "data" / "session_memory.db",
    )
)
_LOCK = threading.Lock()
_READY = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_label TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    name TEXT,
    email TEXT,
    phone TEXT,
    filename TEXT,
    experience_years REAL,
    skills TEXT,
    summary TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    candidate_id INTEGER,
    source TEXT NOT NULL,
    title TEXT,
    company TEXT,
    location TEXT,
    match_score REAL,
    url TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    candidate_id INTEGER,
    job_id INTEGER NOT NULL,
    rank INTEGER,
    score REAL,
    fit TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    candidate_id INTEGER,
    job_id INTEGER,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
"""


def empty_memory():
    return {
        "candidates": [],
        "jobs": [],
        "rankings": [],
        "evidence": [],
        "messages": [],
    }


def remember_analysis(session_id, user_label, result):
    """Replace this session's candidate, catalog jobs, rankings, and evidence."""
    if not session_id or not result:
        return
    contact = result.get("contact") or {}
    skills = ", ".join(result.get("skill_names") or [])
    now = _now()
    with _LOCK:
        conn = _connect()
        try:
            _ensure_session(conn, session_id, user_label)
            conn.execute("DELETE FROM candidates WHERE session_id = ?", (session_id,))
            candidate_id = conn.execute(
                """
                INSERT INTO candidates (
                    session_id, name, email, phone, filename,
                    experience_years, skills, summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    result.get("candidate_name") or "",
                    contact.get("email") or "",
                    contact.get("phone") or "",
                    result.get("filename") or "",
                    result.get("experience_years") or 0,
                    skills,
                    (result.get("summary") or "")[:2000],
                    now,
                ),
            ).lastrowid
            if result.get("summary"):
                _evidence(conn, session_id, candidate_id, None, "summary", result["summary"])
            excerpt = (result.get("experience_excerpt") or "").strip()
            if excerpt:
                _evidence(conn, session_id, candidate_id, None, "experience", excerpt)
            for item in (result.get("ats") or {}).get("breakdown", {}).values():
                if not isinstance(item, dict):
                    continue
                label = item.get("label") or "ATS"
                _evidence(
                    conn,
                    session_id,
                    candidate_id,
                    None,
                    "ats",
                    f"{label}: {item.get('score')}/{item.get('max')}. {item.get('details') or ''}",
                )
            for entry in result.get("education") or []:
                if isinstance(entry, dict):
                    text = ", ".join(
                        str(entry.get(key) or "")
                        for key in ("degree", "institution", "year")
                        if entry.get(key)
                    )
                else:
                    text = str(entry)
                if text:
                    _evidence(conn, session_id, candidate_id, None, "education", text)
            for index, job in enumerate(result.get("recommendations") or [], start=1):
                job_id = _insert_job(
                    conn,
                    session_id,
                    candidate_id,
                    "catalog",
                    job.get("title"),
                    job.get("company"),
                    job.get("location"),
                    job.get("match_score"),
                    "",
                )
                conn.execute(
                    """
                    INSERT INTO rankings (session_id, candidate_id, job_id, rank, score, fit)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        candidate_id,
                        job_id,
                        job.get("rank") or index,
                        job.get("match_score"),
                        job.get("fit_level") or "",
                    ),
                )
                matched = ", ".join(job.get("matched_skills") or [])
                missing = ", ".join(job.get("missing_skills") or [])
                if matched:
                    _evidence(
                        conn,
                        session_id,
                        candidate_id,
                        job_id,
                        "matched_skills",
                        f"{job.get('title')}: matched {matched}",
                    )
                if missing:
                    _evidence(
                        conn,
                        session_id,
                        candidate_id,
                        job_id,
                        "missing_skills",
                        f"{job.get('title')}: missing {missing}",
                    )
            conn.commit()
        finally:
            conn.close()


def remember_jobs(session_id, bundles):
    """Store live or catalog postings found after the resume scan."""
    if not session_id:
        return
    with _LOCK:
        conn = _connect()
        try:
            candidate = conn.execute(
                "SELECT id FROM candidates WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if candidate is None:
                return
            candidate_id = candidate["id"]
            conn.execute(
                "DELETE FROM jobs WHERE session_id = ? AND source != 'catalog'",
                (session_id,),
            )
            for bundle in bundles or []:
                source = bundle.get("provider") or bundle.get("label") or "search"
                ranked = []
                for job in bundle.get("jobs") or []:
                    score = job.get("skill_match_percent")
                    job_id = _insert_job(
                        conn,
                        session_id,
                        candidate_id,
                        source,
                        job.get("title"),
                        job.get("company"),
                        job.get("location"),
                        score,
                        job.get("career_url") or "",
                    )
                    if score is not None:
                        ranked.append((score, job_id, job.get("title")))
                ranked.sort(key=lambda item: item[0], reverse=True)
                for rank, (score, job_id, _title) in enumerate(ranked, start=1):
                    fit = "Strong overlap" if score >= 60 else "Partial overlap"
                    conn.execute(
                        """
                        INSERT INTO rankings (session_id, candidate_id, job_id, rank, score, fit)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (session_id, candidate_id, job_id, rank, score, fit),
                    )
            conn.commit()
        finally:
            conn.close()


def add_message(session_id, role, content):
    if not session_id or not (content or "").strip():
        return
    with _LOCK:
        conn = _connect()
        try:
            exists = conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if exists is None:
                return
            conn.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content.strip()[:4000], _now()),
            )
            conn.commit()
        finally:
            conn.close()


def load_memory(session_id):
    if not session_id:
        return empty_memory()
    with _LOCK:
        conn = _connect()
        try:
            candidates = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, name, email, phone, filename, experience_years, skills, summary
                    FROM candidates WHERE session_id = ? ORDER BY id
                    """,
                    (session_id,),
                )
            ]
            jobs = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, source, title, company, location, match_score, url
                    FROM jobs WHERE session_id = ? ORDER BY source, id
                    """,
                    (session_id,),
                )
            ]
            rankings = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT r.rank, r.score, r.fit, r.job_id, j.title, j.company, j.source
                    FROM rankings r
                    JOIN jobs j ON j.id = r.job_id
                    WHERE r.session_id = ?
                    ORDER BY j.source, r.rank
                    """,
                    (session_id,),
                )
            ]
            evidence = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT e.kind, e.text, e.job_id, j.title AS job_title
                    FROM evidence e
                    LEFT JOIN jobs j ON j.id = e.job_id
                    WHERE e.session_id = ?
                    ORDER BY e.id
                    """,
                    (session_id,),
                )
            ]
            messages = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT role, content, created_at
                    FROM chat_messages WHERE session_id = ? ORDER BY id
                    """,
                    (session_id,),
                )
            ]
        finally:
            conn.close()
    return {
        "candidates": candidates,
        "jobs": jobs,
        "rankings": rankings,
        "evidence": evidence,
        "messages": messages,
    }


def answer_from_memory(memory, question):
    """Answer from the rows stored for this session."""
    candidates = memory.get("candidates") or []
    if not candidates:
        return "No candidate is stored for this session. Scan a resume first."
    person = candidates[0]
    words = [word for word in (question or "").lower().split() if len(word) > 3]
    jobs = memory.get("jobs") or []
    related = []
    for job in jobs:
        blob = " ".join(
            str(job.get(key) or "")
            for key in ("title", "company", "location", "source")
        ).lower()
        if words and any(word in blob for word in words):
            related.append(job)
    if not related:
        related = [job for job in jobs if job.get("source") == "catalog"][:3]
    job_ids = {job["id"] for job in related}
    ranking_bits = []
    for rank in memory.get("rankings") or []:
        if rank["job_id"] in job_ids:
            ranking_bits.append(
                f"{rank['rank']}. {rank['title']} at {rank['company']} "
                f"({rank['score']}%, {rank['fit']}, {rank['source']})"
            )
    evidence_bits = []
    for item in memory.get("evidence") or []:
        text = item.get("text") or ""
        if item.get("job_id") in job_ids or any(word in text.lower() for word in words):
            evidence_bits.append(text)
    name = person.get("name") or "This candidate"
    years = person.get("experience_years") or 0
    parts = [
        f"{name} has {years} years of experience on file. Skills: {person.get('skills') or 'none listed'}."
    ]
    if ranking_bits:
        parts.append("Rankings: " + "; ".join(ranking_bits[:5]) + ".")
    if evidence_bits:
        parts.append("Evidence: " + " ".join(evidence_bits[:4]))
    elif not ranking_bits:
        parts.append("Nothing else stored in this session matches that question.")
    return " ".join(parts)


def end_session(session_id):
    """Delete every row for this session. Called on logout."""
    if not session_id:
        return
    with _LOCK:
        conn = _connect()
        try:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()


def _connect():
    global _READY
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not _READY:
        conn.executescript(_SCHEMA)
        _READY = True
    return conn


def _ensure_session(conn, session_id, user_label):
    conn.execute(
        """
        INSERT INTO sessions (id, user_label, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET user_label = excluded.user_label
        """,
        (session_id, user_label or "anonymous", _now()),
    )


def _insert_job(conn, session_id, candidate_id, source, title, company, location, score, url):
    return conn.execute(
        """
        INSERT INTO jobs (
            session_id, candidate_id, source, title, company, location, match_score, url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            candidate_id,
            source or "search",
            title or "",
            company or "",
            location or "",
            score,
            url or "",
        ),
    ).lastrowid


def _evidence(conn, session_id, candidate_id, job_id, kind, text):
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return
    conn.execute(
        """
        INSERT INTO evidence (session_id, candidate_id, job_id, kind, text)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, candidate_id, job_id, kind, cleaned[:500]),
    )


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
