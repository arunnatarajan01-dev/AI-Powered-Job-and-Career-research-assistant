"""Compare resume skills with the skills named in a job posting."""

import re

from models.skill_extractor import extract_skills, get_skill_names


def unique_skills(skills):
    """Keep skill names in first-seen order."""
    names = []
    seen = set()
    for skill in skills or []:
        text = str(skill or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        names.append(text)
    return names


def skill_match_percent(resume_skills, job):
    """Percent of skills in this posting that also appear on the resume.

    Returns None when the candidate has no resume skills to compare.
    """
    names = unique_skills(resume_skills)
    if not names:
        return None
    blob = " ".join(
        str(job.get(key) or "")
        for key in ("title", "company", "description")
    )
    job_skills = unique_skills(get_skill_names(extract_skills(blob)))
    resume_keys = {name.lower() for name in names}
    if job_skills:
        matched = sum(1 for skill in job_skills if skill.lower() in resume_keys)
        return int(round(100 * matched / len(job_skills)))
    lowered = blob.lower()
    matched = 0
    for name in names:
        pattern = r"(?<![a-z])" + re.escape(name.lower()) + r"(?![a-z])"
        if re.search(pattern, lowered):
            matched += 1
    return int(round(100 * matched / len(names)))


def attach_skill_matches(results, resume_skills):
    """Add skill_match_percent on each job when a resume is available."""
    for bundle in results or []:
        for job in bundle.get("jobs") or []:
            percent = skill_match_percent(resume_skills, job)
            if percent is None:
                job.pop("skill_match_percent", None)
            else:
                job["skill_match_percent"] = percent
    return results
