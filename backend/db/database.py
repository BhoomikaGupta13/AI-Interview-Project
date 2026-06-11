# backend/db/database.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def init_db():
    """Create all tables if they don't exist. Run once on startup."""
    sql = """
    CREATE TABLE IF NOT EXISTS candidates (
        id              SERIAL PRIMARY KEY,
        username        VARCHAR(100) UNIQUE NOT NULL,
        password_hash   VARCHAR(255) NOT NULL,
        full_name       VARCHAR(255),
        email           VARCHAR(255),
        created_by      VARCHAR(100),
        created_at      TIMESTAMP DEFAULT NOW(),
        interview_done  BOOLEAN DEFAULT FALSE,
        is_expired      BOOLEAN DEFAULT FALSE,
        credential_expires_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS interview_sessions (
        id              SERIAL PRIMARY KEY,
        session_id      VARCHAR(100) UNIQUE NOT NULL,
        username        VARCHAR(100) REFERENCES candidates(username),
        status          VARCHAR(50),
        started_at      TIMESTAMP,
        completed_at    TIMESTAMP,
        expires_at      TIMESTAMP,
        created_at      TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS resume_data (
        id              SERIAL PRIMARY KEY,
        session_id      VARCHAR(100) REFERENCES interview_sessions(session_id),
        username        VARCHAR(100),
        raw_profile     JSONB,
        skills          JSONB,
        projects        JSONB,
        created_at      TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS questions_answers (
        id              SERIAL PRIMARY KEY,
        session_id      VARCHAR(100) REFERENCES interview_sessions(session_id),
        question_no     INTEGER,
        question_type   VARCHAR(50),
        question_text   TEXT,
        answer_text     TEXT,
        created_at      TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS scores (
        id              SERIAL PRIMARY KEY,
        session_id      VARCHAR(100) REFERENCES interview_sessions(session_id),
        username        VARCHAR(100),
        overall_score   FLOAT,
        band            VARCHAR(50),
        total_questions INTEGER,
        scored          INTEGER,
        full_report     JSONB,
        created_at      TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS proctoring_flags (
        id                  SERIAL PRIMARY KEY,
        session_id          VARCHAR(100) REFERENCES interview_sessions(session_id),
        fullscreen_warnings INTEGER DEFAULT 0,
        tab_warnings        INTEGER DEFAULT 0,
        face_warnings       INTEGER DEFAULT 0,
        pose_warnings       INTEGER DEFAULT 0,
        phone_warnings      INTEGER DEFAULT 0,
        locked              BOOLEAN DEFAULT FALSE,
        lock_reason         TEXT,
        full_log            JSONB,
        created_at          TIMESTAMP DEFAULT NOW()
    );

    ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS is_expired BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS credential_expires_at TIMESTAMP;

    ALTER TABLE proctoring_flags
        ADD COLUMN IF NOT EXISTS pose_warnings INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS phone_warnings INTEGER DEFAULT 0;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("[DB] Tables ready.")
