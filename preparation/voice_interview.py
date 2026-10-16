"""Practice screening interview: questions from candidate_answers.xlsx, coaching from Groq."""

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from dotenv import load_dotenv

XLSX_PATH = Path(__file__).resolve().parents[1] / "candidate_answers.xlsx"
MODEL_NAME = "openai/gpt-oss-20b"

TOPICS = (
    "Self Introduction",
    "Generative AI",
    "Python",
)

_SHEETS = {
    "Self Introduction": "SelfIntroduction",
    "Generative AI": "GenerativeAI",
    "Python": "Python",
}
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

_INTERVIEWER = """
You are a professional AI interviewer named Natalie.
Conduct a screening interview.
Candidate level is Fresher.
Ask only one question at a time. The app already shows the next question, so you do not ask one.
Be professional and encouraging.
Do not reveal the answer, and do not write an answer the candidate could read aloud.
""".strip()


def load_catalog():
    """Questions for each sidebar topic. Sample answers stay in the workbook."""
    catalog = {topic: [] for topic in TOPICS}
    if not XLSX_PATH.exists():
        return catalog
    with ZipFile(XLSX_PATH) as workbook:
        shared = _shared_strings(workbook)
        sheets = _sheet_paths(workbook)
        for topic, sheet_name in _SHEETS.items():
            path = sheets.get(_sheet_key(sheet_name))
            if path:
                catalog[topic] = _column_a(workbook, path, shared)
    return catalog


def questions_for(topic):
    return list(load_catalog().get(topic) or [])


def _sheet_key(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").casefold())


def _shared_strings(workbook):
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.iter(_NS + "t"))
        for item in root.findall(_NS + "si")
    ]


def _sheet_paths(workbook):
    root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    relation = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    package = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    targets = {
        node.attrib.get("Id"): node.attrib.get("Target")
        for node in rels.findall(package + "Relationship")
    }
    paths = {}
    for sheet in root.findall(_NS + "sheets/" + _NS + "sheet"):
        target = targets.get(sheet.attrib.get(relation + "id")) or ""
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        paths[_sheet_key(sheet.attrib.get("name"))] = target
    return paths


def _column_a(workbook, path, shared):
    root = ET.fromstring(workbook.read(path))
    questions = []
    for cell in root.iter(_NS + "c"):
        ref = cell.attrib.get("r") or ""
        if not ref.startswith("A") or ref == "A1":
            continue
        value = cell.find(_NS + "v")
        if value is None or value.text is None:
            continue
        if cell.attrib.get("t") == "s":
            text = shared[int(value.text)]
        else:
            text = value.text
        text = " ".join(text.split())
        if text and text.casefold() != "question":
            questions.append(text)
    return questions


def reply_to_answer(topic, question, answer):
    """One short coaching line after the candidate speaks. Does not supply an answer."""
    user = (
        f"Topic: {topic}\n"
        f"Question you asked: {question}\n"
        f"What the candidate said:\n{answer}\n\n"
        "Reply in one or two sentences. Comment only on clarity and whether they addressed the question. "
        "Do not give the answer."
    )
    return _complete(_INTERVIEWER, user, max_tokens=180)


def feedback_for(topic, turns):
    """End-of-practice score and coaching. Does not script a replacement answer."""
    lines = []
    for index, turn in enumerate(turns, start=1):
        lines.append(f"Question {index}: {turn['question']}\nCandidate: {turn['answer']}")
    user = (
        f"Topic: {topic}\n\n"
        + "\n\n".join(lines)
        + "\n\nReturn JSON with keys score (number from 0 to 5), feedback, and improvement. "
        "feedback is what they did well. improvement is how to be clearer next time. "
        "Do not write a model answer."
    )
    text = _complete(_INTERVIEWER, user, max_tokens=500)
    return _parse_feedback(text)


def _complete(system, user, max_tokens):
    load_dotenv()
    key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to .env and restart the app.")
    from groq import Groq

    client = Groq(api_key=key)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        max_tokens=max_tokens,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("The interview model returned an empty reply.")
    return text


def _parse_feedback(text):
    payload = _json_object(text)
    try:
        score = float(payload.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0.0, min(5.0, score))
    feedback = str(payload.get("feedback") or "").strip() or text
    improvement = str(payload.get("improvement") or "").strip()
    return {"score": round(score, 1), "feedback": feedback, "improvement": improvement}


def _json_object(text):
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    try:
        data = json.loads(fenced)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", fenced, flags=re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}
