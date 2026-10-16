"""
BERT Matcher - Semantic job matching using sentence-transformers.
Uses all-MiniLM-L6-v2 model for fast, accurate semantic similarity.
"""
import hashlib
import os
import csv
import threading

# Lazy load to avoid slow startup
_model = None
_jobs_data = None
_job_embeddings = None
_warm_started = False
_warm_lock = threading.Lock()
_PROFILE_CHARS = 1500
_CACHE_NAME = "job_embeddings.npz"


def _get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is not None:
        return _model
    with _warm_lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
            print("Loading BERT model (all-MiniLM-L6-v2)... This may take a moment on first run.")
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            print("BERT model loaded successfully!")
        except ImportError:
            print("Warning: sentence-transformers not installed. Using fallback keyword matching.")
            _model = "FALLBACK"
        except Exception as e:
            print(f"Warning: Could not load BERT model: {e}. Using fallback.")
            _model = "FALLBACK"
    return _model


def _load_jobs():
    """Load jobs data from CSV."""
    global _jobs_data
    if _jobs_data is not None:
        return _jobs_data

    jobs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jobs.csv")
    _jobs_data = []

    if not os.path.exists(jobs_path):
        print(f"Warning: Jobs CSV not found at {jobs_path}")
        return _jobs_data

    with open(jobs_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            _jobs_data.append(row)

    return _jobs_data


def _cache_path():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", _CACHE_NAME)


def _jobs_signature(jobs):
    blob = "\n".join(
        f"{job.get('title', '')}\t{job.get('description', '')}\t{job.get('required_skills', '')}"
        for job in jobs
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _load_cached_embeddings(signature):
    path = _cache_path()
    if not os.path.exists(path):
        return None
    try:
        import numpy as np
        loaded = np.load(path, allow_pickle=False)
        saved = str(loaded["signature"].item())
        if saved != signature:
            return None
        return loaded["embeddings"]
    except Exception as exc:
        print(f"Warning: could not read job embeddings cache: {exc}")
        return None


def _save_cached_embeddings(embeddings, signature):
    try:
        import numpy as np
        np.savez(_cache_path(), embeddings=np.asarray(embeddings), signature=np.asarray(signature))
    except Exception as exc:
        print(f"Warning: could not save job embeddings cache: {exc}")


def _get_job_embeddings():
    """Get or compute job description embeddings."""
    global _job_embeddings

    model = _get_model()
    if model == "FALLBACK":
        return None

    if _job_embeddings is not None:
        return _job_embeddings

    jobs = _load_jobs()
    if not jobs:
        return None

    signature = _jobs_signature(jobs)
    cached = _load_cached_embeddings(signature)
    if cached is not None:
        _job_embeddings = cached
        return _job_embeddings

    job_texts = []
    for job in jobs:
        text = f"{job['title']}. {job['description']}. Skills: {job['required_skills']}"
        job_texts.append(text)

    embeddings = model.encode(job_texts, show_progress_bar=False)
    _save_cached_embeddings(embeddings, signature)
    _job_embeddings = embeddings
    return _job_embeddings


def _warm():
    try:
        model = _get_model()
        if model != "FALLBACK":
            _get_job_embeddings()
            print("Job matcher is ready.")
    except Exception as exc:
        print(f"Warning: job matcher warm-up failed: {exc}")


def warm_matcher():
    """Load the model and job embeddings off the resume-analysis request."""
    global _warm_started
    with _warm_lock:
        if _warm_started:
            return
        _warm_started = True
    threading.Thread(target=_warm, name="job-matcher", daemon=True).start()


_INDIA_MARKERS = (
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "mumbai",
    "delhi",
    "chennai",
    "kolkata",
    "ahmedabad",
    "jaipur",
    "noida",
    "gurugram",
    "gurgaon",
    "kochi",
    "india",
)


def _location_preference(location):
    """Indian cities rank ahead of other locations."""
    text = (location or "").lower()
    if any(marker in text for marker in _INDIA_MARKERS):
        return 0
    return 1


def _keyword_match_score(resume_skills_lower, job_skills_str):
    """Fallback keyword-based matching when BERT is unavailable."""
    job_skills = {s.strip().lower() for s in job_skills_str.split(",") if s.strip()}

    if not job_skills:
        return 0.0

    matches = resume_skills_lower.intersection(job_skills)
    return len(matches) / len(job_skills)


def _profile_text(resume_text, resume_skills):
    """Short text for the resume embedding. The full resume is not encoded."""
    skills = ", ".join(resume_skills or [])
    excerpt = (resume_text or "").strip()[:_PROFILE_CHARS]
    return f"Skills: {skills}. {excerpt}"


def _job_result(job, resume_skills_lower, semantic_score, keyword_score, combined_score):
    job_skill_list = [s.strip() for s in job["required_skills"].split(",") if s.strip()]
    matched = [s for s in job_skill_list if s.lower() in resume_skills_lower]
    missing = [s for s in job_skill_list if s.lower() not in resume_skills_lower]
    return {
        "title": job["title"],
        "company": job.get("company", "Tech Enterprise"),
        "location": job.get("location", "Remote / On-site"),
        "description": job["description"],
        "category": job["category"],
        "experience_level": job["experience_level"],
        "salary_range": job["salary_range"],
        "posted_date": job.get("posted_date", "Recently"),
        "required_skills": job_skill_list,
        "matched_skills": matched,
        "missing_skills": missing,
        "semantic_score": round(semantic_score * 100, 1),
        "keyword_score": round(keyword_score * 100, 1),
        "match_score": round(combined_score * 100, 1),
    }


def _cosine_scores(resume_embedding, job_embeddings):
    """Cosine similarity without importing scikit-learn on the analysis request."""
    import numpy as np

    query = np.asarray(resume_embedding, dtype=np.float32).reshape(-1)
    matrix = np.asarray(job_embeddings, dtype=np.float32)
    query_norm = np.linalg.norm(query)
    matrix_norm = np.linalg.norm(matrix, axis=1)
    return matrix.dot(query) / np.maximum(matrix_norm * query_norm, 1e-12)


def _rank(results, top_k):
    results.sort(key=lambda item: (_location_preference(item["location"]), -item["match_score"]))
    return results[:top_k]


def _keyword_results(jobs, resume_skills_lower, top_k):
    results = []
    for job in jobs:
        keyword_score = _keyword_match_score(resume_skills_lower, job["required_skills"])
        results.append(_job_result(job, resume_skills_lower, 0, keyword_score, keyword_score))
    return _rank(results, top_k)


def match_jobs(resume_text, resume_skills, top_k=10):
    """
    Match resume against job descriptions using semantic similarity.

    Args:
        resume_text: Full resume text
        resume_skills: List of skill names extracted from resume
        top_k: Number of top matches to return

    Returns:
        list: Top matching jobs with scores
    """
    jobs = _load_jobs()
    if not jobs:
        return []

    resume_skills_lower = {skill.lower() for skill in resume_skills}
    model = _model
    job_embeddings = _job_embeddings
    if not model or model == "FALLBACK" or job_embeddings is None:
        return _keyword_results(jobs, resume_skills_lower, top_k)

    resume_embedding = model.encode([_profile_text(resume_text, resume_skills)], show_progress_bar=False)
    similarities = _cosine_scores(resume_embedding, job_embeddings)

    results = []
    for i, job in enumerate(jobs):
        semantic_score = float(similarities[i])
        keyword_score = _keyword_match_score(resume_skills_lower, job["required_skills"])
        combined_score = (0.6 * semantic_score) + (0.4 * keyword_score)
        results.append(_job_result(job, resume_skills_lower, semantic_score, keyword_score, combined_score))

    return _rank(results, top_k)
