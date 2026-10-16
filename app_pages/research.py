import streamlit as st

from streamlit_logic import AnalysisError, read_research_pdfs, research_answer, research_draft

st.header("Research")
view = st.segmented_control("View", ["Document chat", "Paper draft"], default="Document chat")

if view == "Paper draft":
    st.caption("Gemini returns an IEEE-style draft from a public GitHub repository.")
    with st.form("paper_form"):
        repo_url = st.text_input("Repository URL", placeholder="https://github.com/org/project")
        author = st.text_input("Author")
        institution = st.text_input("Institution")
        submitted = st.form_submit_button("Generate draft", type="primary")
    if submitted:
        with st.spinner("Drafting the paper"):
            try:
                st.session_state.paper_draft = research_draft(repo_url, author, institution)
            except AnalysisError as exc:
                st.session_state.paper_draft = None
                st.error(str(exc))
            except Exception as exc:
                st.session_state.paper_draft = None
                st.error(f"Draft failed: {exc}")

    draft = st.session_state.get("paper_draft")
    if isinstance(draft, dict):
        stats = draft.get("stats") if isinstance(draft.get("stats"), dict) else {}
        with st.container(horizontal=True):
            st.metric("Files", stats.get("files", "—"), border=True)
            st.metric("Complexity", stats.get("complexity", "—"), border=True)
            st.metric("Confidence", stats.get("confidence", "—"), border=True)
        st.subheader(draft.get("title") or "Draft")
        for key, label in (
            ("abstract", "Abstract"),
            ("introduction", "Introduction"),
            ("lit_review", "Literature review"),
            ("architecture", "Architecture"),
            ("implementation", "Implementation"),
            ("results", "Results"),
            ("conclusion", "Conclusion"),
        ):
            text = draft.get(key)
            if text:
                with st.expander(label, expanded=key == "abstract"):
                    st.write(text)
    elif draft is None and not submitted:
        st.info("Enter a public repository URL, an author, and an institution.")
else:
    st.caption("Answers use the uploaded PDFs. A new upload clears the chat.")
    uploaded = st.file_uploader("Research PDFs", type=["pdf"], accept_multiple_files=True)
    if uploaded:
        signature = tuple((item.name, item.size) for item in uploaded)
        if signature != st.session_state.document_signature:
            st.session_state.document_text = read_research_pdfs(
                [{"name": item.name, "data": item.getvalue()} for item in uploaded]
            )
            st.session_state.document_signature = signature
            st.session_state.research_messages = []
        st.caption(f"{len(st.session_state.document_text):,} characters ready for questions.")
    elif not st.session_state.document_text:
        st.info("Upload one or more PDFs, then ask a question about them.")

    for message in st.session_state.research_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input(
        "Ask about the uploaded papers",
        submit_mode="disable",
        disabled=not st.session_state.document_text,
    )
    if prompt:
        st.session_state.research_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Reading the matching passages"):
                try:
                    answer = research_answer(prompt, st.session_state.document_text)
                except Exception as exc:
                    answer = f"The research assistant failed: {exc}"
            st.markdown(answer)
        st.session_state.research_messages.append({"role": "assistant", "content": answer})
