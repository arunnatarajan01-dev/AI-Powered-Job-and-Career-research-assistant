"""Three-slide overview of the project folder."""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

OUT = r"C:\WorkFolder\AI Powered Job and Career research assistant\Project_Overview.pptx"

NAVY = RGBColor(0x12, 0x32, 0x4A)
TEAL = RGBColor(0x0F, 0x76, 0x6E)
INK = RGBColor(0x14, 0x32, 0x4A)
MUTED = RGBColor(0x4D, 0x65, 0x78)
PAPER = RGBColor(0xF4, 0xF7, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MIST = RGBColor(0xD7, 0xE4, 0xEE)
GREEN_BG = RGBColor(0xE7, 0xF6, 0xEE)
GREEN = RGBColor(0x14, 0x5C, 0x3A)
BLUE_BG = RGBColor(0xE7, 0xF1, 0xFF)
BLUE = RGBColor(0x1D, 0x4F, 0x91)
PURPLE_BG = RGBColor(0xF3, 0xEA, 0xFF)
PURPLE = RGBColor(0x5B, 0x2D, 0x86)
AMBER_BG = RGBColor(0xFF, 0xF1, 0xDF)
AMBER = RGBColor(0x8A, 0x4B, 0x12)
SOFT = RGBColor(0xE8, 0xF0, 0xF6)


def set_run_font(run, name, size, bold, color):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run._r.get_or_add_rPr().set(qn("a:latin"), name) if False else None
    rpr = run._r.get_or_add_rPr()
    latin = rpr.find(qn("a:latin"))
    if latin is None:
        latin = rpr.makeelement(qn("a:latin"), {})
        rpr.append(latin)
    latin.set("typeface", name)


def no_line(shape):
    shape.line.fill.background()


def box(slide, left, top, width, height, fill, rounded=False):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    no_line(shape)
    if rounded:
        shape.adjustments[0] = 0.08
    return shape


def write(slide, left, top, width, height, paragraphs, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT):
    """paragraphs: list of (text, size, bold, color) or (text, size, bold, color, space_after)."""
    shape = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = shape.text_frame
    frame.word_wrap = True
    frame.auto_size = None
    frame.margin_left = Emu(0)
    frame.margin_right = Emu(0)
    frame.margin_top = Emu(0)
    frame.margin_bottom = Emu(0)
    frame.paragraphs[0].alignment = align
    anchor_map = {
        MSO_ANCHOR.TOP: "t",
        MSO_ANCHOR.MIDDLE: "ctr",
        MSO_ANCHOR.BOTTOM: "b",
    }
    frame._txBody.bodyPr.set("anchor", anchor_map.get(anchor, "t"))
    for index, item in enumerate(paragraphs):
        text, size, bold, color = item[:4]
        space_after = item[4] if len(item) > 4 else 2
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = align
        paragraph.space_before = Pt(0)
        paragraph.space_after = Pt(space_after)
        run = paragraph.add_run()
        run.text = text
        set_run_font(run, "Calibri", size, bold, color)
    return shape


def background(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def header(slide, kicker, title, subtitle):
    box(slide, 0, 0, 13.333, 1.28, NAVY)
    box(slide, 0, 1.28, 13.333, 0.06, TEAL)
    write(slide, 0.42, 0.14, 10, 0.28, [(kicker, 12, True, RGBColor(0x9A, 0xD7, 0xC4), 0)])
    write(slide, 0.42, 0.38, 12.4, 0.46, [(title, 28, True, WHITE, 0)])
    write(slide, 0.42, 0.88, 12.4, 0.32, [(subtitle, 14, False, RGBColor(0xD7, 0xE4, 0xEE), 0)])


def footer(slide, page):
    write(
        slide,
        0.42,
        7.18,
        10.2,
        0.24,
        [("IntegrateAI  ·  unified_app.py  ·  Flask and Streamlit", 11, False, MUTED, 0)],
    )
    write(
        slide,
        11.2,
        7.18,
        1.7,
        0.24,
        [(page, 11, True, TEAL, 0)],
        align=PP_ALIGN.RIGHT,
    )


def build():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    slide_one(prs, blank)
    slide_two(prs, blank)
    slide_three(prs, blank)
    prs.save(OUT)
    return OUT


def slide_one(prs, blank):
    slide = prs.slides.add_slide(blank)
    background(slide, PAPER)
    header(
        slide,
        "PROJECT OVERVIEW",
        "AI-Powered Job and Career Research Assistant",
        "One site for resume analysis, job discovery, interview practice, and research papers.",
    )

    cards = [
        (
            GREEN_BG,
            GREEN,
            "Career tools",
            [
                "Upload a PDF or DOCX resume, up to 16 MB.",
                "Extract contact, education, experience, and skills.",
                "Score ATS completeness and give rewrite feedback.",
                "Match roles, skill gaps, a roadmap, and career paths.",
                "Company interview questions and coding practice.",
            ],
        ),
        (
            PURPLE_BG,
            PURPLE,
            "Research assistant",
            [
                "Constructor turns a public GitHub URL into an IEEE draft.",
                "Gemini returns the paper sections as structured JSON.",
                "The browser downloads the draft as a PDF.",
                "Deconstructor answers questions from uploaded PDFs.",
                "Guardrails check text before and after every model call.",
            ],
        ),
        (
            BLUE_BG,
            BLUE,
            "Around the hub",
            [
                "Job search across LinkedIn, Naukri, Indeed, and Foundit.",
                "Cover letters, application tracking, and spreadsheet export.",
                "Voice interview practice with spoken-answer feedback.",
                "Human review for candidate, manager, and auditor roles.",
                "Traces, safety alerts, and a local evaluation suite.",
            ],
        ),
    ]
    for index, (fill, accent, title, lines) in enumerate(cards):
        left = 0.38 + index * 4.28
        box(slide, left, 1.62, 4.08, 4.28, fill, rounded=True)
        box(slide, left, 1.62, 4.08, 0.1, accent)
        write(slide, left + 0.22, 1.86, 3.64, 0.4, [(title, 20, True, accent, 0)])
        write(
            slide,
            left + 0.22,
            2.38,
            3.64,
            3.25,
            [(line, 14, False, INK, 8) for line in lines],
        )

    box(slide, 0.38, 6.08, 12.56, 0.92, NAVY, rounded=True)
    write(
        slide,
        0.62,
        6.22,
        12.1,
        0.28,
        [("How it is delivered", 13, True, RGBColor(0x9A, 0xD7, 0xC4), 0)],
    )
    write(
        slide,
        0.62,
        6.48,
        12.1,
        0.38,
        [(
            "Flask at unified_app.py on port 5000, with the same career and research tools in Streamlit on port 8501. Gemini powers paper drafts and document chat. Resume scoring works without an API key.",
            13,
            False,
            WHITE,
            0,
        )],
    )
    footer(slide, "1  /  3")


def slide_two(prs, blank):
    slide = prs.slides.add_slide(blank)
    background(slide, PAPER)
    header(
        slide,
        "REPOSITORY MAP",
        "Folders and what each one owns",
        "The running application is the root modules. Two earlier projects sit beside it.",
    )

    columns = [
        (
            GREEN,
            GREEN_BG,
            "Application logic",
            [
                ("unified_app.py", "Flask routes, session, and APIs"),
                ("streamlit_app.py", "Same tools in a Streamlit UI"),
                ("parser/", "PDF, DOCX, sections, contact fields"),
                ("models/", "Skills, ATS score, BERT job match"),
                ("recommendation/", "Gaps, roadmap, career paths"),
                ("preparation/", "Interview, coding, voice practice"),
                ("jobs/", "Live feeds and local job catalogs"),
                ("agents/", "Orchestrator, tools, and RAG"),
            ],
        ),
        (
            BLUE,
            BLUE_BG,
            "Screens, safety, data",
            [
                ("templates/", "18 pages: hub, jobs, review, voice"),
                ("static/", "CSS and page scripts"),
                ("app_pages/", "Streamlit home, resume, research"),
                ("safety/", "Guardrails and admin alert mail"),
                ("memory/", "Session store and Pinecone scans"),
                ("middleware/", "Shared request pipeline"),
                ("observability/", "Trace log for each action"),
                ("data/", "Skills, jobs, questions, JSON feeds"),
            ],
        ),
        (
            AMBER,
            AMBER_BG,
            "Copies, docs, and ops",
            [
                ("Resume Analyzer folder", "Earlier standalone career app"),
                ("Research paper folder", "Earlier constructor project"),
                ("docs/", "Overviews, architecture, HTML copies"),
                ("evaluations/", "Local quality-check suite"),
                ("exports/", "ATS PDF and spreadsheet builders"),
                ("test_data/", "Sample papers and resumes"),
                ("Docker + Render", "Dockerfile, compose, render.yaml"),
                ("requirements.txt", "Flask, Streamlit, Gemini, Pinecone"),
            ],
        ),
    ]
    for index, (accent, fill, title, rows) in enumerate(columns):
        left = 0.32 + index * 4.32
        box(slide, left, 1.56, 4.16, 5.42, WHITE, rounded=True)
        box(slide, left, 1.56, 0.1, 5.42, accent)
        write(slide, left + 0.26, 1.68, 3.75, 0.36, [(title, 16, True, accent, 0)])
        y = 2.12
        for name, detail in rows:
            write(slide, left + 0.26, y, 3.72, 0.24, [(name, 13, True, INK, 0)])
            write(slide, left + 0.26, y + 0.22, 3.72, 0.28, [(detail, 12, False, MUTED, 0)])
            y += 0.58
    footer(slide, "2  /  3")


def slide_three(prs, blank):
    slide = prs.slides.add_slide(blank)
    background(slide, PAPER)
    header(
        slide,
        "REQUEST PATH",
        "Every action uses the same pipeline",
        "The browser calls a Flask route. Middleware wraps the handler, then oversight records the result.",
    )

    steps = [
        ("1", "Bind user"),
        ("2", "Trim text"),
        ("3", "Input check"),
        ("4", "Open trace"),
        ("5", "Run handler"),
        ("6", "Output check"),
    ]
    for index, (number, label) in enumerate(steps):
        left = 0.38 + index * 2.14
        box(slide, left, 1.58, 2.0, 0.78, NAVY, rounded=True)
        write(slide, left + 0.12, 1.66, 1.76, 0.26, [(number, 11, True, RGBColor(0x9A, 0xD7, 0xC4), 0)], align=PP_ALIGN.CENTER)
        write(slide, left + 0.12, 1.90, 1.76, 0.32, [(label, 14, True, WHITE, 0)], align=PP_ALIGN.CENTER)

    handlers = [
        (GREEN_BG, GREEN, "Resume", "Parse the file, score ATS, match roles, list gaps, and build a learning roadmap."),
        (BLUE_BG, BLUE, "Jobs", "Search by city and date. Live Apify feeds, or the local JSON catalog, plus cover letters."),
        (PURPLE_BG, PURPLE, "Research", "Chat over an uploaded paper, or draft an IEEE paper from a repository link."),
        (AMBER_BG, AMBER, "Review", "Candidate, hiring manager, or auditor approves, rejects, or corrects the result."),
    ]
    for index, (fill, accent, title, body) in enumerate(handlers):
        left = 0.38 + index * 3.22
        box(slide, left, 2.58, 3.06, 1.72, fill, rounded=True)
        write(slide, left + 0.16, 2.7, 2.74, 0.32, [(title, 16, True, accent, 0)])
        write(slide, left + 0.16, 3.08, 2.74, 1.05, [(body, 13, False, INK, 0)])

    box(slide, 0.38, 4.5, 8.28, 2.48, WHITE, rounded=True)
    write(slide, 0.58, 4.66, 7.9, 0.32, [("Main routes", 16, True, NAVY, 0)])
    left_routes = [
        ("/", "Hub"),
        ("/jobs", "Discovery"),
        ("/research", "Paper lab"),
        ("/observability", "Traces and alerts"),
    ]
    right_routes = [
        ("/resume", "Upload and analyze"),
        ("/dashboard", "Latest result"),
        ("/practice", "Interview drills"),
        ("/review", "Human sign-off"),
    ]
    for column, routes in ((0.58, left_routes), (4.55, right_routes)):
        y = 5.08
        for path, label in routes:
            write(slide, column, y, 1.7, 0.28, [(path, 13, True, TEAL, 0)])
            write(slide, column + 1.55, y, 2.35, 0.28, [(label, 13, False, INK, 0)])
            y += 0.38

    box(slide, 8.84, 4.5, 4.1, 2.48, TEAL, rounded=True)
    write(slide, 9.04, 4.66, 3.72, 0.32, [("Run it", 16, True, WHITE, 0)])
    write(
        slide,
        9.04,
        5.08,
        3.72,
        1.7,
        [
            ("python unified_app.py", 14, True, WHITE, 4),
            ("http://localhost:5000", 13, False, RGBColor(0xD7, 0xF6, 0xF0), 10),
            ("streamlit run streamlit_app.py", 13, True, WHITE, 4),
            ("http://localhost:8501", 13, False, RGBColor(0xD7, 0xF6, 0xF0), 0),
        ],
    )
    footer(slide, "3  /  3")


if __name__ == "__main__":
    print(build())
