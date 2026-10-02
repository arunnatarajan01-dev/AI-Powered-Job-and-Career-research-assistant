"""Gemini function calling for the retrieve_passages tool."""

import google.generativeai as genai

from agents.orchestrator import RESEARCH_ROUTE
from agents.tools import TOOL_SCHEMAS, execute_tool


def _model_names():
    models_info = list(genai.list_models())
    candidates = []
    for model in models_info:
        methods = [str(item).lower() for item in (getattr(model, "supported_generation_methods", None) or [])]
        if "generatecontent" in methods or "generate_content" in methods:
            candidates.append(model.name)
    preferred = [name for name in candidates if "flash" in name.lower()]
    preferred += [name for name in candidates if "pro" in name.lower() and name not in preferred]
    preferred += [name for name in candidates if name not in preferred]
    if not preferred:
        raise RuntimeError("No Gemini model supports generateContent.")
    return preferred


def _function_calls(response):
    calls = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            call = getattr(part, "function_call", None)
            if not call or not getattr(call, "name", None):
                continue
            raw = getattr(call, "args", None)
            try:
                arguments = dict(raw) if raw else {}
            except (TypeError, ValueError):
                arguments = {}
            calls.append((call.name, arguments))
    return calls


def _text(response):
    text = getattr(response, "text", None)
    if text:
        return text
    parts = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            value = getattr(part, "text", None)
            if value:
                parts.append(value)
    return "\n".join(parts).strip()


def answer_with_retrieve_tool(question, document, trace=None):
    """Ask Gemini to call retrieve_passages, run that tool, then write from the passages."""
    declaration = next(tool for tool in TOOL_SCHEMAS if tool["name"] == "retrieve_passages")
    context = {"document": document, "question": question}
    tools_used = []
    last_error = None
    for model_name in _model_names():
        try:
            model = genai.GenerativeModel(model_name, tools=[declaration])
            chat = model.start_chat()
            response = chat.send_message(
                "Call retrieve_passages before you answer. "
                "Then answer only from the passages that tool returns. "
                f"Question: {question}"
            )
            calls = _function_calls(response)
            if not calls:
                calls = [("retrieve_passages", {"query": question})]
            passages = []
            for name, arguments in calls:
                if trace is not None:
                    with trace.span("tool_call", tool=name, source="model"):
                        result = execute_tool(name, arguments, context)
                else:
                    result = execute_tool(name, arguments, context)
                tools_used.append(name)
                passages.extend(result.get("passages") or [])
            follow = chat.send_message(
                "Retrieved passages:\n"
                + "\n\n".join(passages)
                + "\n\nAnswer the question from these passages only. "
                + "If they do not contain the answer, say so."
            )
            answer = _text(follow) or _text(response)
            if not answer:
                raise RuntimeError("Gemini returned an empty answer.")
            return {
                "answer": answer,
                "passages": passages,
                "tools": tools_used or ["retrieve_passages"],
                "agents": list(RESEARCH_ROUTE),
            }
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError(str(last_error) if last_error else "Tool calling failed.")
