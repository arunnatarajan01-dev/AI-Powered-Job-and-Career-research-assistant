import streamlit as st

from memory.session_store import remember_jobs
from jobs.discovery import PROVIDER_OPTIONS
from streamlit_logic import AnalysisError, city_names, job_rows, posted_options, search_jobs

st.header("Jobs")
st.caption("Search the job providers. Without an Apify token, each source uses its local catalog.")

analysis = st.session_state.get("analysis") or {}
suggested = ((analysis.get("recommendations") or [{}])[0]).get("title") or "software engineer"
resume_skills = analysis.get("skill_names") or []

with st.form("job_search"):
    keyword = st.text_input("Role", value=suggested)
    location = st.selectbox("City", city_names())
    posted_pairs = posted_options()
    posted_labels = [label for _key, label in posted_pairs]
    posted_label = st.segmented_control("Posted", posted_labels, default="Last week")
    source_labels = [label for _key, label in PROVIDER_OPTIONS]
    sources = st.pills(
        "Sources",
        source_labels,
        default=source_labels,
        selection_mode="multi",
    )
    experience = st.selectbox("Years of experience", ["Any", *[str(year) for year in range(1, 26)]])
    work_mode = st.segmented_control("Work mode", ["Any", "Remote", "Hybrid", "Onsite"], default="Any")
    submitted = st.form_submit_button("Search jobs", type="primary")

if submitted:
    label_to_key = {label: key for key, label in posted_pairs}
    label_to_provider = {label: key for key, label in PROVIDER_OPTIONS}
    provider_keys = [label_to_provider[source] for source in sources or [] if source in label_to_provider]
    with st.spinner("Searching job sources"):
        try:
            st.session_state.job_results = search_jobs(
                provider_keys,
                location,
                label_to_key.get(posted_label or "Last week", "week"),
                keyword,
                "" if experience == "Any" else experience,
                "" if not work_mode or work_mode == "Any" else work_mode.lower(),
                resume_skills,
            )
            remember_jobs(st.session_state.get("memory_id"), st.session_state.job_results)
        except AnalysisError as exc:
            st.session_state.job_results = None
            st.error(str(exc))
        except Exception as exc:
            st.session_state.job_results = None
            st.error(f"Job search failed: {exc}")

results = st.session_state.get("job_results")
if not results:
    if resume_skills:
        st.info(f"Skill match uses {len(resume_skills)} skills from the analyzed resume.")
    else:
        st.info("Analyze a resume first if you want a skill-match percent on each posting.")
    st.stop()

if resume_skills:
    st.caption(f"Skill match compares each posting with {len(resume_skills)} resume skills.")

for bundle in results:
    count = len(bundle.get("jobs") or [])
    st.subheader(f"{bundle.get('label') or bundle.get('provider')} · {count}")
    if bundle.get("message"):
        st.caption(bundle["message"])
    rows = job_rows(bundle)
    if rows:
        st.dataframe(
            rows,
            width="stretch",
            hide_index=True,
            column_config={"Link": st.column_config.LinkColumn("Link")},
        )
    else:
        st.info("No postings matched these filters.")
