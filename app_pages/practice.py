import streamlit as st

from streamlit_logic import coding_question_rows, interview_question_rows, practice_companies

st.header("Practice")
st.caption("Company interview questions and coding problems from the local catalogs.")

catalogs = practice_companies()
kind = st.segmented_control("Set", ["Interview", "Coding"], default="Interview")

if kind == "Coding":
    companies = catalogs["coding"]
    company = st.selectbox("Company", ["All", *companies])
    topic = st.selectbox("Topic", ["All", *catalogs["topics"]])
    difficulty = st.segmented_control("Difficulty", ["All", "Easy", "Medium", "Hard"], default="All")
    rows = coding_question_rows(
        None if company == "All" else company,
        None if topic == "All" else topic,
        None if difficulty in (None, "All") else difficulty,
    )
    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        column_config={"link": st.column_config.LinkColumn("Link")},
    )
else:
    companies = catalogs["interview"]
    company = st.selectbox("Company", ["All", *companies])
    difficulty = st.segmented_control("Difficulty", ["All", "Easy", "Medium", "Hard"], default="All")
    rows = interview_question_rows(
        None if company == "All" else company,
        None,
        None if difficulty in (None, "All") else difficulty,
    )
    st.dataframe(rows, width="stretch", hide_index=True)

analysis = st.session_state.get("analysis") or {}
role_questions = analysis.get("interview_questions") or {}
if role_questions:
    role = role_questions.get("role") or "matched role"
    with st.expander(f"Questions for {role}"):
        for label, key in (
            ("Technical", "technical"),
            ("Behavioral", "behavioral"),
            ("System design", "system_design"),
            ("From your skills", "skill_specific"),
        ):
            items = role_questions.get(key) or []
            if items:
                st.markdown(f"**{label}**")
                for item in items:
                    st.write(f"- {item}")
