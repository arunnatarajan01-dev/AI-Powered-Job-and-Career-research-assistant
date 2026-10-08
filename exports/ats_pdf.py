"""ATS-friendly resume PDF built from the reviewed case, including field edits."""

import io
import re

from hitl import _education_text


def compose_resume_text(result, case):
    """Resume text with the candidate name on the first line and review edits applied."""
    name = (case.get("candidate_name") or "Candidate").strip() or "Candidate"
    raw = ((result or {}).get("resume_text") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return _structured_resume(case, name)

    lines = [line for line in raw.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        lines = [name]
    else:
        lines[0] = name
    text = "\n".join(lines)
    pending = []

    contact = (result or {}).get("contact") or {}
    text, placed = _replace_once(text, contact.get("email"), case.get("email"))
    if not placed and _changed(contact.get("email"), case.get("email")):
        pending.append(f"Email: {case.get('email').strip()}")
    text, placed = _replace_once(text, contact.get("phone"), case.get("phone"))
    if not placed and _changed(contact.get("phone"), case.get("phone")):
        pending.append(f"Phone: {case.get('phone').strip()}")

    original_skills = ", ".join((result or {}).get("skill_names") or [])
    sections = (result or {}).get("sections") or {}
    new_skills = (case.get("skills") or "").strip()
    if _changed(original_skills, new_skills):
        text, placed = _replace_once(text, original_skills, new_skills)
        if not placed:
            text, placed = _replace_once(text, sections.get("skills"), new_skills)
        if not placed:
            pending.append(f"Skills: {new_skills}")

    original_edu = _education_text((result or {}).get("education"))
    new_edu = (case.get("education") or "").strip()
    if _changed(original_edu, new_edu):
        text, placed = _replace_once(text, sections.get("education"), new_edu)
        if not placed:
            text, placed = _replace_once(text, original_edu, new_edu)
        if not placed:
            pending.append(f"Education: {new_edu}")

    original_years = str((result or {}).get("experience_years", "")).strip()
    new_years = str(case.get("experience_years") or "").strip()
    if original_years and new_years and original_years != new_years:
        placed = False
        for phrase in (f"{original_years} years", f"{original_years}+ years", f"{original_years} yrs"):
            if phrase in text:
                text = text.replace(phrase, phrase.replace(original_years, new_years, 1), 1)
                placed = True
                break
        if not placed:
            pending.append(f"Years of experience: {new_years}")

    original_excerpt = ((result or {}).get("experience_excerpt") or "").strip()
    new_excerpt = (case.get("section_text") or "").strip()
    if _changed(original_excerpt, new_excerpt):
        text, placed = _replace_once(text, original_excerpt, new_excerpt)
        if not placed:
            text, placed = _replace_once(text, sections.get("experience"), new_excerpt)
        if not placed:
            pending.append(f"Experience: {new_excerpt}")

    if pending:
        head, _, tail = text.partition("\n")
        insert = "\n".join(pending)
        text = head + "\n\n" + insert + ("\n" + tail if tail else "")
    return text


def build_ats_pdf(result, case):
    """Return a PDF whose first line is the candidate name."""
    return _pdf_bytes(compose_resume_text(result, case))


def pdf_download_name(candidate_name):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", candidate_name or "resume").strip("-") or "resume"
    return f"{slug}-ats-resume.pdf"


def _changed(old, new):
    old_text = (old or "").strip()
    new_text = (new or "").strip()
    if not new_text or new_text in {"Not extracted", "—", "-"}:
        return False
    return new_text != old_text


def _replace_once(text, old, new):
    old_text = (old or "").strip()
    new_text = (new or "").strip()
    if old_text and new_text and old_text != new_text and old_text in text:
        return text.replace(old_text, new_text, 1), True
    return text, False


def _structured_resume(case, name):
    blocks = [
        name,
        "",
        f"Email: {case.get('email') or ''}",
        f"Phone: {case.get('phone') or ''}",
        "",
        "Skills",
        case.get("skills") or "",
        "",
        "Experience",
        f"{case.get('experience_years') or ''} years",
        case.get("section_text") or "",
        "",
        "Education",
        case.get("education") or "",
        "",
        "Target role",
        case.get("top_title") or "",
    ]
    return "\n".join(blocks).strip() + "\n"


def _pdf_escape(text):
    safe = text.encode("latin-1", "replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_lines(text, width=88):
    lines = []
    for paragraph in (text or "").splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for word in paragraph.split():
            piece = word if not current else f"{current} {word}"
            if len(piece) <= width:
                current = piece
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines or [""]


def _pdf_bytes(text):
    lines = _wrap_lines(text)
    page_lines = 46
    pages = [lines[i:i + page_lines] for i in range(0, len(lines), page_lines)] or [[""]]
    objects = {}
    next_id = 4
    page_ids = []
    for index, chunk in enumerate(pages):
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        page_ids.append(page_id)
        commands = ["BT"]
        cursor = chunk
        if index == 0 and cursor:
            commands.extend([
                "/F1 18 Tf",
                "72 750 Td",
                f"({_pdf_escape(cursor[0])}) Tj",
                "/F1 11 Tf",
                "0 -28 Td",
                "14 TL",
            ])
            cursor = cursor[1:]
        else:
            commands.extend(["/F1 11 Tf", "72 750 Td", "14 TL"])
        if cursor:
            commands.append(f"({_pdf_escape(cursor[0])}) Tj")
            for line in cursor[1:]:
                commands.append("T*")
                commands.append(f"({_pdf_escape(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        objects[content_id] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        ).encode("ascii")

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode("ascii")
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = {}
    for obj_id in sorted(objects):
        offsets[obj_id] = buffer.tell()
        buffer.write(f"{obj_id} 0 obj\n".encode("ascii"))
        buffer.write(objects[obj_id])
        buffer.write(b"\nendobj\n")
    xref = buffer.tell()
    size = max(objects) + 1
    buffer.write(f"xref\n0 {size}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for obj_id in range(1, size):
        buffer.write(f"{offsets[obj_id]:010d} 00000 n \n".encode("ascii"))
    buffer.write(
        f"trailer << /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    buffer.seek(0)
    return buffer
