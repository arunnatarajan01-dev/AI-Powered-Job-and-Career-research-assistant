"""
AI-Powered Excellence Platform
Main Entry Point
"""
import os
import sys
import uuid
import json
from flask import Flask, abort, render_template, request, jsonify, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv

from agents import Orchestrator
from evaluations import run_evaluations
from exports.xlsx import build_xlsx
from hitl import (
    ACTIONS,
    ROLE_COPY,
    ROLES,
    SCREEN,
    apply_action,
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
)
from jobs import CITIES, POSTED_LABELS
from middleware import agent_middleware, pipeline_steps
from observability import recent_traces, trace_summary
from safety.admin_alert import notify_admin
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
from parser.text_cleaning import clean_text, extract_email, extract_phone, extract_links
from parser.section_extractor import extract_sections, extract_education_details, extract_experience_years
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

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)


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
    return url_for("index")

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
    """Landing page for a signed-in user."""
    if _current_user() is None:
        return redirect(url_for("login"))
    return render_template('index.html')

# ========================================================
# --- RESUME ANALYZER ROUTES ---
# ========================================================

def _block_staff():
    """Hiring managers and auditors do not use the candidate career pages."""
    user = _current_user()
    if user and user["role"] in ("hiring_manager", "auditor"):
        return redirect(url_for("index"))
    return None


@app.route('/resume')
def resume_home():
    """Resume Analyzer upload page."""
    blocked = _block_staff()
    if blocked:
        return blocked
    return render_template('resume_index.html')

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
            RESULTS_CACHE[analysis_id] = result
            session['last_analysis_id'] = analysis_id
            return jsonify({'success': True, 'redirect': url_for('dashboard')})

    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/dashboard')
def dashboard():
    """Results dashboard. Empty until a resume is analyzed in this session."""
    blocked = _block_staff()
    if blocked:
        return blocked
    analysis_id = session.get('last_analysis_id')
    result = RESULTS_CACHE.get(analysis_id) if analysis_id else None
    return render_template('dashboard.html', result=result)


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
    analysis_id = session.get("last_analysis_id")
    result = RESULTS_CACHE.get(analysis_id) if analysis_id else None
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
    analysis_id = session.get("last_analysis_id")
    result = RESULTS_CACHE.get(analysis_id) if analysis_id else None
    if result is None:
        return build_case(None, None)
    return build_case(result, analysis_id)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Sign in as a candidate, hiring manager, or auditor."""
    error = None
    next_url = _safe_review_next(request.values.get("next"))
    if request.method == "POST":
        user = authenticate(request.form.get("email"), request.form.get("password"))
        if user is None:
            error = "That email and password do not match a review account."
        else:
            session["user"] = user
            return redirect(_landing_for(user, next_url))
    if _current_user() and request.method == "GET" and not error:
        return redirect(_landing_for(_current_user(), next_url))
    return render_template("login.html", error=error, users=public_users(), next_url=next_url or "")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


@app.route("/jobs")
def job_discovery():
    """Search LinkedIn and Naukri adapters by location and posted date."""
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=request.full_path))
    if user["role"] != "candidate":
        return redirect(url_for("review_role", role=user["role"], action="approve", denied=1))

    analysis = RESULTS_CACHE.get(session.get("last_analysis_id"))
    recommendations = (analysis or {}).get("recommendations") or []
    suggested = recommendations[0] if recommendations else {}
    location = (request.args.get("location") or "").strip()
    if not location and "location" not in request.args:
        location = str(suggested.get("location") or "").split(",")[0].strip()
    keyword = (request.args.get("keyword") or "").strip()
    if not keyword:
        keyword = str(suggested.get("title") or "software engineer").strip()
    posted = request.args.get("posted") or "week"
    if posted not in ("today", "week", "month"):
        posted = "week"
    selected = request.args.getlist("provider")
    searched = "location" in request.args
    error = None
    results = []
    if searched:
        if not location:
            error = "Enter a location."
        elif not selected:
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
                with current.span("providers", keyword=keyword):
                    results = Orchestrator().job_search(
                        selected, location, posted, keyword, current
                    )["results"]
                current.meta["source_count"] = len(results)
                current.meta["job_count"] = sum(len(item.get("jobs") or []) for item in results)
    else:
        selected = ["linkedin", "naukri"]

    return render_template(
        "jobs.html",
        user=user,
        location=location,
        keyword=keyword,
        posted=posted,
        selected=selected,
        posted_labels=POSTED_LABELS,
        cities=CITIES,
        searched=searched and not error,
        error=error,
        results=results,
    )


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
    selected = request.args.getlist("provider") or ["linkedin", "naukri"]
    if not location:
        return redirect(url_for("job_discovery"))
    results = Orchestrator().job_search(selected, location, posted, keyword, None)["results"]
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
    report = run_evaluations()
    return render_template(
        "observability.html",
        user=user,
        report=report,
        traces=recent_traces(limit=25),
        summary=trace_summary(),
        middleware_steps=pipeline_steps(),
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
    selected_role = request.args.get("role") or (user["role"] if user else "all")
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
            return redirect(url_for("review_role", role=role, action=action, recorded=1))
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
    )


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  Unified AI Excellence Platform")
    print("  Starting server at http://localhost:5000")
    print("="*60 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
