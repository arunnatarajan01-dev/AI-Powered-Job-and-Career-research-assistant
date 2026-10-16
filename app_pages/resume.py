import streamlit as st

from memory.session_store import (
    add_message,
    answer_from_memory,
    load_memory,
    remember_analysis,
)
from safety.guardrail import check_text
from streamlit_logic import (
    AnalysisError,
    analysis_workbook,
    analyze_resume,
    gap_rows,
    recommendation_rows,
    roadmap_rows,
)

st.header("Resume")
st.caption("PDF or DOCX, up to the text the parser can read. Scoring and role matching stay local.")

with st.form("resume_form", clear_on_submit=False):
    uploaded = st.file_uploader("Resume file", type=["pdf", "docx", "doc"])
    submitted = st.form_submit_button("Analyze resume", type="primary")

if submitted:
    if uploaded is None:
        st.error("Choose a PDF or DOCX file.")
    else:
        with st.spinner("Reading the resume and matching roles"):
            try:
                st.session_state.analysis = analyze_resume(uploaded.name, uploaded.getvalue())
                remember_analysis(
                    st.session_state.memory_id,
                    "streamlit",
                    st.session_state.analysis,
                )
            except AnalysisError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")

result = st.session_state.analysis
if not result:
    st.info("Analyze a resume to see the score, matched roles, and learning roadmap.")
    st.stop()

contact = result.get("contact") or {}
ats = result.get("ats") or {}
name = result.get("candidate_name") or result.get("filename") or "Resume"

st.subheader(name)
st.caption(" · ".join(part for part in (contact.get("email"), contact.get("phone"), result.get("filename")) if part))

with st.container(horizontal=True):
    st.metric("ATS score", f"{ats.get('percentage', '—')}%", border=True)
    st.metric("Grade", f"{ats.get('grade', '—')} · {ats.get('grade_label', '')}", border=True)
    st.metric("Experience", f"{result.get('experience_years', 0)} years", border=True)
    st.metric("Skills", len(result.get("skill_names") or []), border=True)

if result.get("summary"):
    st.write(result["summary"])

workbook = analysis_workbook(result)
st.download_button(
    "Download Excel",
    data=workbook.getvalue(),
    file_name="resume-analysis.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    icon=":material/download:",
)

st.subheader("Matched roles")
roles = recommendation_rows(result)
if roles:
    st.dataframe(roles, width="stretch", hide_index=True)
else:
    st.info("No catalog roles matched this resume.")

left, right = st.columns(2)
with left:
    st.subheader("Skill gaps")
    gaps = gap_rows(result)
    if gaps:
        st.dataframe(gaps, width="stretch", hide_index=True)
    else:
        st.info("No missing skills stood out against the top roles.")
    if result.get("total_learning_time"):
        st.caption(f"Roadmap time: {result['total_learning_time']}")

with right:
    st.subheader("Roadmap")
    steps = roadmap_rows(result)
    if steps:
        st.dataframe(steps, width="stretch", hide_index=True)
    else:
        st.info("The roadmap is empty because there were no skill gaps to plan.")

skills_by_category = result.get("skills_by_category") or {}
if skills_by_category:
    st.subheader("Skills")
    skill_rows = [
        {"Category": category, "Skills": ", ".join(names)}
        for category, names in skills_by_category.items()
        if names
    ]
    st.dataframe(skill_rows, width="stretch", hide_index=True)

education = result.get("education") or []
if education:
    st.subheader("Education")
    st.dataframe(education, width="stretch", hide_index=True)

paths = result.get("career_paths") or []
if paths:
    st.subheader("Career paths")
    for path in paths:
        with st.container(border=True):
            st.markdown(f"**{path.get('path')}** · {path.get('match_percentage')}% match")
            st.caption(
                f"{path.get('current_level')} → {path.get('next_level')} · {path.get('industry_demand')} demand"
            )
            missing = path.get("missing_skills") or []
            if missing:
                st.write("Still to learn: " + ", ".join(missing))

feedback = result.get("feedback") or []
if feedback:
    st.subheader("Feedback")
    for item in feedback:
        with st.expander(f"{item.get('priority', '').title()} · {item.get('title')}"):
            st.write(item.get("suggestion") or "")

memory = load_memory(st.session_state.memory_id)
if not memory["candidates"] and result:
    remember_analysis(st.session_state.memory_id, "streamlit", result)
    memory = load_memory(st.session_state.memory_id)

st.header("Session memory")
st.caption("Jobs, this candidate, evidence, rankings, and chat stay in SQLite until you log out.")

person = (memory["candidates"] or [{}])[0]
if person:
    st.subheader("Candidate")
    st.write(
        f"{person.get('name') or 'Candidate'} · {person.get('email') or 'no email'} · "
        f"{person.get('experience_years')} years · {person.get('filename') or ''}"
    )
    st.write(person.get("skills") or "")

st.subheader("Jobs")
job_table = [
    {
        "Source": job["source"],
        "Role": job["title"],
        "Company": job["company"],
        "Location": job["location"],
        "Score": job["match_score"],
        "Link": job["url"],
    }
    for job in memory["jobs"]
]
if job_table:
    st.dataframe(
        job_table,
        width="stretch",
        hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Link")},
    )
else:
    st.info("No jobs are stored for this session yet.")

st.subheader("Rankings")
if memory["rankings"]:
    st.dataframe(
        [
            {
                "Rank": rank["rank"],
                "Role": rank["title"],
                "Company": rank["company"],
                "Score": rank["score"],
                "Fit": rank["fit"],
                "Source": rank["source"],
            }
            for rank in memory["rankings"]
        ],
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No rankings are stored for this session yet.")

st.subheader("Evidence")
if memory["evidence"]:
    st.dataframe(
        [
            {
                "Kind": item["kind"],
                "Role": item.get("job_title") or "",
                "Text": item["text"],
            }
            for item in memory["evidence"]
        ],
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No evidence is stored for this session yet.")

st.subheader("Chat history")
for message in memory["messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

prompt = st.chat_input("Ask about this scan", submit_mode="disable")
if prompt:
    guard = check_text(prompt, "message")
    if not guard.allowed:
        st.error(guard.plain_message)
    else:
        add_message(st.session_state.memory_id, "user", prompt)
        reply = answer_from_memory(load_memory(st.session_state.memory_id), prompt)
        add_message(st.session_state.memory_id, "assistant", reply)
        st.rerun()
