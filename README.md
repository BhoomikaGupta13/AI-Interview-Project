# AI Interview System

An AI-powered, résumé-based technical interview platform that automates candidate assessment through personalized question generation, real-time video proctoring, speech transcription, and AI-based answer evaluation.

The system enables recruiters to create candidate accounts and conduct structured technical interviews without requiring a human interviewer for the initial screening round.

Candidates upload their résumés, receive questions tailored to their experience and skills, and answer them through a webcam-recorded interview. The platform monitors interview activity, transcribes responses, evaluates answers, and generates detailed performance reports for recruiters.

## Features

### 1. Candidate Portal
- Secure candidate authentication using recruiter-provided credentials.
- Automatic credential expiration after 48 hours or once an interview attempt begins.
- PDF résumé upload and validation.
- AI-powered résumé parsing and structured candidate profile extraction.
- Personalized technical question generation based on skills, projects, experience, and achievements.
- Text-to-speech question reading.
- Timed interview sessions with webcam and microphone recording.
- Live recording status and microphone-level monitoring.

### 2. AI-Based Proctoring
The system monitors candidate activity during interviews using browser-based monitoring and computer vision.

| Detection | Technology | Action |
|---|---|---|
| Fullscreen exit | Fullscreen API | Warning and session lock |
| Tab switching | Page Visibility API | Warning and session lock |
| Face detection | YOLOv8 | Detects missing or multiple faces |
| Mobile phone detection | YOLOv8 | Detects and logs phone presence |
| Interview activity | Browser and server events | Records proctoring events |

Proctoring events and warnings are stored for recruiter review.

### 3. Admin Portal
- Admin authentication.
- Candidate account creation and credential distribution through email.
- Candidate management and interview status tracking.
- Candidate-wise interview reports.
- Overall performance scores and evaluation bands.
- Per-question evaluation and feedback.
- Proctoring violation summaries.
- JSON report export.
- Candidate record deletion.

### 4. Automated Transcription and Evaluation
- Audio extraction and preprocessing using FFmpeg.
- Speech-to-text transcription using faster-whisper.
- Transcript correction using an LLM with fidelity checks.
- Semantic similarity evaluation using BGE embeddings.
- LLM-based evaluation of answer correctness, clarity, completeness, and technical depth.
- Weighted scoring and performance classification.
- Automated post-interview processing.

## System Workflow

1. The administrator creates a candidate account.
2. The candidate receives login credentials through email.
3. The candidate logs in and uploads a résumé.
4. The system extracts résumé information and generates a structured candidate profile.
5. Personalized technical interview questions are generated.
6. The candidate answers questions through a timed webcam-recorded interview.
7. The system records interview responses and monitors proctoring events.
8. Audio is extracted, processed, and transcribed.
9. AI models evaluate the answers and calculate performance scores.
10. The administrator views the final report and candidate performance.

## Technology Stack

| Component | Technologies |
|---|---|
| Frontend | Streamlit, HTML, CSS, JavaScript |
| Backend API | FastAPI, Uvicorn |
| Database | PostgreSQL, psycopg2 |
| LLM Integration | Groq API |
| Résumé Processing | PyMuPDF |
| Question Generation | LLMs, RapidFuzz |
| Computer Vision | YOLOv8, OpenCV |
| Speech Recognition | faster-whisper |
| Audio Processing | FFmpeg |
| Embeddings | Sentence Transformers, BGE |
| Authentication | bcrypt |
| Email | SMTP, Gmail |
| Programming Language | Python 3.12 |

## Project Structure

```text
AI-Interview-Project/
│
├── backend/
│   ├── auth/
│   ├── db/
│   │   ├── database.py
│   │   └── queries.py
│   ├── interview/
│   ├── proctoring/
│   ├── questions/
│   ├── resume/
│   ├── scoring/
│   ├── transcription/
│   ├── utils/
│   │   ├── file_manager.py
│   │   ├── llm_client.py
│   │   └── mailer.py
│   └── ui/
│
├── admin_app.py
├── streamlit_app.py
├── portal.py
├── portal_app.py
├── server.py
├── run_portal.py
├── requirements.txt
├── .gitignore
├── .env
└── README.md
```

Runtime files, including uploaded résumés, recordings, transcripts, and reports, are stored under the `storage/` directory when generated.

---

# Getting Started

Follow these instructions to set up and run the project on Windows.

## Prerequisites

Install the following before proceeding:

1. Python 3.12
2. PostgreSQL 17 (or a compatible PostgreSQL version)
3. pgAdmin 4
4. Git
5. FFmpeg
6. A Groq API key
7. A Gmail account with an App Password (for candidate invitations)

A Chromium-based browser such as Google Chrome is recommended for webcam and microphone access.

## Step 1: Clone the Repository

Open PowerShell or the VS Code terminal.

```powershell
git clone https://github.com/BhoomikaGupta13/AI-Interview-Project.git

cd AI-Interview-Project
```

## Step 2: Create a Virtual Environment

```powershell
python -m venv venv
```

Activate the environment:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate the environment again:

```powershell
.\venv\Scripts\Activate.ps1
```

## Step 3: Install Dependencies

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install the project dependencies:

```powershell
pip install -r requirements.txt
```

Install the additional email validation dependency if it is not already included:

```powershell
pip install email-validator
```

Verify the environment:

```powershell
pip check
```

The expected output is:

```text
No broken requirements found.
```

**Note:** The first scoring run may download pretrained embedding and speech-recognition models. Ensure sufficient disk space and a stable internet connection.

## Step 4: Configure PostgreSQL

Start the PostgreSQL service.

Open pgAdmin 4 and connect to your local PostgreSQL server.

Create a database named:

```text
ai_interview
```

Default local connection settings:

| Setting | Value |
|---|---|
| Host | localhost |
| Port | 5432 |
| Database | ai_interview |
| Username | postgres |
| Password | Your PostgreSQL password |

The application connects to PostgreSQL using the `DATABASE_URL` environment variable.

## Step 5: Configure Environment Variables

Create a file named `.env` in the project root directory.

Add the following configuration:

```env
# PostgreSQL Configuration
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/ai_interview

# Groq API Configuration
GROQ_API_KEY=your_groq_api_key

# Email Configuration
GMAIL_SENDER=your_email@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password

SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
```

Replace the placeholder values with your actual credentials.

**Important:**
- Generate your Groq API key from https://console.groq.com/
- Use a Gmail App Password rather than your normal Gmail password.
- If your PostgreSQL password contains special URL characters such as `@`, encode them in the connection URL. For example, `@` becomes `%40`.
- Never upload your `.env` file or expose API keys and passwords on GitHub.

## Step 6: Initialize the Database

The application initializes its database tables through:

```python
from backend.db.database import init_db
init_db()
```

The initialization creates the required base tables if they do not already exist.

These include:

- candidates
- interview_sessions
- resume_data
- questions_answers
- scores
- proctoring_flags

The project may also require additional schema columns and unique constraints for scoring and report generation.

If your project version requires those migrations, execute the following SQL once using the pgAdmin Query Tool against the `ai_interview` database:

```sql
ALTER TABLE questions_answers
ADD COLUMN IF NOT EXISTS question_score FLOAT,
ADD COLUMN IF NOT EXISTS question_band VARCHAR(50),
ADD COLUMN IF NOT EXISTS feedback_text TEXT;

ALTER TABLE scores
ADD COLUMN IF NOT EXISTS max_score_scale INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'qa_session_qno_unique'
    ) THEN
        ALTER TABLE questions_answers
        ADD CONSTRAINT qa_session_qno_unique
        UNIQUE (session_id, question_no);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'scores_session_unique'
    ) THEN
        ALTER TABLE scores
        ADD CONSTRAINT scores_session_unique
        UNIQUE (session_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'pf_session_unique'
    ) THEN
        ALTER TABLE proctoring_flags
        ADD CONSTRAINT pf_session_unique
        UNIQUE (session_id);
    END IF;
END $$;
```

**Note:** Execute the constraint migrations only after checking for existing duplicate records. They will fail if duplicate values already exist in the relevant columns. These migrations should be aligned with the actual database queries in the project.

## Step 7: Install and Configure FFmpeg

FFmpeg is required for audio extraction and preprocessing.

Download FFmpeg:

https://ffmpeg.org/download.html

Add its `bin` directory to your Windows PATH.

Verify the installation:

```powershell
ffmpeg -version
```

If the command displays the FFmpeg version, the installation is successful.

## Step 8: Run the Application

Ensure that:
- Your virtual environment is activated.
- PostgreSQL is running.
- The database exists.
- Your `.env` file is configured.
- Required dependencies are installed.

From the project root, execute:

```powershell
python run_portal.py
```

The application launcher is intended to start both services:

| Service | Local URL |
|---|---|
| Streamlit Portal | http://localhost:8501 |
| FastAPI Backend | http://localhost:5001 |
| Backend Health Check | http://127.0.0.1:5001/ping |

Open the portal in your browser:

http://localhost:8501

The portal provides the available login options for administrators and candidates.

**Important:** Run the launcher from the project root directory so that Python imports, environment variables, and storage paths resolve correctly.

## Step 9: Verify the Backend

Open the following URL:

http://127.0.0.1:5001/ping

A successful response should look like:

```json
{
    "status": "ok",
    "message": "FastAPI is running."
}
```

You can also open the FastAPI documentation:

http://127.0.0.1:5001/docs

## Step 10: External Access Using ngrok

For local development, localhost access is sufficient.

If candidates need to access the application from other devices or networks, configure a reverse proxy or tunnel.

The application uses two services:

- Streamlit: port 8501
- FastAPI: port 5001

The browser-side API requests must reach the FastAPI backend. Configure routing so that:

```text
/api/*  →  FastAPI (localhost:5001)

/*      →  Streamlit (localhost:8501)
```

For external access, use an appropriately configured reverse proxy or tunnel that exposes both services through the required routing.

Do not expose the development application publicly without implementing appropriate authentication, access controls, and HTTPS.

---

# API Endpoints

The FastAPI server provides the following endpoints:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/ping` | Backend health check |
| POST | `/append_chunk` | Upload recorded video chunks |
| POST | `/upload_recording` | Upload a complete recording |
| POST | `/detect_faces` | Face and phone detection |
| POST | `/proctor_event` | Record proctoring events |
| GET | `/proctor_status` | Retrieve proctoring status |
| POST | `/finalize_interview` | Finalize an interview session |

---

# Important Notes

1. Keep PostgreSQL running while using the application.
2. Ensure all required environment variables are configured.
3. Grant browser permission to access the camera and microphone.
4. Internet connectivity is required for Groq API requests and initial model downloads.
5. Email invitations require valid SMTP configuration.
6. Do not commit passwords, API keys, candidate records, uploaded résumés, or interview recordings.
7. AI-generated scores should be treated as assessment assistance and reviewed appropriately before making recruitment decisions.

# Known Limitations

- LLM-based evaluations may vary depending on the generated responses and model outputs.
- Email delivery depends on SMTP availability and recipient mail-server policies.
- Proctoring accuracy depends on webcam quality, lighting, and detection-model performance.
- The application currently uses a local PostgreSQL database and local runtime storage.
- Production deployment requires additional security, scalability, and infrastructure configurations.

# Future Enhancements

- Adaptive follow-up question generation.
- Improved head-pose and gaze-based monitoring.
- Enhanced multi-person and second-voice detection.
- Integrated coding assessment rounds.
- Scalable background processing and task queues.
- Cloud-based storage and deployment.
- Improved recruiter analytics and candidate comparisons.
