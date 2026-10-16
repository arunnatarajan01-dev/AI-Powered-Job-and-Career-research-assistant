import streamlit as st

st.header("AI Powered Job and Career research assistant")
st.caption("Streamlit view of the same resume, job, and research tools as the Flask app.")

with st.container(horizontal=True):
    st.metric("Resume", "ATS and roles", border=True)
    st.metric("Jobs", "Naukri and LinkedIn", border=True)
    st.metric("Research", "Chat and IEEE draft", border=True)

st.subheader("Career")
st.markdown(
    "Upload a PDF or DOCX resume to score it, match catalog roles, and build a skill roadmap. "
    "Job search uses the top matched role when you have already analyzed a resume."
)

st.subheader("Research")
st.markdown(
    "Upload a paper and ask questions from that text, or draft an IEEE-style paper from a public GitHub URL. "
    "Both calls use Gemini and the same safety checks as the Flask research page."
)
