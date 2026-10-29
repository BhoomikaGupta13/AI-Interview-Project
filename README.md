# AI Interview System

An end-to-end platform that runs a **personalised, proctored technical interview from a candidate's résumé** and produces an **explainable score** for the recruiter — no human interviewer needed for the first round.

The recruiter creates a candidate and the system e-mails single-use credentials. The candidate uploads a PDF résumé, and an LLM turns it into a structured profile and generates tailored questions. Each question is read aloud and answered on camera while the browser and server watch for malpractice. After the interview, a background job transcribes every answer with Whisper and scores it using embeddings plus two LLM judges.

> Built during an AI/ML internship at Dotsquares Technologies India Pvt. Ltd., Jaipur (May–July 2026).

---

## Features

**For candidates**
- Login with single-use credentials that expire after 48 h or as soon as the attempt starts.
- Upload a PDF résumé (≤ 10 MB) and receive up to 13 questions generated from your own skills, projects and experience.
- Each question has a **30 s read phase** (spoken by text-to-speech) and an **answer phase of up to 90 s**, recorded on camera.
- A live countdown, recording status and microphone-level monitor that warns when your voice is too quiet.

**Proctoring**

| Signal | Detection | Action |
|---|---|---|
| Fullscreen exit | Fullscreen API | Warning; session locked at **2** |
| Tab switch / focus loss | Page Visibility API, window blur | Warning; locked at **3** |
| No face / multiple faces | YOLOv8n-face on webcam frames every 300 ms | Warning; locked at **3** |
| Mobile phone | YOLOv8s, COCO class 67 (confidence ≥ 0.55) | Logged and shown |

Warnings are counted on state changes (e.g. ok → no face), not on every frame. A locked session is marked `TERMINATED`, and whatever was recorded is still transcribed and scored.

**For recruiters (admin console)**
- Create candidates. The e-mail address is checked for valid syntax, an MX record and an SMTP mailbox probe before the invitation is sent.
- A roster showing each candidate's status (Not started / In progress / Completed / Terminated) and latest score with its band.
- A per-candidate report with:
  - overall score and band;
  - proctoring counts and the lock reason, if any;
  - a per-question score matrix;
  - written feedback, strengths and improvements for each answer;
  - JSON export.
- Delete a candidate together with all of their records.

---

## How it works

```mermaid
flowchart LR
    A[Admin creates candidate] --> B[Invitation e-mail]
    B --> C[Candidate login]
    C --> D[Upload résumé PDF]
    D --> E[LLM → JSON profile]
    E --> F[Blueprint + LLM questions<br/>+ fuzzy de-duplication]
    F --> G[Interview<br/>read 30 s · answer ≤ 90 s]
    G -->|1-s video chunks| H[FastAPI server]
    G -->|events + frames| P[Proctoring rules<br/>+ YOLOv8]
    P -->|limit reached| T[TERMINATED]
    G -->|all answered| K[COMPLETED]
    T --> J[Background job]
    K --> J
    J --> W[FFmpeg enhance → Whisper]
    W --> S[Hybrid scoring]
    S --> R[Admin report]
```

### Question generation
1. **Validate the PDF and extract its text.** The file is opened with PyMuPDF and the text is cleaned.
2. **Build a structured profile.** The LLM returns JSON with nine keys: skills, projects, experience, education, certifications, achievements, research publications, patents and co-curricular activities.
3. **Fix the question count per category.** A deterministic blueprint sets how many questions each category gets:

   | Category | Rule |
   |---|---|
   | Skills | min(#skills, 4) |
   | Projects | min(2 × #projects, 4) |
   | Experience | 2 |
   | Research / Patents / Achievements | min(count, 1) each |

4. **Write and de-duplicate the questions.** The LLM writes the questions, and any question with a RapidFuzz ratio above 85 against an earlier one is dropped.

### Transcription
- Recordings are WebM files, uploaded in 1-second chunks so a crash loses at most one second.
- FFmpeg extracts the audio as 16 kHz mono and cleans it with a high-pass and low-pass filter, `afftdn` denoising, `dynaudnorm` and `loudnorm`.
- faster-whisper (`small`, CPU, int8, beam 5, English, temperature 0) produces the transcript.

### Scoring
Each answer goes through four steps:
1. **Remove the echo.** If the candidate began by reading the question aloud, that part is stripped.
2. **Correct recognition errors.** An LLM fixes speech-recognition mistakes. A **fidelity guardrail** rejects the correction, and keeps the raw transcript, if any of these fail:
   - the length must stay between 0.5× and 1.35× the original;
   - at least 55 % of the original words must be kept;
   - order-sensitive similarity must be at least 0.70.
3. **Compute three sub-scores (0–1):**
   - **S** — cosine similarity between BGE embeddings (`BAAI/bge-large-en-v1.5`) of the answer and LLM-generated key concepts;
   - **L** — LLM rubric: clarity, correctness, completeness;
   - **D** — LLM depth judge: architecture, challenges, outcomes, technology justification.
4. **Combine them into a 0–10 score:** `score = 10 × (w_s·S + w_l·L + w_d·D)`, with weights by question type:

| Type | w_s | w_l | w_d |
|---|---|---|---|
| Skill | 0.30 | 0.60 | 0.10 |
| Project / Experience | 0.10 | 0.30 | 0.60 |
| Research | 0.20 | 0.40 | 0.40 |
| Other | 0.20 | 0.50 | 0.30 |

The session score is a weighted average by question type: project 1.4, skill 1.2, achievement 0.8, others 1.0. It maps to a band: **Strong** ≥ 8.5, **Good** ≥ 7.0, **Average** ≥ 5.5, otherwise **Weak**. All weights and thresholds are in `backend/scoring/config.py`.

---

## Tech stack

| Layer | Technology |
|---|---|
| UI | Streamlit, embedded JavaScript (MediaRecorder, Fullscreen, Page Visibility, Web Speech APIs) |
| API server | FastAPI + Uvicorn |
| Database | PostgreSQL (psycopg2) |
| LLM | Groq API — `llama-3.3-70b-versatile` |
| Speech | faster-whisper, FFmpeg |
| Embeddings | sentence-transformers, `BAAI/bge-large-en-v1.5` |
| Vision | Ultralytics YOLOv8 (`yolov8n-face.pt`, `yolov8s.pt`), OpenCV |
| Other | PyMuPDF, RapidFuzz, bcrypt, email-validator, dnspython |

---

## Project structure

```
├── run_portal.py          # starts FastAPI (:5001) and the Streamlit portal (:8501)
├── portal.py              # role gateway: candidate / admin
├── streamlit_app.py       # candidate interview page
├── admin_app.py           # admin console
├── server.py              # FastAPI: chunk upload, proctoring, finalisation
└── backend/
    ├── auth/              # admin and candidate login gates
    ├── db/                # schema (database.py) and all SQL (queries.py)
    ├── resume/            # validator, parser, cleaner, LLM understanding
    ├── questions/         # blueprint, generator, de-duplication
    ├── interview/         # session, expiry, attempt lock, recorder component, post-interview job
    ├── proctoring/        # YOLOv8 face + phone detection
    ├── transcription/     # FFmpeg + Whisper pipeline
    ├── scoring/           # hybrid scoring pipeline
    ├── utils/             # LLM client, mailer, file manager
    └── ui/                # shared light/dark theme
```

Runtime data is written to `storage/`. The folder is git-ignored:

```
storage/resumes/            uploaded PDFs
storage/sessions/           session JSON (questions + profile)
storage/recordings/<id>/    q1.webm … qN.webm
storage/proctoring/         proctoring state per session
storage/audio/, transcripts/, scores/, post_interview_jobs/
```

---

## Getting started

### Prerequisites
- Python 3.12
- PostgreSQL
- [FFmpeg](https://ffmpeg.org/) on your `PATH`
- A [Groq API key](https://console.groq.com/)
- A Gmail account with an app password (for invitations)
- A Chromium-based desktop browser with camera and microphone access

### 1. Install

```bash
git clone https://github.com/BhoomikaGupta13/AI-Interview-Project.git
cd AI-Interview-Project
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install psycopg2-binary email-validator   # not yet listed in requirements.txt
```

The first scoring run downloads the BGE model (~1.3 GB) and the Whisper `small` model.

### 2. Configure

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_interview
GROQ_API_KEY=your_groq_key
GMAIL_SENDER=you@gmail.com
GMAIL_APP_PASSWORD=your_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
```

### 3. Prepare the database

The tables are created automatically on first start. The scoring and proctoring code also writes a few columns, and relies on unique constraints, that `init_db()` does not yet create. Run this once after the first start:

```sql
ALTER TABLE questions_answers
  ADD COLUMN IF NOT EXISTS question_score FLOAT,
  ADD COLUMN IF NOT EXISTS question_band  VARCHAR(50),
  ADD COLUMN IF NOT EXISTS feedback_text  TEXT;
ALTER TABLE questions_answers ADD CONSTRAINT qa_session_qno_unique UNIQUE (session_id, question_no);

ALTER TABLE scores ADD COLUMN IF NOT EXISTS max_score_scale INTEGER;
ALTER TABLE scores ADD CONSTRAINT scores_session_unique UNIQUE (session_id);

ALTER TABLE proctoring_flags ADD CONSTRAINT pf_session_unique UNIQUE (session_id);
```

### 4. Run

```bash
python run_portal.py
```

This starts the FastAPI server on **:5001** and the portal on **:8501**. Open http://localhost:8501 and choose *Admin login* or *Candidate login*.

**Default admin login:** `admin` / `admin123`. Change it in `backend/auth/auth.py` before any real use.

> **Routing note:** the browser recorder calls the API at `<page origin>/api/...`. Put a reverse proxy (e.g. Nginx) or a tunnel (e.g. ngrok) in front of both services. It should route `/api/*` → `localhost:5001` and everything else → `localhost:8501`. Without this, recordings and proctoring requests will not reach the server.

### Re-running post-processing manually

```bash
python -m backend.transcription.main <session_id>   # transcribe one session
python -m backend.scoring.pipeline   <session_id>   # score one session
```

---

## API endpoints (`server.py`)

| Method & path | Purpose |
|---|---|
| `POST /append_chunk` | Append a 1-second video chunk to `q<N>.webm` |
| `POST /upload_recording` | Save a whole recording in one request (fallback) |
| `POST /detect_faces` | Face + phone detection on a webcam frame |
| `POST /proctor_event` | Record a fullscreen / tab / face event and apply limits |
| `GET /proctor_status` | Current proctoring state for a session |
| `POST /finalize_interview` | Mark COMPLETED / TERMINATED and queue scoring |
| `GET /ping` | Health check |

---

## Known limitations

- **Security:**
  - the admin credentials are hard-coded;
  - the invitation e-mail contains the plain-text password;
  - the invitation link points to `localhost`.
- **Proctoring:**
  - a phone detection is logged but never locks the session;
  - the server counts a face warning from a single frame, so the browser's 4-frame debounce is effectively bypassed.
- **Duplicate questions:** filtering is character-based, so re-phrased duplicates (e.g. with "Can you…" prefixed) can slip through.
- **Scale:** post-processing runs on one in-process worker, so sessions are scored one at a time.
- **Fairness:** LLM-based scores should be validated against human ratings before being used for hiring decisions. Treat the band as a screening aid, not a verdict.


## Author

**Bhoomika Gupta** — B.Tech (CSE), Manipal University Jaipur
Internship: AIML Department, Dotsquares Technologies India Pvt. Ltd., Jaipur
