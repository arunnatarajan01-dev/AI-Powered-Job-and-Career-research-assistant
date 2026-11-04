# AI Powered Job and Career research assistant

A Flask application that combines career guidance and research assistance in one site. The hub is branded **IntegrateAI**. From there you can analyze a resume or work with research papers.

The running application is `unified_app.py` at the project root. It serves the pages in `templates/` and the logic in `parser/`, `models/`, `recommendation/`, `preparation/`, and `safety/`.

---

## What you can do

### Hub (`/`)

The landing page is a green-and-gold screen with two entries:

- **AI Resume Analyzer** opens the career tools.
- **Research Assistant** opens paper construction and document chat.

### Career tools

Upload a PDF or DOCX resume (up to 16 MB). The analyzer:

- Extracts contact details, education, experience, and skills from `data/skills_db.csv`
- Scores the resume for ATS-style completeness and formatting
- Recommends roles from `data/jobs.csv`
- Shows skill gaps, a learning roadmap, career-path suggestions, and interview questions for the top matching role

Job matching uses `all-MiniLM-L6-v2` when `sentence-transformers` is installed. Without that package, matching falls back to keywords.

After analysis, the dashboard at `/dashboard` shows the latest result for the current browser session. `/practice` lists company interview questions and coding problems from `data/company_questions.csv` and `data/coding_questions.csv`.

### Research assistant (`/research`)

One page with three views:

| View | What it does |
| --- | --- |
| Home | Short introduction and links into the two labs |
| Constructor | Builds an IEEE-style paper draft from a public GitHub URL, author name, and institution. Gemini returns the sections as JSON. The browser can download the draft as a PDF. This view uses a silver-and-charcoal background. |
| Deconstructor | Reads uploaded PDFs in the browser, then answers questions from that text through Gemini. This view uses a cyan accent background. |

Constructor and deconstructor requests pass through the safety checks in `safety/guardrail.py` before and after the model call. Blocked requests can email an administrator when SMTP settings are present, and they are also written to `logs/admin_alerts.log`.

---

## Run it locally

Python 3.10 or newer is expected.

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
```

Optional mail settings, used only when a guardrail blocks a request:

```env
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
ADMIN_EMAIL=
```

Start the Flask app:

```powershell
python unified_app.py
```

Open [http://localhost:5000](http://localhost:5000).

The same career and research tools are also available in Streamlit:

```powershell
streamlit run streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501). Streamlit uses the resume, job, and research modules directly. The Flask site stays the hosted app.

Research paper generation and document chat need a valid `GEMINI_API_KEY`. Resume analysis, the dashboard, and practice questions work without it. For semantic job matching, also install:

```powershell
pip install sentence-transformers
```

---

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | IntegrateAI hub |
| GET | `/resume` | Resume upload |
| POST | `/analyze` | Run the resume pipeline and store the result |
| GET | `/dashboard` | Latest analysis for this session |
| GET | `/practice` | Interview and coding practice |
| GET | `/research` | Constructor and deconstructor |
| GET | `/api/interview-questions/<company>` | Company interview questions |
| GET | `/api/coding-practice` | Coding problems, with optional company, topic, and difficulty |
| GET | `/api/companies` | Company lists |
| GET | `/api/topics` | Coding topics |
| POST | `/api/constructor_generate` | IEEE paper draft from a repository URL |
| POST | `/api/chat_research` | Document-grounded research chat |

Gemini calls try available `generateContent` models and prefer names that contain `flash` or `pro`.

---

## Project layout

```text
unified_app.py          Flask entry point
streamlit_app.py        Streamlit entry point
app_pages/              Streamlit pages for home, resume, jobs, practice, and research
templates/              Hub, resume, dashboard, practice, and research pages
static/                 CSS and research page script
parser/                 PDF, DOCX, and section extraction
models/                 Skills, ATS score, feedback, and job matching
recommendation/         Skill gaps, roadmap, and career paths
preparation/            Interview and coding question banks
data/                   Skills, jobs, and practice CSVs
safety/                 Input and output guardrails, admin alerts
uploads/                Temporary resume files, removed after analysis
```

`Resume Analyzer and Job Recommendation System/` and `research-Paper-AI-Assistant-main/` are earlier standalone copies. They are not what `python unified_app.py` serves.

---

## Hosted copy

A deployed instance is published at [https://ai-career-research-assistant-resume.onrender.com](https://ai-career-research-assistant-resume.onrender.com). On the free tier, the first request after idle time can take about a minute.
# AI-Powered-Job-and-Career-research-assistant
# AI-Powered-Job-and-Career-research-assistant
