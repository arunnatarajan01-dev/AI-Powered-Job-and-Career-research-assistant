"""Human review of a resume screen for candidate, hiring manager, and auditor."""

import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from parser.text_cleaning import extract_candidate_name
from werkzeug.security import check_password_hash, generate_password_hash

ROLES = ("candidate", "hiring_manager", "auditor")
ACTIONS = ("approve", "reject", "edit")

ACTORS = {
    "hiring_manager": "Arjun Mehta",
    "auditor": "Meera Iyer",
}

# Demo accounts for the three review roles. Shown on the sign-in page.
USERS = (
    {
        "email": "priya.sharma@email.com",
        "password": "candidate123",
        "name": "Priya Sharma",
        "role": "candidate",
    },
    {
        "email": "arjun.mehta@email.com",
        "password": "manager123",
        "name": "Arjun Mehta",
        "role": "hiring_manager",
    },
    {
        "email": "meera.iyer@email.com",
        "password": "auditor123",
        "name": "Meera Iyer",
        "role": "auditor",
    },
)

ROLE_COPY = {
    "candidate": {
        "label": "Candidate",
        "summary": "Confirm the extracted profile, dispute the screen, or correct a field before the score is treated as final.",
    },
    "hiring_manager": {
        "label": "Hiring manager",
        "summary": "Advance or reject the candidate for the open role, or override a parsed field and send the case back to pending.",
    },
    "auditor": {
        "label": "Auditor",
        "summary": "Sign off a complete decision record, reopen one that fails review, or append an annotation without changing the hiring outcome.",
    },
}

SCREEN = {
    "candidate": {
        "approve": {
            "title": "Confirm your profile",
            "submit": "Submit profile",
            "constraint": "You confirm the extracted profile. You do not set a hire or reject outcome.",
        },
        "reject": {
            "title": "Dispute this screening",
            "submit": "Dispute analysis",
            "constraint": "This stops the profile from being used as screened. It does not close a job.",
        },
        "edit": {
            "title": "Correct extracted fields",
            "submit": "Save correction",
            "constraint": "The corrected value is saved on this case. The ATS score and match percent stay at the original analysis.",
        },
    },
    "hiring_manager": {
        "approve": {
            "title": "Advance this candidate",
            "submit": "Advance candidate",
            "constraint": "This is the hiring decision for the role under review. The score stays a recommendation.",
        },
        "reject": {
            "title": "Reject for this requisition",
            "submit": "Reject candidate",
            "constraint": "A reason code and a written note are both stored with the decision.",
        },
        "edit": {
            "title": "Override a parsed field",
            "submit": "Save override",
            "constraint": "Saving returns the case to Pending. Advance or reject is a separate action.",
        },
    },
    "auditor": {
        "approve": {
            "title": "Sign off the decision record",
            "submit": "Sign off record",
            "constraint": "You attest the record is complete. You do not change the hiring outcome.",
        },
        "reject": {
            "title": "Reopen a non-compliant decision",
            "submit": "Reopen record",
            "constraint": "The original decision stays in the history. Reopen sends the case back for a human decision.",
        },
        "edit": {
            "title": "Annotate the record",
            "submit": "Save annotation",
            "constraint": "The annotation is appended. Approve and reject on the original decision stay as recorded.",
        },
    },
}

SAMPLE_ANALYSIS_ID = "a8f3c1e2-4b91-4d0a-9c77-1e2b6f0a91d4"

CASE_STATE = {}
_NEXT_DECISION = 2041
_REGISTERED_PATH = Path(__file__).resolve().parent / "data" / "registered_users.json"
_RESET_PATH = Path(__file__).resolve().parent / "data" / "password_resets.json"
_RESET_MINUTES = 30
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _profile(user):
    return {
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
    }


def _load_registered():
    if not _REGISTERED_PATH.exists():
        return []
    try:
        payload = json.loads(_REGISTERED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _save_registered(users):
    _REGISTERED_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REGISTERED_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _email_taken(email_value):
    for user in USERS:
        if user["email"].lower() == email_value:
            return True
    for user in _load_registered():
        if str(user.get("email", "")).lower() == email_value:
            return True
    return False


def register_account(name, email, password):
    """Create a candidate account. Returns an error message, or None on success."""
    name_value = " ".join((name or "").split())
    email_value = (email or "").strip().lower()
    password_value = password or ""
    missing = []
    if not name_value:
        missing.append("Name")
    if not email_value:
        missing.append("Email")
    if not password_value:
        missing.append("New Password")
    if missing:
        verb = "is" if len(missing) == 1 else "are"
        return f"{', '.join(missing)} {verb} required."
    if _EMAIL_RE.match(email_value) is None:
        return "Enter a valid email address."
    if _email_taken(email_value):
        return "An account with this email already exists."
    users = _load_registered()
    users.append({
        "email": email_value,
        "password_hash": generate_password_hash(password_value),
        "name": name_value,
        "role": "candidate",
    })
    _save_registered(users)
    return None


def issue_reset_token(email):
    """Store a short-lived reset token for a registered account."""
    email_value = (email or "").strip().lower()
    if _EMAIL_RE.match(email_value) is None:
        return "Enter a valid email address.", None
    for user in USERS:
        if user["email"].lower() == email_value:
            return "Demo account passwords are listed on the login page.", None
    if not any(str(user.get("email", "")).lower() == email_value for user in _load_registered()):
        return "No account uses that email.", None
    token = secrets.token_urlsafe(32)
    pending = _load_resets()
    pending[token] = {
        "email": email_value,
        "expires": (datetime.now(timezone.utc) + timedelta(minutes=_RESET_MINUTES)).isoformat(),
    }
    _save_resets(pending)
    return None, token


def apply_reset_token(token, password):
    """Set a new password when the emailed token is still valid."""
    password_value = password or ""
    if not password_value:
        return "New Password is required."
    pending = _load_resets()
    record = pending.get(token or "")
    if not record:
        return "This reset link is invalid or has already been used."
    expires = datetime.fromisoformat(record["expires"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        pending.pop(token, None)
        _save_resets(pending)
        return "This reset link has expired. Request a new one."
    email_value = record["email"]
    users = _load_registered()
    matched = False
    for user in users:
        if str(user.get("email", "")).lower() != email_value:
            continue
        user["password_hash"] = generate_password_hash(password_value)
        matched = True
        break
    if not matched:
        return "No account uses that email."
    _save_registered(users)
    pending.pop(token, None)
    _save_resets(pending)
    return None


def _load_resets():
    if not _RESET_PATH.exists():
        return {}
    try:
        payload = json.loads(_RESET_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _save_resets(pending):
    _RESET_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RESET_PATH.write_text(json.dumps(pending, indent=2), encoding="utf-8")


def public_users():
    """Demo accounts on the login page. Auditor is omitted; hiring manager is shown as Mentor."""
    visible = []
    for user in USERS:
        if user["role"] == "auditor":
            continue
        label = ROLE_COPY[user["role"]]["label"]
        if user["role"] == "hiring_manager":
            label = "Mentor"
        visible.append({
            "email": user["email"],
            "password": user["password"],
            "name": user["name"],
            "role": user["role"],
            "label": label,
        })
    return visible


def authenticate(email, password):
    """Return the signed-in profile, or None when the email or password does not match."""
    email_value = (email or "").strip().lower()
    password_value = password or ""
    for user in USERS:
        if user["email"].lower() != email_value:
            continue
        password_ok = (
            len(password_value) == len(user["password"])
            and hmac.compare_digest(user["password"], password_value)
        )
        if password_ok:
            return _profile(user)
    for user in _load_registered():
        if str(user.get("email", "")).lower() != email_value:
            continue
        password_hash = user.get("password_hash") or ""
        if password_hash and check_password_hash(password_hash, password_value):
            return _profile(user)
    return None


def _now():
    return datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def _decision_id():
    global _NEXT_DECISION
    value = f"DEC-{_NEXT_DECISION}"
    _NEXT_DECISION += 1
    return value


def ensure_state(analysis_id):
    state = CASE_STATE.get(analysis_id)
    if state is None:
        state = {
            "status": "Pending",
            "prior_status": "",
            "audit_status": "Not reviewed",
            "overrides": {},
            "annotations": [],
            "decision_id": _decision_id(),
            "history": [],
            "share": "Not granted",
            "candidate_notice": "Not recorded",
            "mentor_approved": False,
        }
        CASE_STATE[analysis_id] = state
    return state


def _education_text(education):
    if not education:
        return "Not extracted"
    parts = []
    for entry in education:
        if not isinstance(entry, dict):
            continue
        bits = [entry.get("degree"), entry.get("year")]
        text = " ".join(bit for bit in bits if bit) or (entry.get("raw") or "")
        if text:
            parts.append(text)
    return "; ".join(parts) or "Not extracted"


def build_case(result, analysis_id):
    """Map a stored analysis, or the sample screen, into review fields."""
    if not result:
        analysis_id = SAMPLE_ANALYSIS_ID
        case = {
            "analysis_id": analysis_id,
            "source": "sample",
            "filename": "priya_sharma_resume.pdf",
            "candidate_name": "Priya Sharma",
            "email": "priya.sharma@email.com",
            "phone": "+91 98XXXXXX10",
            "ats_percentage": 72,
            "ats_grade": "B",
            "ats_label": "Good",
            "top_title": "Data Analyst",
            "fit": "Moderate Fit",
            "skill_match": 64,
            "skills": "Python, SQL, TensorFlow, Pandas, Git",
            "experience_years": "3",
            "education": "B.Tech Computer Science, 2022",
            "section_text": "Built ranking models for product search using Python and SQL.",
            "target_role_options": [
                "Machine Learning Engineer",
                "Data Scientist",
                "Data Analyst",
            ],
            "requisition": "REQ-1842 · Machine Learning Engineer",
            "ai_time": "30 Sep 2026, 17:12 UTC",
        }
    else:
        recommendations = result.get("recommendations") or []
        top = recommendations[0] if recommendations else {}
        titles = []
        for job in recommendations[:6]:
            title = (job.get("title") or "").strip()
            if title and title not in titles:
                titles.append(title)
        if not titles:
            titles = ["Software Engineer"]
        skills = result.get("skill_names") or []
        contact = result.get("contact") or {}
        extracted_email = (contact.get("email") or "").strip()
        if "@" not in extracted_email:
            extracted_email = "priya.sharma@email.com"
        section_text = (result.get("experience_excerpt") or "Experience section was not stored with this analysis.")[:400]
        case = {
            "analysis_id": analysis_id,
            "source": "session",
            "filename": result.get("filename") or "resume",
            "candidate_name": (
                (result.get("candidate_name") or "").strip()
                or extract_candidate_name(result.get("resume_text") or "")
                or "Candidate"
            ),
            "email": extracted_email,
            "phone": contact.get("phone") or "Not extracted",
            "ats_percentage": (result.get("ats") or {}).get("percentage", 0),
            "ats_grade": (result.get("ats") or {}).get("grade", "—"),
            "ats_label": (result.get("ats") or {}).get("grade_label", ""),
            "top_title": top.get("title") or "No matching role",
            "fit": top.get("fit_level") or "—",
            "skill_match": top.get("skill_match_percent", 0),
            "skills": ", ".join(skills) if skills else "None extracted",
            "experience_years": str(result.get("experience_years", 0)),
            "education": _education_text(result.get("education")),
            "section_text": section_text,
            "target_role_options": titles,
            "requisition": f"Role under review · {top.get('title') or titles[0]}",
            "ai_time": "This browser session",
        }

    state = ensure_state(case["analysis_id"])
    display = dict(case)
    for key, value in state["overrides"].items():
        if key in display:
            display[key] = value
    if state["overrides"].get("target_role"):
        display["top_title"] = state["overrides"]["target_role"]
    display.setdefault("target_role", display["top_title"])
    display["decision_reason"] = state.get("latest_note") or "No hiring decision recorded yet."
    display["ats_score"] = f"{case['ats_percentage']} · {case['ats_grade']} · {case['ats_label']}"
    return display, state


def mentor_approved(state):
    """True after the mentor (hiring manager) has advanced this resume."""
    if not state:
        return False
    if "mentor_approved" in state:
        return bool(state["mentor_approved"])
    return str(state.get("status") or "").startswith("Advanced")


def ats_pdf_ready(case, state):
    """Resume PDF download opens after mentor approval and an ATS score above 75%."""
    try:
        score = float(case.get("ats_percentage"))
    except (TypeError, ValueError):
        return False
    return score > 75 and mentor_approved(state)


def field_options(role):
    if role == "candidate":
        return [
            ("skills", "Skills"),
            ("experience_years", "Years of experience"),
            ("target_role", "Target role"),
            ("education", "Education"),
            ("email", "Email"),
            ("phone", "Phone"),
        ]
    if role == "hiring_manager":
        return [
            ("skills", "Skills"),
            ("experience_years", "Years of experience"),
            ("target_role", "Target role"),
            ("section_text", "Section text"),
        ]
    return [
        ("decision_reason", "Decision reason"),
        ("skills", "Skills"),
        ("target_role", "Target role"),
        ("ats_score", "ATS score"),
    ]


def reason_options(role, action):
    if action == "edit" and role == "auditor":
        return [
            ("note", "Note"),
            ("correction_request", "Ask the hiring manager to correct it"),
        ]
    if role == "candidate":
        return [
            ("wrong_skills", "Wrong skills"),
            ("wrong_experience", "Wrong experience"),
            ("wrong_role", "Wrong role"),
            ("withdraw", "Withdraw"),
            ("other", "Other"),
        ]
    if role == "hiring_manager":
        return [
            ("skills_gap", "Skills gap"),
            ("experience", "Experience below the posting"),
            ("role_mismatch", "Role mismatch"),
            ("unreadable", "Resume unreadable"),
            ("other", "Other"),
        ]
    return [
        ("missing_reason", "Missing reason"),
        ("score_only", "Score-only decision"),
        ("edit_without_values", "Edit without old and new values"),
        ("wrong_requisition", "Wrong requisition"),
        ("parser_not_reviewed", "Parser not reviewed"),
    ]


def next_options(role):
    if role == "candidate":
        return [("reupload", "Re-upload"), ("correct", "Correct and resubmit")]
    if role == "hiring_manager":
        return [
            ("close", "Close for this requisition"),
            ("keep", "Keep for another requisition"),
        ]
    return [
        ("return", "Return to the hiring manager"),
        ("flag", "Leave the decision and flag it"),
    ]


def stage_options():
    return [
        ("screen", "Recruiter screen"),
        ("hm", "Hiring-manager interview"),
        ("onsite", "Onsite"),
    ]


def notice_options(role):
    if role == "auditor":
        return [
            ("yes", "Yes, notice matches the record"),
            ("no", "No"),
            ("missing", "Missing from the record"),
        ]
    return [("yes", "Yes"), ("no", "No")]


def _label(options, value):
    for key, label in options:
        if key == value:
            return label
    return value


def _checked(form, name):
    return form.get(name) == "on"


def validate(role, action, form):
    errors = []
    note = (form.get("note") or "").strip()
    if len(note) > 1000:
        errors.append("Note must be 1000 characters or fewer.")
    new_value = (form.get("new_value") or "").strip()
    if len(new_value) > 500:
        errors.append("The new value must be 500 characters or fewer.")

    if action == "approve" and role == "candidate":
        if not _checked(form, "confirm"):
            errors.append("Confirm that the extracted profile is accurate.")
        if not (form.get("target_role") or "").strip():
            errors.append("Select a target role.")
        if not _checked(form, "share_notice"):
            errors.append("Confirm that a hiring manager may see this profile.")
    elif action == "approve" and role == "hiring_manager":
        if not _checked(form, "confirm"):
            errors.append("Confirm that you reviewed the resume, not only the score.")
        if form.get("stage") not in {key for key, _ in stage_options()}:
            errors.append("Select the next stage.")
        if not note:
            errors.append("Enter a decision note.")
    elif action == "approve" and role == "auditor":
        if not _checked(form, "confirm"):
            errors.append("Confirm that reviewer, reason, and original score are present.")
        if not note:
            errors.append("Describe what was checked.")
        if form.get("notice") not in {key for key, _ in notice_options(role)}:
            errors.append("Select the candidate notice status.")
    elif action == "reject":
        allowed_reasons = {key for key, _ in reason_options(role, action)}
        if form.get("reason_code") not in allowed_reasons:
            errors.append("Select a reason code.")
        if not note:
            errors.append("Enter a written note.")
        if form.get("next_step") not in {key for key, _ in next_options(role)}:
            errors.append("Select what happens next.")
        if not _checked(form, "confirm"):
            errors.append("Confirm this rejection.")
        if role != "candidate" and form.get("notice") not in {key for key, _ in notice_options(role)}:
            errors.append("Select whether the candidate is told.")
    elif action == "edit":
        allowed_fields = {key for key, _ in field_options(role)}
        if form.get("field") not in allowed_fields:
            errors.append("Select a field.")
        if not new_value:
            errors.append("Enter the new value." if role != "auditor" else "Enter the annotation.")
        if not note:
            errors.append("Enter a reason.")
        if role == "auditor" and form.get("reason_code") not in {key for key, _ in reason_options(role, action)}:
            errors.append("Select an annotation type.")
    return errors


def _account(role):
    for user in USERS:
        if user["role"] == role:
            return user["email"], user["name"]
    return "", role


def decision_parties(role, case):
    """Requester is the candidate. Approver is the hiring manager, unless an auditor acted."""
    candidate_email, candidate_name = _account("candidate")
    extracted = (case.get("email") or "").strip()
    requester_email = extracted if "@" in extracted else candidate_email
    if role == "auditor":
        approver_email, approver_name = _account("auditor")
    else:
        approver_email, approver_name = _account("hiring_manager")
    return {
        "requester": {
            "email": requester_email,
            "name": case.get("candidate_name") or candidate_name,
            "party": "requester",
        },
        "approver": {
            "email": approver_email,
            "name": approver_name,
            "party": "approver",
        },
    }


def notify_decision(role, action, case, state, actor_name, note):
    """Email the requester and the approver about an approve, reject, or edit."""
    from safety.review_mail import notify_parties

    parties = decision_parties(role, case)
    subject = (
        f"[IntegrateAI] {action} recorded for {case.get('candidate_name') or 'candidate'}"
    )

    def body_for(party):
        return "\n".join([
            f"Hello {party['name']},",
            "",
            "A review decision was recorded on the career assistant.",
            f"Your role on this message: {party['party']}",
            f"Action: {action}",
            f"Recorded by: {actor_name} ({ROLE_COPY[role]['label']})",
            f"Candidate: {case.get('candidate_name')}",
            f"Email: {parties['requester']['email']}",
            f"Case status: {state.get('status')}",
            f"Audit status: {state.get('audit_status')}",
            f"ATS score: {case.get('ats_score')}",
            f"Note: {note or 'None'}",
        ])

    payload = []
    for key in ("requester", "approver"):
        item = dict(parties[key])
        item["action"] = action
        item["role"] = role
        payload.append(item)
    result = notify_parties(payload, subject, body_for)
    result["requester"] = parties["requester"]["email"]
    result["approver"] = parties["approver"]["email"]
    return result


def _actor_name(role, case):
    if role == "candidate":
        return case.get("candidate_name") or "Candidate"
    return ACTORS[role]


def apply_action(role, action, form, case, state, actor_name=None):
    """Record the action and update case status. Returns receipt rows."""
    note = (form.get("note") or "").strip()
    recorded = _now()
    actor = actor_name or _actor_name(role, case)
    field = form.get("field") or ""
    old_value = ""
    if action == "edit":
        old_value = str(case.get(field, ""))

    if action == "approve" and role == "candidate":
        state["prior_status"] = state["status"]
        state["status"] = "Profile confirmed"
        state["overrides"]["target_role"] = form.get("target_role")
        state["latest_note"] = note or "Profile confirmed by the candidate."
        state["share"] = "Yes"
    elif action == "approve" and role == "hiring_manager":
        state["prior_status"] = state["status"]
        state["status"] = f"Advanced · {_label(stage_options(), form.get('stage'))}"
        state["latest_note"] = note
        state["decision_id"] = _decision_id()
        state["mentor_approved"] = True
    elif action == "approve" and role == "auditor":
        state["audit_status"] = "Signed off"
        state["latest_note"] = note
        state["candidate_notice"] = _label(notice_options(role), form.get("notice"))
    elif action == "reject" and role == "candidate":
        state["prior_status"] = state["status"]
        state["status"] = "Disputed"
        state["latest_note"] = note
    elif action == "reject" and role == "hiring_manager":
        state["prior_status"] = state["status"]
        state["status"] = "Rejected"
        state["latest_note"] = note
        state["decision_id"] = _decision_id()
        state["candidate_notice"] = _label(notice_options(role), form.get("notice"))
        state["mentor_approved"] = False
    elif action == "reject" and role == "auditor":
        state["prior_status"] = state["status"]
        state["audit_status"] = "Reopened"
        state["latest_note"] = note
        if form.get("next_step") == "return":
            state["status"] = "Pending"
            state["mentor_approved"] = False
        state["candidate_notice"] = _label(notice_options(role), form.get("notice"))
    elif action == "edit" and role == "auditor":
        state["annotations"].append({
            "field": _label(field_options(role), field),
            "old": old_value,
            "new": (form.get("new_value") or "").strip(),
            "kind": _label(reason_options(role, action), form.get("reason_code")),
            "reason": note,
            "at": recorded,
        })
    elif action == "edit":
        state["prior_status"] = state["status"]
        state["status"] = "Pending"
        state["mentor_approved"] = False
        state["overrides"][field] = (form.get("new_value") or "").strip()
        state["latest_note"] = note

    receipt = [
        ["Action", action],
        ["Actor", f"{actor} · {ROLE_COPY[role]['label']}"],
        ["Analysis id", case["analysis_id"]],
        ["Decision id", state["decision_id"]],
        ["AI score at decision", case["ats_score"]],
        ["Case status", state["status"]],
        ["Audit status", state["audit_status"]],
        ["Recorded", recorded],
    ]
    if role != "candidate":
        receipt.append(["Requisition", case["requisition"]])
    if action == "approve" and role == "candidate":
        receipt.extend([
            ["Target role", form.get("target_role")],
            ["Share notice", "Yes"],
        ])
    if action == "approve" and role == "hiring_manager":
        receipt.extend([
            ["Outcome", "Advance"],
            ["Next stage", _label(stage_options(), form.get("stage"))],
            ["Note", note],
        ])
    if action == "approve" and role == "auditor":
        receipt.extend([
            ["Outcome", "Compliant"],
            ["Candidate notice", _label(notice_options(role), form.get("notice"))],
            ["Note", note],
        ])
    if action == "reject":
        receipt.extend([
            ["Reason code", _label(reason_options(role, action), form.get("reason_code"))],
            ["Note", note],
            ["Next", _label(next_options(role), form.get("next_step"))],
        ])
        if role != "candidate":
            receipt.append(["Candidate notice", _label(notice_options(role), form.get("notice"))])
    if action == "edit":
        receipt.extend([
            ["Field", _label(field_options(role), field)],
            ["Old value", old_value],
            ["New value", (form.get("new_value") or "").strip()],
            ["Reason", note],
        ])
        if role == "auditor":
            receipt.append(["Hiring outcome", "Unchanged"])
        else:
            receipt.append(["Case status after edit", "Pending"])

    state["history"].insert(0, {
        "at": recorded,
        "role": ROLE_COPY[role]["label"],
        "action": action,
        "summary": note or state["status"],
    })
    state["history"] = state["history"][:8]
    return receipt


USE_CASES = (
    {
        "role": "candidate",
        "kind": "positive",
        "focus": "Status",
        "use_case": "Priya confirms an accurate Pending profile and selects Machine Learning Engineer.",
        "start": "Pending · audit Not reviewed",
        "result": "Status becomes Profile confirmed. The case can be reviewed by a hiring manager.",
    },
    {
        "role": "candidate",
        "kind": "negative",
        "focus": "Status",
        "use_case": "Priya submits Approve without confirming that the extracted profile is accurate.",
        "start": "Pending",
        "result": "Nothing is recorded. Status stays Pending.",
    },
    {
        "role": "candidate",
        "kind": "positive",
        "focus": "Score",
        "use_case": "ATS 72 is borderline. Priya corrects a missed skill and gives a reason. She does not type a new score.",
        "start": "72 · B · Good · 64% skill match",
        "result": "The skill text is saved. Status returns to Pending. The score stays 72 · B · Good.",
    },
    {
        "role": "candidate",
        "kind": "negative",
        "focus": "Score",
        "use_case": "Priya wants the ATS percentage raised. The edit list has skills, experience, role, education, email, and phone only.",
        "start": "72 · B · Good",
        "result": "The score cannot be edited. Status and share stay unchanged.",
    },
    {
        "role": "candidate",
        "kind": "positive",
        "focus": "Share",
        "use_case": "Priya checks that a hiring manager may see the profile, confirms accuracy, and selects a target role.",
        "start": "Share not granted",
        "result": "Share notice is Yes. Status becomes Profile confirmed.",
    },
    {
        "role": "candidate",
        "kind": "negative",
        "focus": "Share",
        "use_case": "Priya confirms accuracy and a target role, and leaves the share checkbox empty.",
        "start": "Share not granted",
        "result": "Submit stays blocked. The profile is not shared. Status stays Pending.",
    },
    {
        "role": "hiring_manager",
        "kind": "positive",
        "focus": "Status",
        "use_case": "Arjun reads the resume, chooses Recruiter screen, and writes why the person advances.",
        "start": "Pending or Profile confirmed",
        "result": "Status becomes Advanced · Recruiter screen. A new decision id is stored.",
    },
    {
        "role": "hiring_manager",
        "kind": "negative",
        "focus": "Status",
        "use_case": "Arjun presses Advance with no stage and no decision note.",
        "start": "Pending",
        "result": "Nothing is recorded. Status stays Pending.",
    },
    {
        "role": "hiring_manager",
        "kind": "positive",
        "focus": "Score",
        "use_case": "Score is 72 and skill match is 64%. Arjun advances because the resume projects cover the gap, and the note says so.",
        "start": "72 · B · Good · 64% skill match",
        "result": "Status becomes Advanced. The receipt keeps 72 · B · Good as context, not as the decision.",
    },
    {
        "role": "hiring_manager",
        "kind": "negative",
        "focus": "Score",
        "use_case": "Arjun rejects with a completed form whose note only says the score is too low.",
        "start": "72 · B · Good",
        "result": "Status becomes Rejected. This is a score-only decision an auditor can reopen.",
    },
    {
        "role": "hiring_manager",
        "kind": "positive",
        "focus": "Share",
        "use_case": "Arjun rejects for a named skills gap and sets candidate notice to Yes.",
        "start": "Candidate has not been told",
        "result": "Status becomes Rejected. The record says the candidate is told.",
    },
    {
        "role": "hiring_manager",
        "kind": "negative",
        "focus": "Share",
        "use_case": "Arjun fills the reason, note, and next step, and leaves candidate notice empty.",
        "start": "Candidate has not been told",
        "result": "Nothing is recorded. Status stays unchanged and no notice is sent.",
    },
    {
        "role": "auditor",
        "kind": "positive",
        "focus": "Status",
        "use_case": "Meera finds a reviewer, a reason, and the original score on a finished decision, then signs off.",
        "start": "Advanced or Rejected · audit Not reviewed",
        "result": "Audit becomes Signed off. The hiring status stays as recorded.",
    },
    {
        "role": "auditor",
        "kind": "negative",
        "focus": "Status",
        "use_case": "The decision has no written reason. Meera reopens it and sends it back to the hiring manager.",
        "start": "Rejected · audit Not reviewed",
        "result": "Audit becomes Reopened. Status returns to Pending.",
    },
    {
        "role": "auditor",
        "kind": "positive",
        "focus": "Score",
        "use_case": "Meera signs off after checking the receipt still shows 72 · B · Good and the note does not use that number as the reason.",
        "start": "72 · B · Good on the receipt",
        "result": "Audit becomes Signed off. The original score stays on the record.",
    },
    {
        "role": "auditor",
        "kind": "negative",
        "focus": "Score",
        "use_case": "The hiring note is only “score too low.” Meera records a score-only finding and returns the case.",
        "start": "72 · B · Good · status Rejected",
        "result": "Audit becomes Reopened. Status returns to Pending for a new human decision.",
    },
    {
        "role": "auditor",
        "kind": "positive",
        "focus": "Share",
        "use_case": "The record says the candidate was told, and that matches the notice. Meera selects Yes and signs off.",
        "start": "Candidate notice Yes",
        "result": "Audit becomes Signed off. The share record matches what the candidate was told.",
    },
    {
        "role": "auditor",
        "kind": "negative",
        "focus": "Share",
        "use_case": "No notice was stored. Meera leaves candidate notice blank. Choosing Missing and still signing off does not repair the missing share.",
        "start": "Candidate notice missing",
        "result": "A blank notice blocks sign-off. Choosing Missing still sets audit to Signed off.",
    },
)


def review_scenarios(role=None, kind=None):
    """Return the status, score, and share cases, optionally filtered."""
    rows = []
    for item in USE_CASES:
        if role in ROLES and item["role"] != role:
            continue
        if kind in ("positive", "negative") and item["kind"] != kind:
            continue
        row = dict(item)
        row["role_label"] = ROLE_COPY[item["role"]]["label"]
        row["kind_label"] = "Positive" if item["kind"] == "positive" else "Negative"
        rows.append(row)
    return rows
