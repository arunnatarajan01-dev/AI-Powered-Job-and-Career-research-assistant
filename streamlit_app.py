import uuid

import streamlit as st

from memory.session_store import end_session
from models.bert_matcher import warm_matcher

warm_matcher()

st.set_page_config(
    page_title="AI Powered Job and Career research assistant",
    page_icon=":material/work:",
    layout="wide",
)

st.session_state.setdefault("memory_id", str(uuid.uuid4()))
st.session_state.setdefault("analysis", None)
st.session_state.setdefault("research_messages", [])
st.session_state.setdefault("document_text", "")
st.session_state.setdefault("document_signature", None)
st.session_state.setdefault("paper_draft", None)

page = st.navigation(
    {
        "Career": [
            st.Page("app_pages/home.py", title="Home", icon=":material/home:", default=True),
            st.Page("app_pages/resume.py", title="Resume", icon=":material/description:"),
            st.Page("app_pages/jobs.py", title="Jobs", icon=":material/work:"),
            st.Page("app_pages/practice.py", title="Practice", icon=":material/school:"),
        ],
        "Research": [
            st.Page("app_pages/research.py", title="Research", icon=":material/menu_book:"),
        ],
    },
    position="sidebar",
)

if st.sidebar.button("Log out", icon=":material/logout:"):
    end_session(st.session_state.get("memory_id"))
    st.session_state.clear()
    st.rerun()

page.run()
