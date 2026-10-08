"""Build text-based sample research PDFs for the research assistant."""
from pathlib import Path

PAGE_W, PAGE_H = 612, 792
MARGIN_X = 54
MARGIN_TOP = 64
MARGIN_BOTTOM = 54
MAX_W = PAGE_W - 2 * MARGIN_X


def esc(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def wrap(text: str, size: float, width: float) -> list[str]:
    # Approximate Helvetica advance so lines stay inside the page.
    limit = max(20, int(width / (size * 0.50)))
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if len(trial) <= limit:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def layout(blocks: list[tuple[str, str]]) -> list[list[tuple[str, float, str, float]]]:
    """Return pages of (font, size, text, y) items."""
    styles = {
        "title": ("F2", 16, 22),
        "meta": ("F1", 10, 14),
        "h": ("F2", 12, 18),
        "body": ("F1", 11, 15),
    }
    pages: list[list[tuple[str, float, str, float]]] = []
    items: list[tuple[str, float, str, float]] = []
    y = PAGE_H - MARGIN_TOP

    def new_page():
        nonlocal items, y
        if items:
            pages.append(items)
        items = []
        y = PAGE_H - MARGIN_TOP

    for kind, text in blocks:
        font, size, leading = styles[kind]
        gap = 10 if kind in {"h", "title"} else 3
        if y - gap < MARGIN_BOTTOM + leading:
            new_page()
        y -= gap
        for line in wrap(text, size, MAX_W):
            if y - leading < MARGIN_BOTTOM:
                new_page()
            items.append((font, size, line, y))
            y -= leading
    if items:
        pages.append(items)
    return pages


def build_pdf(blocks: list[tuple[str, str]]) -> bytes:
    pages = layout(blocks)
    objects: list[bytes] = []

    def add(data: str) -> int:
        objects.append(data.encode("latin-1"))
        return len(objects)

    font_regular = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font_bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    page_ids = []
    for index, items in enumerate(pages, start=1):
        lines = ["BT"]
        for font, size, text, y in items:
            lines.append(f"/{font} {size:.1f} Tf")
            lines.append(f"1 0 0 1 {MARGIN_X} {y:.2f} Tm")
            lines.append(f"({esc(text)}) Tj")
        footer = f"Sample test paper  |  page {index} of {len(pages)}"
        lines.append("/F1 9 Tf")
        lines.append(f"1 0 0 1 {MARGIN_X} 32 Tm")
        lines.append(f"({esc(footer)}) Tj")
        lines.append("ET")
        stream = "\n".join(lines).encode("latin-1")
        content_id = add(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1").decode("latin-1")
            + stream.decode("latin-1")
            + "\nendstream"
        )
        page_id = add(
            "<< /Type /Page /Parent PAGES 0 R "
            f"/MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            "/Resources << /Font << "
            f"/F1 {font_regular} 0 R /F2 {font_bold} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    pages_id = add(f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>")
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    # Parent reference was a placeholder so page objects could be written first.
    fixed = []
    for obj in objects:
        fixed.append(obj.replace(b"/Parent PAGES 0 R", f"/Parent {pages_id} 0 R".encode("latin-1")))
    objects = fixed

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("latin-1"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref_at = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(out)


PAPERS = {
    "anchor_score_faithfulness.pdf": [
        ("title", "AnchorScore: Measuring Faithfulness in Document Question Answering"),
        ("meta", "Sofia Alvarez and Kenji Watanabe"),
        ("meta", "Harborview Research Lab, Lisbon and Kyoto"),
        ("meta", "Proceedings of the Workshop on Document Intelligence (WDI), 2025"),
        ("h", "Abstract"),
        ("body", "This paper introduces AnchorScore, a simple faithfulness metric for systems that answer questions from an uploaded document. We built a test set of 200 questions written over 12 computer-science papers. When the system was required to answer from retrieved passages, faithfulness was 91 percent. When the same questions were answered with no document context, faithfulness fell to 54 percent. A chunk size of 800 tokens gave the best recall. Cutting chunks to 200 tokens lowered recall by 11 percentage points. Thirty-eight graduate students rated answer helpfulness at a mean of 4.2 out of 5. We recommend reporting AnchorScore beside accuracy whenever a system answers from uploaded files."),
        ("h", "1. Introduction"),
        ("body", "Document assistants often sound confident even when the answer is not supported by the file the user uploaded. Accuracy against a gold label does not reveal that failure. AnchorScore checks whether each factual claim in an answer appears in the retrieved passages. A claim is anchored only when a human rater can point to a sentence in those passages that states the same fact. The score is the percentage of claims that are anchored."),
        ("body", "The study was run at Harborview Research Lab between March and June 2025. The only language in the corpus is English. The only domain is computer science. Those two limits are stated again in Section 5 so they are easy to find."),
        ("h", "2. Test collection"),
        ("body", "Twelve papers were chosen from an internal reading list. None of them is a famous benchmark paper, so memorized model knowledge is a weak substitute for the file. Two annotators wrote 200 questions. Each question has one short factual answer and a pointer to the supporting sentence. Disagreements were resolved by a third annotator. The question types are definition (40), numeric result (70), method detail (50), and limitation (40)."),
        ("body", "The numeric subset is the hardest slice. It includes counts, percentages, and named thresholds such as the 800-token chunk size. A system that rounds 91 percent to about 90 percent is marked unanchored on that claim."),
        ("h", "3. Method"),
        ("body", "Passages are embedded with all-MiniLM-L6-v2, which produces 384-dimensional vectors. The index is a FAISS flat L2 index. At question time the retriever returns the top 4 passages. The generator may use only those passages. Overlap between adjacent chunks is 150 characters when the chunk size is 1000 characters. That overlap setting is separate from the 800-token experiment in Section 4."),
        ("body", "AnchorScore is computed after generation. Raters split the answer into claims, then mark each claim anchored or unsupported. The metric ignores tone, grammar, and answer length. A correct fact that is not present in the retrieved passages still counts as unsupported, because the assistant was not allowed to leave the document."),
        ("h", "4. Experiments"),
        ("body", "Condition A used retrieval. Condition B used the same generator with an empty document. Condition A reached 91 percent faithfulness. Condition B reached 54 percent faithfulness. The 37-point gap is the main result of the paper. On the numeric subset alone, Condition A scored 88 percent and Condition B scored 41 percent."),
        ("body", "We also varied chunk size while holding the retriever fixed. Chunks of 200, 400, 800, and 1200 tokens were compared on recall of the supporting sentence. The 800-token setting was best. The 200-token setting reduced recall by 11 percentage points relative to 800 tokens. The 1200-token setting was 3 points below 800 because the extra context diluted the match."),
        ("body", "Helpfulness was rated by 38 graduate students on a 1-to-5 scale after they read the answer and the source passage. The mean rating was 4.2. The median rating was 4. No rater was an author of this paper."),
        ("h", "5. Limitations"),
        ("body", "The corpus is English only. The corpus is computer science only. AnchorScore needs human raters, so it is not an automatic training loss. The generator was not compared across model vendors. We did not test scanned image PDFs, because the loader expects selectable text."),
        ("h", "6. Conclusion"),
        ("body", "Retrieval raised faithfulness from 54 percent to 91 percent on 200 questions. The best chunk size in this study was 800 tokens. AnchorScore should be reported alongside accuracy whenever a system answers from uploaded documents."),
        ("h", "References"),
        ("body", "[1] Alvarez, S. and Watanabe, K. AnchorScore: Measuring Faithfulness in Document Question Answering. WDI 2025."),
    ],
    "careergraph_skill_gap.pdf": [
        ("title", "CareerGraph: Skill-Gap Detection for Early-Career Software Roles"),
        ("meta", "Priya Nair and Arjun Mehta"),
        ("meta", "Northbridge Institute of Applied Computing, Bengaluru"),
        ("meta", "Journal of Applied Career Computing, Vol. 7, 2024"),
        ("h", "Abstract"),
        ("body", "CareerGraph compares a resume with a job posting and lists skills that the posting asks for and the resume does not show. We evaluated it on 1,240 anonymized resumes and 860 job postings collected from January 2022 through December 2023. Top-5 job-match accuracy was 81.4 percent, against 63.2 percent for a keyword baseline. Skill-gap precision was 0.76 and skill-gap recall was 0.69. For data roles the most common missing skill was SQL. For frontend roles the most common missing skill was TypeScript. The false-positive rate on soft skills was 0.18, which is the main weakness of the tool."),
        ("h", "1. Introduction"),
        ("body", "Early-career applicants often apply to roles whose required skills are only partly visible on the resume. A matcher that returns a job title without naming the missing skills is hard to act on. CareerGraph returns both a ranked list of roles and a skill-gap list. This paper measures those two outputs separately. Match accuracy answers whether the role is relevant. Gap precision answers whether a listed missing skill is truly absent from the resume and truly required by the posting."),
        ("body", "All labeling was done in Bengaluru by four career coaches who were not the authors. The coaches worked from written guidelines. Each resume-posting pair was labeled by two coaches. A fifth coach broke ties."),
        ("h", "2. Data"),
        ("body", "The resume set contains 1,240 anonymized resumes. Names, phone numbers, and email addresses were removed before labeling. The posting set contains 860 job postings. The collection window is January 2022 through December 2023. Roles are limited to software engineering, data science, and product-adjacent technical jobs. Internships shorter than three months were kept, because they still list skills."),
        ("body", "We did not include design-only portfolios or executive biographies. Those documents lack the skill lines CareerGraph expects. A resume with no skills section is still scored. In that case the tool reads projects and experience lines."),
        ("h", "3. Method"),
        ("body", "CareerGraph extracts skill phrases with a dictionary, then embeds the remaining resume sentences and the job description. Similarity is cosine similarity over normalized vectors. The top 5 postings are returned as matches. A skill is reported as a gap only when it appears in the posting and no dictionary alias appears in the resume. Soft skills such as leadership and communication use the same rule, which is why their false-positive rate is higher."),
        ("body", "The keyword baseline counts overlapping skill names and ignores embeddings. It is the only baseline in this paper. We do not claim a comparison with large language models."),
        ("h", "4. Results"),
        ("body", "Top-5 job-match accuracy was 81.4 percent for CareerGraph and 63.2 percent for the keyword baseline. The absolute gain is 18.2 points. Top-1 accuracy was 64.0 percent for CareerGraph and 49.5 percent for the baseline. These match figures use the coach labels as ground truth."),
        ("body", "Skill-gap precision was 0.76. Skill-gap recall was 0.69. Precision is higher than recall because the tool stays silent when a skill mention is ambiguous. The most common missing skill among data roles was SQL. The most common missing skill among frontend roles was TypeScript. The most common missing skill among backend roles was Docker, but that third finding is secondary and was not part of the pre-registered hypotheses."),
        ("body", "The false-positive rate on soft skills was 0.18. The false-positive rate on technical skills was 0.07. Soft-skill errors usually came from a resume that demonstrated the skill in a bullet without using the dictionary phrase."),
        ("h", "5. Limitations"),
        ("body", "The study covers early-career software roles only. It does not measure interview performance or hiring outcomes. The dictionary is English only. Postings outside the 2022-2023 window were excluded. CareerGraph does not invent skills that are absent from both the resume and the posting."),
        ("h", "6. Conclusion"),
        ("body", "On 1,240 resumes and 860 postings, CareerGraph reached 81.4 percent top-5 match accuracy and 0.76 skill-gap precision. SQL was the most common gap for data roles, and TypeScript was the most common gap for frontend roles. The soft-skill false-positive rate of 0.18 remains the main weakness."),
        ("h", "References"),
        ("body", "[1] Nair, P. and Mehta, A. CareerGraph: Skill-Gap Detection for Early-Career Software Roles. Journal of Applied Career Computing, 7, 2024."),
    ],
}


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    for name, blocks in PAPERS.items():
        path = out_dir / name
        path.write_bytes(build_pdf(blocks))
        print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
