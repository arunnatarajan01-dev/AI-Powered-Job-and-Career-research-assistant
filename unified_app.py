"""
AI-Powered Excellence Platform
Main Entry Point
"""
import os
import re
import sys
import uuid
import json
from datetime import datetime
from flask import Flask, abort, render_template, request, jsonify, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv

from agents import Orchestrator
from evaluations import run_evaluations
from exports.ats_pdf import build_ats_pdf, pdf_download_name
from exports.xlsx import build_xlsx
from hitl import (
    ACTIONS,
    ROLE_COPY,
    ROLES,
    SCREEN,
    apply_action,
    ats_pdf_ready,
    authenticate,
    build_case,
    field_options,
    next_options,
    notice_options,
    notify_decision,
    reason_options,
    review_scenarios,
    stage_options,
    validate,
    public_users,
    register_account,
    apply_reset_token,
    issue_reset_token,
)
from jobs import POSTED_LABELS, PROVIDER_OPTIONS, parse_experience, parse_work_mode
from jobs.skill_match import attach_skill_matches
from memory.applications import application_counts, record_application
from memory.pinecone_memory import (
    delete_candidate_scan,
    list_candidates,
    load_candidate_scan,
    load_user_scan,
    save_user_scan,
    scan_id_for,
)
from memory.session_store import (
    add_message,
    answer_from_memory,
    end_session,
    load_memory,
    remember_analysis,
    remember_jobs,
)
from middleware import agent_middleware, pipeline_steps
from observability import recent_traces, trace_summary
from safety.admin_alert import _smtp_settings, notify_admin
from safety.review_mail import _deliver
from safety.guardrail import check_output, check_text

# Load API Keys
load_dotenv()
_gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
if _gemini_api_key and _gemini_api_key != "your_actual_api_key_here":
    genai.configure(api_key=_gemini_api_key)

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import logic from Resume Analyzer components
from parser.pdf_reader import extract_text_from_pdf
from parser.docx_reader import extract_text_from_docx
from parser.text_cleaning import clean_text, extract_candidate_name, extract_email, extract_phone, extract_links
from parser.section_extractor import extract_sections, extract_education_details, extract_experience_years
from models.bert_matcher import warm_matcher
from models.skill_extractor import extract_skills, get_skills_by_category, get_skill_names
from models.ats_scorer import calculate_ats_score
from models.resume_feedback import generate_feedback, get_overall_summary
from recommendation.job_recommender import get_recommendations
from recommendation.skill_gap_analysis import analyze_skill_gaps
from recommendation.learning_roadmap import generate_roadmap, estimate_total_time
from recommendation.career_guidance import suggest_career_paths
from preparation.interview_questions import generate_interview_questions
from preparation.company_questions import get_company_questions, get_available_companies as get_interview_companies, get_company_stats
from preparation.coding_practice import (
    get_coding_questions, get_available_companies as get_coding_companies,
    get_available_topics, get_company_coding_stats, get_recommended_problems
)
from preparation.voice_interview import TOPICS, feedback_for, load_catalog, questions_for, reply_to_answer

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)

_SALARY_AMOUNT = re.compile(r"\d[\d,]*")


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


@app.template_filter("inr_salary")
def inr_salary(value):
    """Show a salary range with the rupee symbol and Indian digit grouping."""
    text = "" if value is None else str(value).strip()
    if not text:
        return "₹—"
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


@app.route("/health")
def health():
    """Load-balancer probe. Stays 200 even when the hub redirects to login."""
    return jsonify(status="ok")


@app.context_processor
def inject_current_user():
    return {"current_user": session.get("user")}


def _actor():
    user = _current_user()
    return user["name"] if user else "anonymous"


def _current_user():
    user = session.get("user")
    if not user or user.get("role") not in ROLES:
        return None
    return user


_PUBLIC_ENDPOINTS = {
    "home_page",
    "main_page",
    "welcome_page",
    "resume_home",
    "index",
    "login",
    "signup",
    "forgot_password",
    "reset_with_token",
    "health",
    "static",
    "analyze",
}
_GUEST_ANALYSIS_ENDPOINTS = {"dashboard", "dashboard_chat", "dashboard_export"}


@app.before_request
def _signed_out_stays_on_home():
    """After sign-out, a stored page must open the public main page again."""
    endpoint = request.endpoint or ""
    if endpoint in _PUBLIC_ENDPOINTS or endpoint.startswith("static"):
        return None
    if _current_user() is not None:
        return None
    if endpoint in _GUEST_ANALYSIS_ENDPOINTS and session.get("last_analysis_id"):
        return None
    return redirect(url_for("welcome_page"))


@app.after_request
def _do_not_cache_pages(response):
    """Stop the back button from showing a signed-in page from memory."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _safe_jobs_next(value):
    """Stay on the jobs page after a resume upload."""
    target = (value or "").strip()
    if target.startswith("//") or not target.startswith("/jobs"):
        return None
    return target


def _candidate_resume_skills():
    """Skills from the latest attached resume, or from the scanned resume when that is newer."""
    analysis = _current_analysis()
    analysis_id = session.get("last_analysis_id") or ""
    uploaded = session.get("job_resume_skills")
    upload_for = session.get("job_resume_after_analysis") or ""
    scanned = (analysis or {}).get("skill_names") or []
    if uploaded and (not analysis_id or upload_for == analysis_id):
        return list(uploaded), session.get("job_resume_name") or "uploaded resume"
    if scanned:
        return list(scanned), (analysis or {}).get("filename") or "scanned resume"
    if uploaded:
        return list(uploaded), session.get("job_resume_name") or "uploaded resume"
    return [], ""


def _upload_is_current_resume():
    """True when the jobs-page upload is the resume used for scoring."""
    analysis_id = session.get("last_analysis_id") or ""
    uploaded = session.get("job_resume_skills")
    upload_for = session.get("job_resume_after_analysis") or ""
    return bool(uploaded) and (not analysis_id or upload_for == analysis_id)


def _active_resume(user):
    """Candidate resume the application counts belong to."""
    analysis = _current_analysis()
    if _upload_is_current_resume():
        candidate = (session.get("job_resume_candidate") or "").strip()
        resume = session.get("job_resume_name") or "uploaded resume"
        return candidate or resume, resume
    if analysis and ((analysis.get("skill_names") or []) or analysis.get("candidate_name")):
        candidate = (analysis.get("candidate_name") or "").strip()
        resume = analysis.get("filename") or "scanned resume"
        return candidate or resume, resume
    if session.get("job_resume_skills"):
        candidate = (session.get("job_resume_candidate") or "").strip()
        resume = session.get("job_resume_name") or "uploaded resume"
        return candidate or resume, resume
    return "", ""


def _resume_application_counts(user):
    candidate, _resume = _active_resume(user)
    tracked = bool(candidate)
    counts = application_counts(user.get("email") or "", candidate)
    counts["tracked"] = tracked
    return counts


_COVER_LETTER_BODY = """Subject:  Application for suitable position

To : 

Dear Hiring Manager,

I am writing to express my interest in applying for a suitable position within your organization. Please find my resume attached for your review.

With over 18 years of experience in Software Testing and QA, including automation, API testing, performance testing, and Agile/Scrum methodologies, I bring a strong background in ensuring quality and efficiency in software delivery. My recent work includes building RAG-based customer support assistants using FastAPI, ChromaDB, Groq LLM, and Streamlit, as well as containerized deployments with Docker.

I am confident that my skills and experience align well with the requirements of your team, and I would welcome the opportunity to contribute to your projects.

Thank you for considering my application. I look forward to the possibility of discussing how I can add value to your organization.

Best regards,
"""
_COVER_LETTER_LIMIT = 8000
_SKILL_LINE = re.compile(r"^My skill set includes .+$", re.M)
_LEGACY_SKILL_PARAGRAPH = re.compile(
    r"With over 18 years of experience in Software Testing and QA, including .+?Docker\.",
    re.S,
)


def _skill_key(skills):
    return "|".join(str(name).strip().lower() for name in skills or [] if str(name).strip())


def _join_skills(names):
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def _spread_skills(skills, limit=12):
    """Spread the resume skill set across categories so one group does not crowd out the rest."""
    from models.skill_extractor import SKILLS_DB

    groups = {}
    order = []
    for name in skills or []:
        text = str(name or "").strip()
        if not text:
            continue
        category = (SKILLS_DB.get(text.lower()) or {}).get("category") or "Other"
        bucket = groups.setdefault(category, [])
        if text not in bucket:
            bucket.append(text)
            if category not in order:
                order.append(category)
    ranked = sorted(order, key=lambda category: (-len(groups[category]), order.index(category)))
    buckets = [list(groups[category]) for category in ranked]
    selected = []
    while len(selected) < limit and any(buckets):
        for bucket in buckets:
            if bucket and len(selected) < limit:
                selected.append(bucket.pop(0))
    return selected


def _skill_set_sentence(skills):
    selected = _spread_skills(skills)
    if not selected:
        return ""
    return (
        f"My skill set includes {_join_skills(selected)}. "
        "I bring this background to ensuring quality and efficiency in software delivery."
    )


def _sync_cover_letter_skills(letter, skills):
    """Put the current resume skill set into the letter, replacing an older skill paragraph."""
    sentence = _skill_set_sentence(skills)
    if not sentence:
        return letter
    if _SKILL_LINE.search(letter):
        return _SKILL_LINE.sub(sentence, letter, count=1)
    if _LEGACY_SKILL_PARAGRAPH.search(letter):
        return _LEGACY_SKILL_PARAGRAPH.sub(sentence, letter, count=1)
    marker = "Please find my resume attached for your review."
    if marker in letter:
        return letter.replace(marker, marker + "\n\n" + sentence, 1)
    return sentence + "\n\n" + letter


def _default_cover_letter(name, skills=None):
    """Standard cover letter, signed with the account name and filled from the resume skill set."""
    letter = _COVER_LETTER_BODY.rstrip() + "\n"
    signature = " ".join((name or "").split())
    if signature:
        letter += signature + "\n"
    return _sync_cover_letter_skills(letter, skills)


def _cover_letter_for_page(name):
    """Saved letter, with its skill sentence refreshed when the resume skill set changes."""
    skills, _resume_name = _candidate_resume_skills()
    key = _skill_key(skills)
    saved = session.get("job_cover_letter")
    if isinstance(saved, str) and saved.strip():
        if session.get("job_cover_skill_key") == key:
            return saved
        return _sync_cover_letter_skills(saved, skills)
    return _default_cover_letter(name, skills)


def _safe_review_next(value):
    target = (value or "").strip()
    if target.startswith("//"):
        return None
    if target.startswith(("/review", "/jobs", "/observability")):
        return target
    return None


def _home_for(user):
    if user["role"] == "candidate":
        return url_for("job_discovery")
    return url_for("review_home")


def _landing_for(user, next_url):
    """After sign-in, open the role landing page."""
    return url_for("hub_page")


def _memory_id():
    """SQLite session for this browser. Cleared on logout."""
    memory_id = session.get("memory_id")
    if not memory_id:
        memory_id = str(uuid.uuid4())
        session["memory_id"] = memory_id
    return memory_id


def _memory_label():
    user = _current_user()
    if user:
        return user.get("email") or user.get("name") or "anonymous"
    return "anonymous"


def _bind_stored_scan(email):
    """Put this account's last scan back into the dashboard session."""
    stored = load_user_scan(email) if email else None
    if not stored:
        session.pop("last_analysis_id", None)
        return
    analysis_id = scan_id_for(email, stored.get("candidate_name"))
    RESULTS_CACHE[analysis_id] = stored
    session["last_analysis_id"] = analysis_id
    remember_analysis(_memory_id(), email, stored)


def _current_analysis():
    """Latest resume scan for the signed-in user. It stays until the next scan."""
    analysis_id = session.get("last_analysis_id")
    cached = RESULTS_CACHE.get(analysis_id) if analysis_id else None
    if cached is not None:
        return cached
    user = _current_user()
    email = (user or {}).get("email") or ""
    if not email:
        return None
    stored = load_user_scan(email)
    if not stored:
        return None
    analysis_id = scan_id_for(email, stored.get("candidate_name"))
    RESULTS_CACHE[analysis_id] = stored
    session["last_analysis_id"] = analysis_id
    if not load_memory(session.get("memory_id"))["candidates"]:
        remember_analysis(_memory_id(), email, stored)
    return stored

# Server-side results storage for Resume Analyzer
RESULTS_CACHE = {}

# Configure upload
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def enforce_guardrail(text, endpoint, field):
    """Block unsafe input and notify the administrator."""
    result = check_text(text, field)
    if result.allowed:
        return None
    if result.category != "invalid_input":
        notify_admin(
            endpoint=endpoint,
            category=result.category,
            reason=result.reason,
            field=field,
            excerpt=text,
            remote_addr=request.remote_addr,
        )
    return result

def enforce_output_guardrail(text, endpoint):
    """Block model output that leaks secrets or hidden instructions."""
    result = check_output(text)
    if result.allowed:
        return None
    notify_admin(
        endpoint=endpoint,
        category=result.category,
        reason=result.reason,
        field="model_output",
        excerpt=text,
        remote_addr=request.remote_addr,
    )
    return result

# ========================================================
# --- MAIN HUB ROUTE ---
# ========================================================

@app.route('/')
def index():
    """Send a new visit to /welcome. A signed-in person opens the hub."""
    if _current_user() is None:
        return redirect(url_for("welcome_page"))
    return redirect(url_for("hub_page"))


@app.route('/Hub')
def hub_page():
    """Signed-in hub. The address is /Hub."""
    return render_template('index.html')


@app.route('/welcome')
def welcome_page():
    """First page of the application."""
    return render_template('welcome.html')


@app.route('/home')
def home_page():
    """Home page. The address is /home."""
    return render_template('resume_index.html', active_nav='main')


@app.route('/main')
def main_page():
    """Older address for the home page."""
    return redirect(url_for("home_page"))

# ========================================================
# --- RESUME ANALYZER ROUTES ---
# ========================================================

def _block_staff():
    """Hiring managers and auditors do not use the candidate career pages."""
    user = _current_user()
    if user and user["role"] in ("hiring_manager", "auditor"):
        return redirect(url_for("hub_page"))
    return None


@app.route('/resume')
def resume_home():
    """Older address for the main page."""
    return redirect(url_for("home_page"))

@app.route('/analyze', methods=['POST'])
def analyze():
    """Handle resume upload and analysis."""
    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Please upload PDF or DOCX.'}), 400

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        with agent_middleware("resume.analyze", "/analyze", actor=_actor(), filename=filename) as gate:
            current = gate.trace
            ext = filename.rsplit('.', 1)[1].lower()
            with current.span("extract_text", extension=ext):
                if ext == 'pdf':
                    raw_text = extract_text_from_pdf(file_path=filepath)
                elif ext in ('docx', 'doc'):
                    raw_text = extract_text_from_docx(file_path=filepath)
                else:
                    current.status = "error"
                    current.error = "Unsupported file format"
                    return jsonify({'error': 'Unsupported file format'}), 400

            if not raw_text or len(raw_text.strip()) < 50:
                current.status = "error"
                current.error = "Could not extract enough text"
                return jsonify({'error': 'Could not extract enough text from the resume.'}), 400

            with current.span("parse_profile"):
                cleaned_text = clean_text(raw_text)
                sections = extract_sections(cleaned_text)
                email = extract_email(raw_text)
                phone = extract_phone(raw_text)
                links = extract_links(raw_text)
                skills = extract_skills(cleaned_text)
                skill_names = get_skill_names(skills)
                skills_by_category = get_skills_by_category(skills)
                education = extract_education_details(sections.get('education', ''))
                experience_years = extract_experience_years(cleaned_text)

            with current.span("score_and_match"):
                ats_result = calculate_ats_score(cleaned_text, sections, skills, experience_years)
                feedback = generate_feedback(ats_result, sections, skills, experience_years)
                summary = get_overall_summary(ats_result, skills, sections)
                recommendations = get_recommendations(cleaned_text, skill_names, top_k=8)
                skill_gaps = analyze_skill_gaps(skill_names, recommendations)

            with current.span("coach"):
                roadmap = generate_roadmap(skill_gaps, skill_names)
                total_learning_time = estimate_total_time(roadmap)
                career_paths = suggest_career_paths(skill_names, experience_years)
                top_role = recommendations[0]['title'] if recommendations else 'Software Engineer'
                interview_qs = generate_interview_questions(top_role, skill_names[:5])

            try:
                os.remove(filepath)
            except OSError:
                pass

            current.meta["ats_percentage"] = ats_result.get("percentage")
            current.meta["skill_count"] = len(skill_names)
            current.meta["role_count"] = len(recommendations)

            result = {
                'candidate_name': extract_candidate_name(raw_text) or extract_candidate_name(cleaned_text),
                'resume_text': raw_text[:30000],
                'sections': {
                    key: value for key, value in sections.items() if isinstance(value, str)
                },
                'contact': {'email': email, 'phone': phone, 'links': links},
                'sections_found': list(sections.keys()),
                'skills': skills,
                'skill_names': skill_names,
                'skills_by_category': skills_by_category,
                'education': education,
                'experience_years': experience_years,
                'ats': ats_result,
                'feedback': feedback,
                'summary': summary,
                'recommendations': recommendations,
                'skill_gaps': skill_gaps,
                'roadmap': roadmap,
                'total_learning_time': total_learning_time,
                'career_paths': career_paths,
                'interview_questions': interview_qs,
                'filename': filename,
                'experience_excerpt': (sections.get('experience') or '')[:400],
            }

            analysis_id = str(uuid.uuid4())
            owner = (_current_user() or {}).get("email") or (result.get("contact") or {}).get("email") or ""
            saved_id = save_user_scan(owner, result)
            if saved_id:
                analysis_id = saved_id
            RESULTS_CACHE[analysis_id] = result
            session['last_analysis_id'] = analysis_id
            remember_analysis(_memory_id(), _memory_label(), result)
            return jsonify({'success': True, 'redirect': url_for('dashboard')})

    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/dashboard')
def dashboard():
    """Results dashboard. Empty until a resume is analyzed in this session."""
    blocked = _block_staff()
    if blocked:
        return blocked
    result = _current_analysis()
    return render_template(
        'dashboard.html',
        result=result,
        memory=load_memory(session.get("memory_id")),
        memory_error=session.pop("memory_chat_error", None),
    )


@app.route("/dashboard/chat", methods=["POST"])
def dashboard_chat():
    """Save a question and answer against the SQLite session memory."""
    blocked = _block_staff()
    if blocked:
        return blocked
    message = request.form.get("message") or ""
    guard = enforce_guardrail(message, "/dashboard/chat", "message")
    if guard:
        session["memory_chat_error"] = guard.plain_message
        return redirect(url_for("dashboard"))
    memory_id = session.get("memory_id")
    stored = load_memory(memory_id)
    if not stored["candidates"]:
        session["memory_chat_error"] = "Scan a resume before chatting about this session."
        return redirect(url_for("dashboard"))
    add_message(memory_id, "user", message)
    reply = answer_from_memory(load_memory(memory_id), message)
    add_message(memory_id, "assistant", reply)
    return redirect(url_for("dashboard") + "#session-memory")


def _analysis_workbook(result):
    contact = result.get("contact") or {}
    ats = result.get("ats") or {}
    summary_rows = [[
        result.get("filename") or "",
        contact.get("email") or "",
        contact.get("phone") or "",
        ats.get("percentage", ""),
        ats.get("grade", ""),
        ats.get("grade_label", ""),
        result.get("experience_years", ""),
        ", ".join(result.get("skill_names") or []),
    ]]
    recommendations = []
    for job in result.get("recommendations") or []:
        recommendations.append([
            job.get("title"),
            job.get("company"),
            job.get("location"),
            job.get("match_score"),
            job.get("skill_match_percent"),
            job.get("fit_level"),
            job.get("experience_level"),
            job.get("salary_range"),
            ", ".join(job.get("matched_skills") or []),
            ", ".join(job.get("missing_skills") or []),
        ])
    gaps = []
    grouped = result.get("skill_gaps") or {}
    for key in ("critical", "important", "nice_to_have"):
        for gap in grouped.get(key) or []:
            gaps.append([
                gap.get("skill"),
                gap.get("priority"),
                gap.get("demanded_by"),
                ", ".join(gap.get("related_jobs") or []),
            ])
    roadmap = []
    for item in result.get("roadmap") or []:
        roadmap.append([
            item.get("order"),
            item.get("skill"),
            item.get("priority"),
            item.get("why"),
            item.get("estimated_time"),
            ", ".join(item.get("resources") or []) if isinstance(item.get("resources"), list) else item.get("resources"),
        ])
    return build_xlsx([
        ("Summary", ["File", "Email", "Phone", "ATS percent", "Grade", "Label", "Experience years", "Skills"], summary_rows),
        ("Recommendations", ["Title", "Company", "Location", "Match percent", "Skill match percent", "Fit", "Experience", "Salary", "Matched skills", "Missing skills"], recommendations),
        ("Skill gaps", ["Skill", "Priority", "Demanded by", "Related jobs"], gaps),
        ("Roadmap", ["Order", "Skill", "Priority", "Why", "Estimated time", "Resources"], roadmap),
    ])


@app.route("/dashboard/export")
def dashboard_export():
    """Download the current resume analysis as an Excel workbook."""
    blocked = _block_staff()
    if blocked:
        return blocked
    result = _current_analysis()
    if not result:
        return redirect(url_for("dashboard"))
    return send_file(
        _analysis_workbook(result),
        as_attachment=True,
        download_name="resume-analysis.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@app.route('/practice')
def practice():
    """Interview and coding practice page."""
    blocked = _block_staff()
    if blocked:
        return blocked
    return render_template('practice.html',
                           companies_interview=get_interview_companies(),
                           companies_coding=get_coding_companies(),
                           topics=get_available_topics(),
                           company_stats=get_company_stats(),
                           coding_stats=get_company_coding_stats())

# ========================================================
# --- RESEARCH ASSISTANT ROUTES ---
# ========================================================

@app.route('/research')
def research_home():
    """Research Paper Assistant Page."""
    return render_template('research.html')

# ========================================================
# --- API ENDPOINTS (Shared) ---
# ========================================================

@app.route('/api/interview-questions/<company>')
def api_interview_questions(company):
    questions = get_company_questions(company=company, 
                                     category=request.args.get('category'), 
                                     difficulty=request.args.get('difficulty'))
    return jsonify(questions)

@app.route('/api/coding-practice')
@app.route('/api/coding-practice/<company>')
def api_coding_practice(company=None):
    questions = get_coding_questions(company=company, 
                                    topic=request.args.get('topic'), 
                                    difficulty=request.args.get('difficulty'))
    return jsonify(questions)

@app.route('/api/companies')
def api_companies():
    return jsonify({'interview': get_interview_companies(), 'coding': get_coding_companies()})

@app.route('/api/topics')
def api_topics():
    return jsonify(get_available_topics())

# --- AI Resiliency Helper ---
def call_gemini_ai(prompt):
    """Dynamically discover and call the best available Gemini model."""
    try:
        models_info = genai.list_models()

        # Collect candidates that explicitly support generateContent
        candidates = []
        for m in models_info:
            methods = getattr(m, "supported_generation_methods", None) or []
            methods_lower = [str(x).lower() for x in methods]

            # Accept both possible spellings that may show up in SDKs
            supports_generate_content = (
                "generatecontent" in methods_lower or
                "generate_content" in methods_lower
            )

            if supports_generate_content:
                candidates.append((m.name, methods))

        # If none matched, fail with a helpful diagnostic showing what is available
        if not candidates:
            available = [(m.name, getattr(m, "supported_generation_methods", None) or []) for m in models_info]
            debug_list = "\n".join([f"- {name}: {methods}" for name, methods in available[:50]])
            raise Exception(
                "No available Gemini models support generateContent/generate_content for this SDK.\n"
                f"Available models (sample):\n{debug_list}"
            )

        # Prioritize flash/pro by name, then keep the rest
        priority = []
        for keyword in ["flash", "pro"]:
            for name, methods in candidates:
                if keyword in name.lower() and (name, methods) not in priority:
                    priority.append((name, methods))
        for item in candidates:
            if item not in priority:
                priority.append(item)

        models_to_try = [name for name, _ in priority]

        print(f"DEBUG: Found {len(models_to_try)} eligible AI models. Trying best match...")
        last_error = None

        for model_name in models_to_try:
            try:
                print(f"DEBUG: Attempting AI call with discovered model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)  # python SDK uses snake_case
                print(f"DEBUG: Success with model: {model_name}")
                return response.text
            except Exception as e:
                print(f"DEBUG: Model {model_name} failed: {e}")
                last_error = str(e)
                continue

        raise Exception(f"All {len(models_to_try)} eligible Gemini models failed. Last error: {last_error}")

    except Exception as e:
        print(f"DEBUG: Discovery/Call failure: {e}")
        raise e

@app.route('/api/chat_research', methods=['POST'])
def api_chat_research():
    """Gemini-powered Document Intelligence Chat with Resilience."""
    try:
        data = request.json or {}
        user_msg = data.get('message')
        doc_text = data.get('document_text', '')

        print(f"DEBUG: Received AI Chat request: '{user_msg}'")

        with agent_middleware(
            "research.chat",
            "/api/chat_research",
            actor=_actor(),
            fields={"message": user_msg},
            guard_fields=("message",),
            guard_output=True,
            message_chars=len((user_msg or "").strip()),
            document_chars=len(doc_text or ""),
        ) as gate:
            current = gate.trace
            user_msg = gate.fields["message"]
            if gate.blocked:
                return jsonify({'response': gate.blocked.user_message, 'blocked': True}), 200

            if not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") == "your_actual_api_key_here":
                current.status = "error"
                current.error = "API key missing"
                return jsonify({'response': "<strong>API Key Missing</strong><br><br>Please add your Gemini API Key to the .env file."}), 200

            result = Orchestrator().research_answer(
                user_msg,
                doc_text,
                call_gemini_ai,
                current,
                use_model_tools=True,
            )
            response_text = result["answer"]
            current.meta["agents"] = " > ".join(result.get("agents") or [])
            current.meta["tools"] = ",".join(result.get("tools") or [])
            output_block = gate.screen_output(response_text)
            if output_block:
                return jsonify({'response': output_block.user_message, 'blocked': True}), 200
            current.meta["response_chars"] = len(response_text or "")
            return jsonify({'response': response_text})

    except Exception as e:
        print(f"DEBUG: Global AI Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/constructor_generate', methods=['POST'])
def api_constructor_generate():
    """Real AI-powered IEEE Research Paper Generation."""
    try:
        data = request.json or {}
        repo_url = data.get('repo_url')
        author = data.get('author')
        institution = data.get('institution')

        print(f"DEBUG: Generating AI Paper for: {repo_url}")

        with agent_middleware(
            "research.constructor",
            "/api/constructor_generate",
            actor=_actor(),
            fields={"repo_url": repo_url, "author": author, "institution": institution},
            guard_fields=("repo_url", "author", "institution"),
            guard_output=True,
        ) as gate:
            current = gate.trace
            repo_url = gate.fields["repo_url"]
            author = gate.fields["author"]
            institution = gate.fields["institution"]
            if gate.blocked:
                return jsonify({
                    'success': False,
                    'blocked': True,
                    'error': gate.blocked.plain_message,
                }), 403

            if not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") == "your_actual_api_key_here":
                current.status = "error"
                current.error = "API key missing"
                return jsonify({'error': 'API Key Missing'}), 400

            drafted = Orchestrator().research_draft(
                repo_url, author, institution, call_gemini_ai, current
            )
            response_text = drafted["draft"]
            current.meta["agents"] = " > ".join(drafted.get("agents") or [])
            current.meta["tools"] = ",".join(drafted.get("tools") or [])
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            output_block = gate.screen_output(response_text)
            if output_block:
                return jsonify({
                    'success': False,
                    'blocked': True,
                    'error': output_block.plain_message,
                }), 403

            with current.span("parse_draft"):
                analysis = json.loads(response_text)
            current.meta["section_count"] = len(analysis) if isinstance(analysis, dict) else 0
            return jsonify({'success': True, 'analysis': analysis})

    except Exception as e:
        print(f"DEBUG: Constructor Error: {e}")
        return jsonify({'error': str(e)}), 500


def _review_case():
    """Review screen for the selected candidate, or the latest scan."""
    user = _current_user()
    email = (user or {}).get("email") or ""
    selected = (request.values.get("candidate") or "").strip()
    result = load_candidate_scan(email, selected) if email and selected else None
    if result is not None:
        analysis_id = scan_id_for(email, result.get("candidate_name") or selected)
        RESULTS_CACHE[analysis_id] = result
    else:
        result = _current_analysis()
        analysis_id = session.get("last_analysis_id")
    if result is None:
        return build_case(None, None)
    return build_case(result, analysis_id)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login as a candidate or mentor."""
    error = None
    notice = session.pop("login_notice", None)
    next_url = _safe_review_next(request.values.get("next"))
    if request.method == "POST":
        user = authenticate(request.form.get("email"), request.form.get("password"))
        if user is None:
            error = "That email and password do not match an account."
        else:
            previous = session.get("user") or {}
            if previous.get("email") and previous.get("email") != user["email"]:
                end_session(session.get("memory_id"))
                session.pop("memory_id", None)
                session.pop("last_analysis_id", None)
                session.pop("job_cover_letter", None)
                session.pop("job_cover_skill_key", None)
                session.pop("job_resume_after_analysis", None)
                session.pop("job_resume_candidate", None)
            session["user"] = user
            _bind_stored_scan(user.get("email") or "")
            return redirect(_landing_for(user, next_url))
    if _current_user() and request.method == "GET" and not error:
        return redirect(_landing_for(_current_user(), next_url))
    return render_template(
        "login.html",
        error=error,
        notice=notice,
        users=public_users(),
        next_url=next_url or "",
        year=datetime.now().year,
    )


def _send_reset_link(recipient, link):
    """Email the reset link. Returns an error message, or None when it is sent."""
    settings = _smtp_settings()
    if not settings["ready"]:
        return (
            "Email is not configured. Add SMTP_HOST, SMTP_PORT, SMTP_USER, "
            "SMTP_PASSWORD, and SMTP_FROM to .env."
        )
    body = "\n".join([
        "Use this link to reset your password:",
        link,
        "",
        "The link expires in 30 minutes.",
        "If you did not ask for this, you can ignore the email.",
    ])
    try:
        _deliver(settings, recipient, "Reset your password", body)
    except Exception as exc:
        return f"The reset email could not be sent: {exc}"
    return None


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Email a reset link, then return the person to login."""
    error = None
    form = {"email": ""}
    if request.method == "POST":
        form["email"] = request.form.get("email") or ""
        error, token = issue_reset_token(form["email"])
        if error is None:
            link = url_for("reset_with_token", token=token, _external=True)
            error = _send_reset_link(form["email"].strip(), link)
        if error is None:
            session["login_notice"] = "A reset link was sent to your email."
            return redirect(url_for("login"))
    return render_template("forgot_password.html", error=error, form=form)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_with_token(token):
    """Choose a new password from the link in the reset email."""
    error = None
    if request.method == "POST":
        error = apply_reset_token(token, request.form.get("password"))
        if error is None:
            session["login_notice"] = "Password updated. Login with your email and new password."
            return redirect(url_for("login"))
    return render_template("reset_link.html", error=error)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Create a candidate account."""
    error = None
    warning = None
    form = {"name": "", "email": "", "password": "", "confirm": ""}
    if request.method == "POST":
        form["name"] = request.form.get("name") or ""
        form["email"] = request.form.get("email") or ""
        form["password"] = request.form.get("password") or ""
        form["confirm"] = request.form.get("confirm_password") or ""
        if form["password"] != form["confirm"]:
            warning = "New password and confirm password do not match."
        else:
            error = register_account(form["name"], form["email"], form["password"])
            if error is None:
                session["login_notice"] = "Account created. Login with your email and password."
                return redirect(url_for("login"))
    return render_template("signup.html", error=error, warning=warning, form=form)


@app.route("/logout")
def logout():
    session.pop("last_analysis_id", None)
    end_session(session.pop("memory_id", None))
    session.pop("job_resume_skills", None)
    session.pop("job_resume_name", None)
    session.pop("job_cover_letter", None)
    session.pop("job_cover_skill_key", None)
    session.pop("job_resume_after_analysis", None)
    session.pop("job_resume_candidate", None)
    session.clear()
    return redirect(url_for("welcome_page"), code=303)


@app.route("/jobs")
def job_discovery():
    """Search LinkedIn and Naukri adapters by location and posted date."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.full_path))
    if user["role"] != "candidate":
        return redirect(url_for("review_role", role=user["role"], action="approve", denied=1))

    analysis = _current_analysis()
    recommendations = (analysis or {}).get("recommendations") or []
    suggested = recommendations[0] if recommendations else {}
    location = (request.args.get("location") or "").strip() or "All location"
    keyword = (request.args.get("keyword") or "").strip()
    if not keyword:
        keyword = str(suggested.get("title") or "software engineer").strip()
    posted = request.args.get("posted") or "week"
    if posted not in ("today", "week", "month"):
        posted = "week"
    experience = parse_experience(request.args.get("experience"))
    work_mode = parse_work_mode(request.args.get("work_mode"))
    remote_only = request.args.get("remote") == "1"
    selected = request.args.getlist("provider")
    searched = "location" in request.args
    error = None
    results = []
    if searched:
        if not selected:
            error = "Select at least one provider."
        else:
            with agent_middleware(
                "jobs.discover",
                "/jobs",
                actor=user["name"],
                location=location,
                posted=posted,
                providers=",".join(selected),
            ) as gate:
                current = gate.trace
                with current.span("providers", keyword=keyword, experience=experience or "", remote=remote_only, work_mode=work_mode):
                    results = Orchestrator().job_search(
                        selected,
                        location,
                        posted,
                        keyword,
                        current,
                        experience=experience,
                        remote_only=remote_only,
                        work_mode=work_mode,
                    )["results"]
                current.meta["source_count"] = len(results)
                current.meta["job_count"] = sum(len(item.get("jobs") or []) for item in results)
    else:
        selected = [key for key, _label in PROVIDER_OPTIONS]

    resume_skills, resume_name = _candidate_resume_skills()
    if searched and not error:
        attach_skill_matches(results, resume_skills)
        if session.get("memory_id"):
            remember_jobs(session["memory_id"], results)

    return render_template(
        "jobs.html",
        user=user,
        location=location,
        keyword=keyword,
        posted=posted,
        experience=experience,
        work_mode=work_mode,
        remote_only=remote_only,
        experience_years=list(range(1, 26)),
        selected=selected,
        posted_labels=POSTED_LABELS,
        provider_options=PROVIDER_OPTIONS,
        searched=searched and not error,
        error=error,
        results=results,
        resume_name=resume_name,
        resume_skill_count=len(resume_skills),
        applied=_resume_application_counts(user),
        resume_notice=session.pop("job_resume_notice", None),
        resume_error=session.pop("job_resume_error", None),
        cover_letter=_cover_letter_for_page(user.get("name")),
        cover_notice=session.pop("job_cover_notice", None),
        cover_error=session.pop("job_cover_error", None),
    )


@app.route("/jobs/resume", methods=["POST"])
def job_resume_upload():
    """Store skills from a newly uploaded resume for the job search."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.full_path))
    if user["role"] != "candidate":
        return redirect(url_for("review_role", role=user["role"], action="approve", denied=1))

    next_url = _safe_jobs_next(request.form.get("next")) or url_for("job_discovery")
    upload = request.files.get("resume")
    if upload is None or not upload.filename:
        session["job_resume_error"] = "Choose a PDF or Word resume to upload."
        return redirect(next_url)
    if not allowed_file(upload.filename):
        session["job_resume_error"] = "Upload a PDF or Word resume."
        return redirect(next_url)

    filename = secure_filename(upload.filename) or "resume"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    upload.save(filepath)
    try:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext == "pdf":
            raw_text = extract_text_from_pdf(file_path=filepath)
        else:
            raw_text = extract_text_from_docx(file_path=filepath)
        cleaned = clean_text(raw_text or "")
        if len(cleaned.strip()) < 50:
            session["job_resume_error"] = "Could not read enough text from that resume."
            return redirect(next_url)
        skill_names = get_skill_names(extract_skills(cleaned))
        if not skill_names:
            session["job_resume_error"] = "No skills were found in that resume."
            return redirect(next_url)
        session["job_resume_skills"] = skill_names
        session["job_resume_name"] = filename
        session["job_resume_candidate"] = (
            extract_candidate_name(raw_text) or extract_candidate_name(cleaned) or ""
        ).strip()
        session["job_resume_after_analysis"] = session.get("last_analysis_id") or ""
        session["job_resume_notice"] = (
            f"Uploaded {filename}. Job search and the cover letter will use {len(skill_names)} skills from this resume."
        )
    except Exception:
        session["job_resume_error"] = "That resume could not be read. Try a PDF or Word file."
        return redirect(next_url)
    finally:
        try:
            os.remove(filepath)
        except OSError:
            pass
    return redirect(next_url)


@app.route("/jobs/applied", methods=["POST"])
def job_applied():
    """Count one Apply click against the resume selected for this candidate."""
    user = _current_user()
    if user is None:
        return jsonify(error="Sign in required."), 401
    if user["role"] != "candidate":
        return jsonify(error="Only a candidate can record an application."), 403
    candidate, resume = _active_resume(user)
    if not candidate:
        counts = application_counts("", "")
        counts["tracked"] = False
        return jsonify(counts)
    counts = record_application(user.get("email") or "", candidate, resume)
    counts["tracked"] = True
    return jsonify(counts)


@app.route("/jobs/cover-letter", methods=["POST"])
def job_cover_letter():
    """Store the cover letter used when a candidate applies from search results."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.full_path))
    if user["role"] != "candidate":
        return redirect(url_for("review_role", role=user["role"], action="approve", denied=1))

    next_url = _safe_jobs_next(request.form.get("next")) or url_for("job_discovery")
    text = (request.form.get("cover_letter") or "").replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > _COVER_LETTER_LIMIT:
        text = text[:_COVER_LETTER_LIMIT]
    if not text.strip():
        session["job_cover_error"] = "Write a cover letter before saving."
        return redirect(next_url)
    skills, _resume_name = _candidate_resume_skills()
    session["job_cover_letter"] = text
    session["job_cover_skill_key"] = _skill_key(skills)
    session["job_cover_notice"] = "Cover letter saved. Check Include cover letter on a job to use it when you apply."
    return redirect(next_url)


@app.route("/jobs/export")
def job_export():
    """Download the current job search as an Excel table."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.full_path))
    if user["role"] != "candidate":
        return redirect(url_for("review_role", role=user["role"], action="approve", denied=1))
    location = (request.args.get("location") or "").strip()
    keyword = (request.args.get("keyword") or "").strip() or "software engineer"
    posted = request.args.get("posted") or "week"
    if posted not in ("today", "week", "month"):
        posted = "week"
    experience = parse_experience(request.args.get("experience"))
    work_mode = parse_work_mode(request.args.get("work_mode"))
    remote_only = request.args.get("remote") == "1"
    selected = request.args.getlist("provider") or [key for key, _label in PROVIDER_OPTIONS]
    if not location:
        return redirect(url_for("job_discovery"))
    results = Orchestrator().job_search(
        selected,
        location,
        posted,
        keyword,
        None,
        experience=experience,
        remote_only=remote_only,
        work_mode=work_mode,
    )["results"]
    rows = []
    for bundle in results:
        for job in bundle.get("jobs") or []:
            rows.append([
                bundle.get("label"),
                job.get("title"),
                job.get("company"),
                job.get("location"),
                job.get("employment_type"),
                job.get("posted_days_ago"),
                job.get("description"),
            ])
    workbook = build_xlsx([
        (
            "Jobs",
            ["Provider", "Title", "Company", "Location", "Employment type", "Posted days ago", "Description"],
            rows,
        )
    ])
    return send_file(
        workbook,
        as_attachment=True,
        download_name="job-search.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/observability")
def observability_page():
    """Traces for agent steps, plus the local evaluation suite."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.path))
    if user["role"] == "candidate":
        return redirect(url_for("hub_page"))
    report = run_evaluations()
    return render_template(
        "observability.html",
        user=user,
        report=report,
        traces=recent_traces(limit=25),
        summary=trace_summary(),
        middleware_steps=pipeline_steps(),
    )


@app.route("/review/delete", methods=["POST"])
def review_delete():
    """Remove one stored resume from the Review candidate list."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.path))
    email = user.get("email") or ""
    name = (request.form.get("candidate") or "").strip()
    scan_id = scan_id_for(email, name) if name else ""
    delete_candidate_scan(email, name)
    if scan_id:
        RESULTS_CACHE.pop(scan_id, None)
        if session.get("last_analysis_id") == scan_id:
            session.pop("last_analysis_id", None)
    _bind_stored_scan(email)
    action = request.form.get("review_action") or "approve"
    if action not in ACTIONS:
        action = "approve"
    return redirect(url_for("review_role", role=user["role"], action=action))


@app.route("/review/ats-pdf")
def review_ats_pdf():
    """Download the reviewed resume as a PDF after mentor approval and ATS above 75%."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.path))
    case, state = _review_case()
    if not ats_pdf_ready(case, state):
        return redirect(url_for("review_role", role=user["role"], action="approve"))
    analysis_id = case.get("analysis_id")
    result = RESULTS_CACHE.get(analysis_id) if case.get("source") != "sample" else None
    return send_file(
        build_ats_pdf(result, case),
        as_attachment=True,
        download_name=pdf_download_name(case.get("candidate_name")),
        mimetype="application/pdf",
    )


@app.route("/review")
def review_home():
    """Open the signed-in role's review screen."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.path))
    return redirect(url_for("review_role", role=user["role"], action="approve"))


@app.route("/review/scenarios")
def review_scenarios_page():
    """Positive and negative cases for status, score, and share."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.path))
    if user["role"] == "candidate":
        return redirect(url_for("hub_page"))
    selected_role = request.args.get("role") or user["role"]
    selected_kind = request.args.get("kind") or "all"
    if selected_role not in ROLES and selected_role != "all":
        selected_role = "all"
    if selected_kind not in ("positive", "negative", "all"):
        selected_kind = "all"
    case, state = _review_case()
    return render_template(
        "scenarios.html",
        cases=review_scenarios(
            None if selected_role == "all" else selected_role,
            None if selected_kind == "all" else selected_kind,
        ),
        selected_role=selected_role,
        selected_kind=selected_kind,
        case=case,
        state=state,
        user=user,
        role_labels=ROLE_COPY,
    )


@app.route("/review/<role>", methods=["GET", "POST"])
def review_role(role):
    """Approve, reject, or edit a resume screen as the signed-in role."""
    if role not in ROLES:
        abort(404)
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.full_path))
    if user["role"] != role:
        return redirect(url_for("review_role", role=user["role"], action="approve", denied=1))
    action = request.values.get("action", "approve")
    if action not in ACTIONS:
        action = "approve"
    notice = None
    if request.args.get("denied"):
        notice = (
            f"You are signed in as {user['name']}, a {ROLE_COPY[user['role']]['label']}. "
            "That screen belongs to another role."
        )

    case, state = _review_case()
    form = {}
    errors = []
    receipt = None

    if request.method == "POST":
        form = {
            key: request.form.get(key, "")
            for key in (
                "confirm",
                "share_notice",
                "target_role",
                "note",
                "reason_code",
                "next_step",
                "stage",
                "notice",
                "field",
                "new_value",
            )
        }
        errors = validate(role, action, form)
        if not errors:
            with agent_middleware(
                "hitl.decision",
                "/review",
                actor=user["name"],
                role=role,
                action=action,
            ) as gate:
                current = gate.trace
                with current.span("apply"):
                    receipt = apply_action(role, action, form, case, state, actor_name=user["name"])
                with current.span("mail"):
                    mail = notify_decision(
                        role,
                        action,
                        case,
                        state,
                        user["name"],
                        (form.get("note") or "").strip(),
                    )
                current.meta["status"] = state.get("status")
                current.meta["requester"] = mail["requester"]
                current.meta["approver"] = mail["approver"]
            if mail["emailed"]:
                mail_line = "Sent"
            elif mail["failed"]:
                mail_line = "Failed: " + "; ".join(mail["failed"])
            else:
                mail_line = "Logged. Add SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM to .env to deliver it."
            receipt.extend([
                ["Requester email", mail["requester"]],
                ["Approver email", mail["approver"]],
                ["Mail", mail_line],
            ])
            session["review_receipt"] = receipt
            return redirect(url_for(
                "review_role",
                role=role,
                action=action,
                recorded=1,
                candidate=(request.form.get("candidate") or "").strip(),
            ))
    elif request.args.get("recorded"):
        receipt = session.pop("review_receipt", None)
        case, state = _review_case()

    old_values = {key: case.get(key, "") for key, _ in field_options(role)}
    return render_template(
        "review.html",
        role=role,
        action=action,
        case=case,
        state=state,
        screen=SCREEN[role][action],
        role_copy=ROLE_COPY[role],
        actor=user["name"],
        notice=notice,
        errors=errors,
        receipt=receipt,
        form=form,
        field_options=field_options(role),
        reason_options=reason_options(role, action),
        next_options=next_options(role),
        stage_options=stage_options(),
        notice_options=notice_options(role),
        old_values=old_values,
        ats_pdf_ready=ats_pdf_ready(case, state),
        candidates=list_candidates(user.get("email") or ""),
        selected_candidate="" if case.get("source") == "sample" else case.get("candidate_name") or "",
    )


def _candidate_only():
    """Voice practice is limited to a signed-in candidate."""
    user = _current_user()
    if user is None:
        return None, redirect(url_for("login", next="/voice"))
    if user["role"] != "candidate":
        return None, redirect(url_for("review_role", role=user["role"], action="approve", denied=1))
    return user, None


def _voice_turn():
    payload = request.get_json(silent=True) or {}
    topic = (payload.get("topic") or "").strip()
    if topic not in TOPICS:
        return None, None, (jsonify({"error": "Select a topic from the sidebar."}), 400)
    question = (payload.get("question") or "").strip()
    answer = (payload.get("answer") or "").strip()
    if question not in questions_for(topic):
        return None, None, (jsonify({"error": "That question is not in candidate_answers.xlsx."}), 400)
    if not answer:
        return None, None, (jsonify({"error": "Speak or type an answer first."}), 400)
    if len(answer) > 4000:
        answer = answer[:4000]
    return topic, {"question": question, "answer": answer}, None


@app.route("/voice")
def voice_assistant():
    """Practice screening interview with microphone transcript and Groq coaching."""
    _user, denied = _candidate_only()
    if denied:
        return denied
    return render_template("voice.html", topics=TOPICS, questions=load_catalog())


@app.route("/api/voice/reply", methods=["POST"])
def voice_reply():
    _user, denied = _candidate_only()
    if denied:
        return jsonify({"error": "Sign in as a candidate to practice."}), 401
    topic, turn, error = _voice_turn()
    if error:
        return error
    try:
        reply = reply_to_answer(topic, turn["question"], turn["answer"])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"reply": reply})


@app.route("/api/voice/feedback", methods=["POST"])
def voice_feedback():
    _user, denied = _candidate_only()
    if denied:
        return jsonify({"error": "Sign in as a candidate to practice."}), 401
    payload = request.get_json(silent=True) or {}
    topic = (payload.get("topic") or "").strip()
    if topic not in TOPICS:
        return jsonify({"error": "Select a topic from the sidebar."}), 400
    known = set(questions_for(topic))
    turns = []
    for item in payload.get("turns") or []:
        if not isinstance(item, dict):
            continue
        question = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()
        if question in known and answer:
            turns.append({"question": question, "answer": answer[:4000]})
    if not turns:
        return jsonify({"error": "Answer at least one question before asking for feedback."}), 400
    try:
        return jsonify(feedback_for(topic, turns[:12]))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


warm_matcher()

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  Unified AI Excellence Platform")
    print("  Starting server at http://localhost:5000")
    print("="*60 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
