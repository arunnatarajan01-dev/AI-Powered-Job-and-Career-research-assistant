"""Fill the CAAE02 capstone template with this project's content."""

from copy import deepcopy

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

TEMPLATE = r"C:\Users\Lenovo\Downloads\CAAE02_Certified Agentic AI Engineer_Capstone Project_Final Submission_Your Name.pptx"
OUTPUTS = [
    r"C:\WorkFolder\AI Powered Job and Career research assistant\docs\CAAE02_AI_Career_and_Research_Assistant.pptx",
    r"C:\Users\Lenovo\Downloads\CAAE02_AI_Career_and_Research_Assistant.pptx",
]
JOBS_PNG = r"C:\Users\Lenovo\AppData\Local\Temp\cursor\screenshots\capstone-jobs.png"
OBSERVE_PNG = r"C:\Users\Lenovo\AppData\Local\Temp\cursor\screenshots\capstone-observability.png"

INK = RGBColor(0x1C, 0x24, 0x33)
MUTED = RGBColor(0x3D, 0x4A, 0x5C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x1F, 0x7A, 0x4D)
GREEN_SOFT = RGBColor(0xE5, 0xF4, 0xEC)
GREY = RGBColor(0xE8, 0xED, 0xF2)
GREY_INK = RGBColor(0x5C, 0x67, 0x70)


def set_text(shape, text, size=None, bold=None, color=None, align=None):
    frame = shape.text_frame
    frame.word_wrap = True
    lines = text.split("\n") if text else [""]
    paragraphs = list(frame.paragraphs)
    while len(paragraphs) < len(lines):
        paragraphs.append(frame.add_paragraph())
    for index, line in enumerate(lines):
        paragraph = paragraphs[index]
        if align is not None:
            paragraph.alignment = align
        if paragraph.runs:
            paragraph.runs[0].text = line
            for extra in paragraph.runs[1:]:
                extra.text = ""
            run = paragraph.runs[0]
        else:
            run = paragraph.add_run()
            run.text = line
            run.font.name = "Calibri"
        if size is not None:
            run.font.size = Pt(size)
        if bold is not None:
            run.font.bold = bold
        if color is not None:
            run.font.color.rgb = color
    for extra in paragraphs[len(lines):]:
        parent = extra._p.getparent()
        if parent is not None:
            parent.remove(extra._p)


def find(slide, name):
    for shape in slide.shapes:
        if shape.name == name:
            return shape
    raise KeyError(name)


def add_bullets(slide, lines, left, top, width, height, size=16):
    box = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    frame = box.text_frame
    frame.word_wrap = True
    frame.auto_size = None
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = PP_ALIGN.LEFT
        paragraph.space_after = Pt(8)
        run = paragraph.add_run()
        run.text = line
        run.font.name = "Calibri"
        run.font.size = Pt(size)
        run.font.color.rgb = INK
        run.font.bold = line.endswith(":") or line.startswith("Green") or line.startswith("Grey")
    return box


def paint(shape, fill):
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill


def add_titled_slide(prs, title, subtitle, lines, size=16):
    layout = next(item for item in prs.slide_layouts if item.name == "Title Only")
    slide = prs.slides.add_slide(layout)
    slide.shapes.title.text = title
    title_shape = slide.shapes.title
    if title_shape.text_frame.paragraphs[0].runs:
        run = title_shape.text_frame.paragraphs[0].runs[0]
        run.font.name = "Roboto Slab"
        run.font.size = Pt(28)
        run.font.color.rgb = INK
    box = slide.shapes.add_textbox(Emu(402336), Emu(980000), Emu(10800000), Emu(380000))
    set_text(box, subtitle, size=18, bold=True, color=INK)
    add_bullets(slide, lines, 402336, 1450000, 11200000, 4300000, size=size)
    return slide


def main():
    prs = Presentation(TEMPLATE)

    title = prs.slides[0]
    title_box = find(title, "Text 28")
    title_box.height = Emu(700000)
    set_text(
        title_box,
        "Project Title:  RAG-based Unified Career and Research Assistant for Resume–Job Matching and Uploaded-Paper Queries",
        size=14,
    )
    participant = find(title, "Text 29")
    participant.top = Emu(4480000)
    set_text(participant, "Participant(s): arunnatarajan01-dev")
    organisation = find(title, "Text 30")
    organisation.top = Emu(4980000)
    set_text(organisation, "Organisation: REVA University")
    submitted = find(title, "Text 32")
    submitted.top = Emu(5480000)
    set_text(submitted, "Submission Date:  1 October 2026")

    problem = prs.slides[2]
    set_text(find(problem, "TextBox 1"), "Why career screening, job search, and research sit in too many places", size=18, bold=True, color=INK)
    set_text(find(problem, "TextBox 2"), "")
    add_bullets(
        problem,
        [
            "A resume is read by hand for ATS fit, missing skills, and a learning plan.",
            "LinkedIn and Naukri are searched as two separate tasks, then copied into a sheet.",
            "A question about a paper, and an IEEE-style draft, sit outside that career flow.",
            "Approve, reject, and edit are not mailed to both the requester and the approver.",
            "A blocked prompt, and the steps behind a result, are hard to show to a reviewer.",
        ],
        460000,
        1750000,
        11000000,
        3400000,
        size=18,
    )

    objectives = prs.slides[3]
    set_text(find(objectives, "TextBox 6"), "Four outcomes this build delivers", size=18, bold=True, color=INK)
    set_text(find(objectives, "TextBox 1"), "")
    set_text(
        find(objectives, "TextBox 3"),
        "\n".join(
            [
                "Score a resume and return skills, role matches, gaps, a roadmap, and interview practice.",
                "Search LinkedIn and Naukri by city and posting date, and download that table as Excel.",
                "Answer from an uploaded paper, and draft an IEEE paper from a public repository for review.",
                "Keep approve, reject, and edit with a named person, email both parties, and log every step.",
            ]
        ),
        size=18,
        color=INK,
    )

    current = prs.slides[4]
    set_text(find(current, "TextBox 6"), "Same work, with the checks and the record added", size=18, bold=True, color=INK)
    set_text(find(current, "TextBox 5"), "")
    add_bullets(
        current,
        [
            "Current process",
            "Resume fit, gaps, and a study plan are assembled by hand.",
            "Two job sites are searched, then pasted into a spreadsheet.",
            "Paper questions and a first draft are a separate task.",
            "Review notes do not automatically reach both parties.",
        ],
        420000,
        1650000,
        5400000,
        3700000,
        size=16,
    )
    add_bullets(
        current,
        [
            "This build",
            "One dashboard returns the score, matches, gaps, roadmap, and practice.",
            "One search filters by city and date, then downloads job-search.xlsx.",
            "Chat uses retrieved passages. The IEEE draft is reviewed before PDF download.",
            "A named role decides. Both parties are emailed. The trace is kept.",
        ],
        6100000,
        1650000,
        5600000,
        3700000,
        size=16,
    )

    architecture = prs.slides[5]
    set_text(find(architecture, "TextBox 6"), "Career analysis, job search, and research draft", size=16, bold=True, color=INK)
    set_text(find(architecture, "TextBox 5"), "Every request uses the same six middleware steps: bind the user, trim the text, check input, open a trace, run the handler, check the output.", size=12, color=MUTED)
    set_text(find(architecture, "Text 7"), "Career and Research Assistant", size=14, bold=True, color=INK)
    set_text(find(architecture, "Text 12"), "Resume upload, job search, paper question, or a repository link.", size=10, color=INK)
    set_text(find(architecture, "Text 18"), "PDF or DOCX, city and date, paper text, and a public repository URL.", size=10, color=INK)
    set_text(find(architecture, "Text 24"), "The orchestrator sends career, research, or draft. The order is fixed.", size=10, color=INK)
    set_text(find(architecture, "Text 30"), "ATS tools, search_jobs, retrieve_passages, and the Gemini writer.", size=10, color=INK)
    set_text(find(architecture, "Text 36"), "Guardrail, human review, email, trace, and 13 local checks.", size=10, color=INK)

    workflow = prs.slides[6]
    set_text(find(workflow, "TextBox 5"), "Green chips are in this build. Grey chips are not. Also included: guardrails, grounded answers, IEEE JSON, and model routing.", size=12, color=MUTED)
    set_text(find(workflow, "Text 11"), "Signed-in user, resume, city and date, uploaded paper, or a repository link.", size=11, color=INK)
    set_text(find(workflow, "Text 16"), "Orchestrator delegates. Research retrieves, then writes. Career calls job search. The order is fixed.", size=11, color=INK)
    set_text(find(workflow, "Text 21"), "Search jobs, retrieve passages, and read the repository. Scores and the roadmap stay in Python.", size=11, color=INK)
    set_text(find(workflow, "Text 26"), "Output is checked. A person approves, rejects, or edits. Both parties are emailed.", size=11, color=INK)
    set_text(find(workflow, "Text 31"), "Techniques", size=12, bold=True, color=INK)

    included = {
        "Text 35": "Shape 34",
        "Text 37": "Shape 36",
        "Text 39": "Shape 38",
        "Text 45": "Shape 44",
    }
    excluded = {
        "Text 33": "Shape 32",
        "Text 41": "Shape 40",
        "Text 43": "Shape 42",
        "Text 47": "Shape 46",
    }
    for text_name, shape_name in included.items():
        paint(find(workflow, shape_name), GREEN)
        set_text(find(workflow, text_name), find(workflow, text_name).text_frame.text, size=8, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    for text_name, shape_name in excluded.items():
        paint(find(workflow, shape_name), GREY)
        set_text(find(workflow, text_name), find(workflow, text_name).text_frame.text, size=8, bold=False, color=GREY_INK, align=PP_ALIGN.CENTER)

    demo = prs.slides[7]
    set_text(find(demo, "TextBox 6"), "Walk-through on http://localhost:5000", size=18, bold=True, color=INK)
    set_text(find(demo, "TextBox 5"), "")
    add_bullets(
        demo,
        [
            "1. Sign in as the candidate, then open Jobs or upload a resume.",
            "2. Download job-search.xlsx, or resume-analysis.xlsx after a score.",
            "3. Ask a paper question, or build an IEEE draft and review it before PDF download.",
            "4. As hiring manager or auditor, approve, reject, or edit. Open Observability for the 13 checks.",
        ],
        402336,
        1450000,
        11400000,
        1400000,
        size=15,
    )
    demo.shapes.add_picture(JOBS_PNG, Emu(402336), Emu(3000000), width=Emu(5200000))
    demo.shapes.add_picture(OBSERVE_PNG, Emu(5900000), Emu(3000000), width=Emu(5200000))

    testing = prs.slides[8]
    set_text(find(testing, "TextBox 6"), "Local checks. No invented time or cost savings.", size=16, bold=True, color=INK)
    set_text(find(testing, "TextBox 5"), "Latest local run: 13 passed, 0 failed. The suite does not call Gemini or a live job provider.", size=12, color=MUTED)
    replacements = {
        "Text 9": "Check",
        "Text 11": "Risk if skipped",
        "Text 13": "This build",
        "Text 15": "Result",
        "Text 17": "Unsafe prompt",
        "Text 19": "Could reach Gemini",
        "Text 21": "Stopped first",
        "Text 23": "Blocked and logged",
        "Text 25": "Incomplete review",
        "Text 27": "Blank advance",
        "Text 29": "Form rejected",
        "Text 31": "Reason required",
        "Text 33": "Jobs posted today",
        "Text 35": "Today can be missed",
        "Text 37": "Today stays in",
        "Text 39": "Date filter holds",
        "Text 41": "Grounded answer",
        "Text 43": "Unrelated text",
        "Text 45": "Top passage only",
        "Text 47": "RAG check passed",
        "Text 49": "Evaluation suite",
        "Text 51": "Checks were separate",
        "Text 53": "13 local checks",
        "Text 55": "13 passed, 0 failed",
    }
    for name, value in replacements.items():
        set_text(find(testing, name), value, size=11, bold=name in {"Text 9", "Text 11", "Text 13", "Text 15"}, color=INK, align=PP_ALIGN.CENTER)

    analysis = prs.slides[9]
    set_text(find(analysis, "TextBox 6"), "What a user receives from one pass", size=18, bold=True, color=INK)
    set_text(find(analysis, "TextBox 5"), "")
    add_bullets(
        analysis,
        [
            "A resume upload returns an ATS score, skills, role matches, missing skills, a roadmap, and interview practice.",
            "Job search returns a LinkedIn and Naukri table for one city and date window. The file is job-search.xlsx.",
            "The dashboard downloads as resume-analysis.xlsx: summary, recommendations, skill gaps, and roadmap.",
            "A paper question is answered from retrieved passages. A repository link becomes an IEEE-style draft.",
            "The user reviews that draft before the PDF download. Unsafe prompts are blocked and recorded.",
            "A review stores the requester, the approver, and whether the mail was sent or only logged.",
        ],
        402336,
        1550000,
        11200000,
        3900000,
        size=16,
    )

    conclusions = prs.slides[10]
    set_text(find(conclusions, "TextBox 4"), "Governance, limits, and the support this demo still needs", size=16, bold=True, color=INK)
    set_text(find(conclusions, "TextBox 2"), "")
    add_bullets(
        conclusions,
        [
            "Governance. Gemini runs only after the input check. Output is checked for secrets. Approve, reject, and edit stay with a named role, and both parties are emailed.",
            "Limits. The step order is fixed. Chat keeps only the current question. Results live in the session. Review mail is logged until SMTP settings are filled.",
            "Support needed. A Gemini key, an Apify token for live job search, SMTP settings, an administrator address, and a short demo slot with one resume and one paper or repository.",
            "Next step. Run the walk-through on this machine, or on a shared host with the existing Docker setup, and replace the participant name on the title slide if the submission needs a legal name.",
        ],
        400000,
        1550000,
        11200000,
        3900000,
        size=16,
    )

    annex = prs.slides[11]
    set_text(find(annex, "TextBox 4"), "Stack, data, and where the code lives", size=16, bold=True, color=INK)
    set_text(find(annex, "TextBox 2"), "")
    add_bullets(
        annex,
        [
            "Framework. Flask, Jinja, HTML, CSS, and JavaScript. Entry point: unified_app.py.",
            "Model and agents. Gemini, flash then pro. Orchestrator, research, retriever, writer, and career.",
            "Tools. retrieve_passages, search_jobs, read_repository_request. Optional embeddings: all-MiniLM-L6-v2.",
            "Data. data/skills_db.csv, data/jobs.csv, interview and coding question files, data/job_feeds/linkedin.json and naukri.json.",
            "Records. logs/traces.jsonl, the review mail log, and evaluations/suite.py (13 checks).",
            "Run. python unified_app.py, then open http://localhost:5000.",
        ],
        400000,
        1500000,
        11200000,
        4000000,
        size=16,
    )

    add_titled_slide(
        prs,
        "Data, Tools, and Technology Stack",
        "What the application uses, and what it does not invent",
        [
            "Framework. One Flask application. Pages are Jinja templates with HTML, CSS, and JavaScript.",
            "Model. Gemini is used for a grounded paper answer and for the IEEE draft. Routing tries a flash model, then a pro model.",
            "Agents. An orchestrator hands work to research, retriever, writer, or career.",
            "Tools. retrieve_passages, search_jobs, and read_repository_request. Resume scoring and the roadmap are Python tools.",
            "Data. A skills list, a role catalog, interview and coding questions, and local LinkedIn and Naukri catalogs.",
            "Configuration. Gemini, Apify, and SMTP are read from .env. Traces are appended to logs/traces.jsonl.",
        ],
        size=16,
    )
    add_titled_slide(
        prs,
        "Business Impact",
        "Value for a candidate, a reviewer, and an author",
        [
            "A candidate gets an ATS score, matched roles, missing skills, and a learning plan in one pass.",
            "A reviewer keeps the decision: advance, reject, or correct, and both parties are told by email.",
            "LinkedIn and Naukri results for one city and date window come back as a table that can be shared as Excel.",
            "An author can question a paper from its own text and take a first IEEE-style draft into review.",
            "Unsafe prompts are stopped and recorded, and every step is logged so the result can be explained.",
            "The time saved is in screening, search, and the first draft. The final decision stays with the person.",
        ],
        size=16,
    )

    listing = prs.slides._sldIdLst
    items = list(listing)
    # 0-12 original, 13 stack, 14 business impact
    order = [0, 1, 2, 3, 4, 5, 6, 13, 7, 8, 9, 14, 10, 11, 12]
    for element in items:
        listing.remove(element)
    for index in order:
        listing.append(items[index])

    for path in OUTPUTS:
        prs.save(path)
        print(path)


if __name__ == "__main__":
    main()
