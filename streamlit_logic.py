"""Shared actions for the Streamlit UI. Pages stay focused on widgets."""

import io
import os
import re

from dotenv import load_dotenv

from agents import Orchestrator
from jobs import POSTED_LABELS, parse_experience, parse_work_mode
from jobs.discovery import CITIES
from jobs.skill_match import attach_skill_matches
from middleware import agent_middleware
from models.ats_scorer import calculate_ats_score
from models.resume_feedback import generate_feedback, get_overall_summary
from models.skill_extractor import extract_skills, get_skill_names, get_skills_by_category
from parser.docx_reader import extract_text_from_docx
from parser.pdf_reader import extract_text_from_pdf
from parser.section_extractor import (
    extract_education_details,
    extract_experience_years,
    extract_sections,
)
from parser.text_cleaning import (
    clean_text,
    extract_candidate_name,
    extract_email,
    extract_links,
    extract_phone,
)
from preparation.coding_practice import get_available_companies as coding_companies
from preparation.coding_practice import get_available_topics, get_coding_questions
from preparation.company_questions import get_available_companies as interview_companies
from preparation.company_questions import get_company_questions
from preparation.interview_questions import generate_interview_questions
from recommendation.career_guidance import suggest_career_paths
from recommendation.job_recommender import get_recommendations
from recommendation.learning_roadmap import estimate_total_time, generate_roadmap
from recommendation.skill_gap_analysis import analyze_skill_gaps

load_dotenv()

ACTOR = "streamlit"
_SALARY_AMOUNT = re.compile(r"\d[\d,]*")


class AnalysisError(ValueError):
    """The uploaded resume could not be analyzed."""


def format_inr(value):
    """Show a salary range with the rupee symbol and Indian digit grouping."""
    text = "" if value is None else str(value).strip()
    if not text:
        return "—"
    if "₹" in text:
        return text
    amounts = [int(chunk.replace(",", "")) for chunk in _SALARY_AMOUNT.findall(text)]
    if not amounts:
        return text
    multiply = 10 if "$" in text or "USD" in text.upper() else 1
    formatted = [f"₹{_group_indian(amount * multiply)}" for amount in amounts[:2]]
    if len(formatted) == 1:
        return formatted[0]
    return f"{formatted[0]}–{formatted[1]}"


def analyze_resume(filename, data):
    """Run the same resume pipeline the Flask analyzer uses."""
    name = (filename or "").strip()
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in {"pdf", "docx", "doc"}:
        raise AnalysisError("Upload a PDF or DOCX resume.")
    if not data:
        raise AnalysisError("The file is empty.")

    with agent_middleware(
        "resume.analyze",
        "/streamlit/resume",
        actor=ACTOR,
        filename=name,
    ) as gate:
        current = gate.trace
        stream = io.BytesIO(data)
        with current.span("extract_text", extension=ext):
            if ext == "pdf":
                raw_text = extract_text_from_pdf(file_stream=stream)
            else:
                raw_text = extract_text_from_docx(file_stream=stream)
        if not raw_text or len(raw_text.strip()) < 50:
            raise AnalysisError("Could not extract enough text from the resume.")

        with current.span("parse_profile"):
            cleaned_text = clean_text(raw_text)
            sections = extract_sections(cleaned_text)
            skills = extract_skills(cleaned_text)
            skill_names = get_skill_names(skills)
            education = extract_education_details(sections.get("education", ""))
            experience_years = extract_experience_years(cleaned_text)

        with current.span("score_and_match"):
            ats_result = calculate_ats_score(cleaned_text, sections, skills, experience_years)
            feedback = generate_feedback(ats_result, sections, skills, experience_years)
            summary = get_overall_summary(ats_result, skills, sections)
            recommendations = get_recommendations(cleaned_text, skill_names, top_k=8)
            skill_gaps = analyze_skill_gaps(skill_names, recommendations)

        with current.span("coach"):
            roadmap = generate_roadmap(skill_gaps, skill_names)
            top_role = recommendations[0]["title"] if recommendations else "Software Engineer"
            interview_qs = generate_interview_questions(top_role, skill_names[:5])

        current.meta["ats_percentage"] = ats_result.get("percentage")
        current.meta["skill_count"] = len(skill_names)
        current.meta["role_count"] = len(recommendations)

    return {
        "candidate_name": extract_candidate_name(raw_text) or extract_candidate_name(cleaned_text),
        "contact": {
            "email": extract_email(raw_text),
            "phone": extract_phone(raw_text),
            "links": extract_links(raw_text),
        },
        "skills": skills,
        "skill_names": skill_names,
        "skills_by_category": get_skills_by_category(skills),
        "education": education,
        "experience_years": experience_years,
        "ats": ats_result,
        "feedback": feedback,
        "summary": summary,
        "recommendations": recommendations,
        "skill_gaps": skill_gaps,
        "roadmap": roadmap,
        "total_learning_time": estimate_total_time(roadmap),
        "career_paths": suggest_career_paths(skill_names, experience_years),
        "interview_questions": interview_qs,
        "filename": name,
    }


def analysis_workbook(result):
    """Excel export shared with the Flask dashboard."""
    from unified_app import _analysis_workbook

    return _analysis_workbook(result)


def search_jobs(providers, location, posted, keyword, experience, work_mode, resume_skills):
    """Search the selected job providers, then compare postings with resume skills."""
    from jobs.discovery import PROVIDERS

    selected = [key for key in providers if key in PROVIDERS]
    if not selected:
        raise AnalysisError("Select at least one job source.")
    years = parse_experience(experience)
    mode = parse_work_mode(work_mode)
    role = (keyword or "software engineer").strip() or "software engineer"
    window = posted if posted in {"today", "week", "month"} else "week"
    with agent_middleware(
        "jobs.discover",
        "/streamlit/jobs",
        actor=ACTOR,
        location=location,
        posted=window,
        providers=",".join(selected),
    ) as gate:
        current = gate.trace
        with current.span("providers", keyword=role, experience=years or "", work_mode=mode):
            results = Orchestrator().job_search(
                selected,
                location,
                window,
                role,
                current,
                experience=years,
                remote_only=mode == "remote",
                work_mode=mode,
            )["results"]
        current.meta["source_count"] = len(results)
        current.meta["job_count"] = sum(len(item.get("jobs") or []) for item in results)
    attach_skill_matches(results, resume_skills or [])
    return results


def read_research_pdfs(files):
    """Extract text from uploaded research PDFs."""
    parts = []
    for item in files or []:
        text = extract_text_from_pdf(file_stream=io.BytesIO(item["data"]))
        if text:
            parts.append(f"# {item['name']}\n{text}")
    return "\n\n".join(parts)


def research_answer(question, document):
    """Answer from the uploaded document through the research agent."""
    with agent_middleware(
        "research.chat",
        "/streamlit/research",
        actor=ACTOR,
        fields={"message": question},
        guard_fields=("message",),
        guard_output=True,
        message_chars=len((question or "").strip()),
        document_chars=len(document or ""),
    ) as gate:
        if gate.blocked:
            return gate.blocked.user_message
        if not _gemini_ready():
            return "Add GEMINI_API_KEY to the .env file before asking a research question."
        result = Orchestrator().research_answer(
            gate.fields["message"],
            document or "",
            _call_gemini(),
            gate.trace,
            use_model_tools=True,
        )
        answer = result["answer"]
        blocked = gate.screen_output(answer)
        if blocked:
            return blocked.user_message
        return answer


def research_draft(repo_url, author, institution):
    """Ask Gemini for an IEEE-style draft and return the parsed sections."""
    import json

    with agent_middleware(
        "research.constructor",
        "/streamlit/constructor",
        actor=ACTOR,
        fields={"repo_url": repo_url, "author": author, "institution": institution},
        guard_fields=("repo_url", "author", "institution"),
        guard_output=True,
    ) as gate:
        if gate.blocked:
            raise AnalysisError(gate.blocked.plain_message)
        if not _gemini_ready():
            raise AnalysisError("Add GEMINI_API_KEY to the .env file before generating a draft.")
        drafted = Orchestrator().research_draft(
            gate.fields["repo_url"],
            gate.fields["author"],
            gate.fields["institution"],
            _call_gemini(),
            gate.trace,
        )
        response_text = drafted["draft"]
        if "```json" in response_text:
            response_text = response_text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```", 1)[1].split("```", 1)[0].strip()
        blocked = gate.screen_output(response_text)
        if blocked:
            raise AnalysisError(blocked.plain_message)
        return json.loads(response_text)


def recommendation_rows(result):
    rows = []
    for job in result.get("recommendations") or []:
        rows.append({
            "Rank": job.get("rank"),
            "Role": job.get("title"),
            "Company": job.get("company"),
            "Location": job.get("location"),
            "Match": job.get("match_score"),
            "Skill match": job.get("skill_match_percent"),
            "Fit": job.get("fit_level"),
            "Experience": job.get("experience_level"),
            "Salary": format_inr(job.get("salary_range")),
        })
    return rows


def gap_rows(result):
    rows = []
    grouped = result.get("skill_gaps") or {}
    for key in ("critical", "important", "nice_to_have"):
        for gap in grouped.get(key) or []:
            rows.append({
                "Skill": gap.get("skill"),
                "Priority": gap.get("priority"),
                "Demanded by": gap.get("demanded_by"),
                "Related roles": ", ".join(gap.get("related_jobs") or []),
            })
    return rows


def roadmap_rows(result):
    rows = []
    for item in result.get("roadmap") or []:
        resources = item.get("resources") or []
        if not isinstance(resources, list):
            resources = [resources]
        rows.append({
            "Order": item.get("order"),
            "Skill": item.get("skill"),
            "Priority": item.get("priority"),
            "Why": item.get("why"),
            "Time": item.get("estimated_time"),
            "Resources": ", ".join(str(resource) for resource in resources),
        })
    return rows


def job_rows(bundle):
    rows = []
    for job in bundle.get("jobs") or []:
        match = job.get("skill_match_percent")
        rows.append({
            "Role": job.get("title"),
            "Company": job.get("company"),
            "Location": job.get("location"),
            "Experience": job.get("experience_label") or "",
            "Type": job.get("employment_type"),
            "Skill match": "" if match is None else match,
            "Link": job.get("career_url") or "",
        })
    return rows


def interview_question_rows(company, category, difficulty):
    return get_company_questions(
        company=company or None,
        category=category or None,
        difficulty=difficulty or None,
    )


def coding_question_rows(company, topic, difficulty):
    return get_coding_questions(
        company=company or None,
        topic=topic or None,
        difficulty=difficulty or None,
    )


def city_names():
    return ["All location", *[city["name"] for city in CITIES]]


def posted_options():
    return list(POSTED_LABELS)


def practice_companies():
    return {
        "interview": interview_companies(),
        "coding": coding_companies(),
        "topics": get_available_topics(),
    }


def _gemini_ready():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(key) and key != "your_actual_api_key_here"


def _call_gemini():
    from unified_app import call_gemini_ai

    return call_gemini_ai


def _group_indian(amount):
    digits = str(abs(int(amount)))
    if len(digits) <= 3:
        return digits
    last3 = digits[-3:]
    rest = digits[:-3]
    parts = []
    while rest:
        parts.append(rest[-2:])
        rest = rest[:-2]
    return ",".join(reversed(parts)) + "," + last3
