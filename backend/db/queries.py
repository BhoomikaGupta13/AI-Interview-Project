# backend/db/queries.py
import json
import bcrypt
from datetime import datetime, timedelta
from .database import get_conn

# ── Credentials ───────────────────────────────────────────────────────────────


def candidate_login_allowed(username):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.credential_expires_at,
                    COALESCE(c.is_expired, FALSE),
                    COALESCE(c.interview_done, FALSE),
                    EXISTS (
                        SELECT 1
                        FROM interview_sessions s
                        WHERE s.username = c.username
                          AND (
                              s.started_at IS NOT NULL
                              OR s.completed_at IS NOT NULL
                              OR s.status IN ('IN_PROGRESS', 'COMPLETED', 'TERMINATED', 'EXPIRED')
                          )
                    ) AS attempt_used
                FROM candidates c
                WHERE c.username=%s
                """,
                (username,),
            )

            row = cur.fetchone()

            if not row:
                return False

            expiry = row[0]
            expired_flag = row[1]
            interview_done = row[2]
            attempt_used = row[3]

            if expired_flag or interview_done or attempt_used:
                if attempt_used and not expired_flag:
                    cur.execute(
                        """
                        UPDATE candidates
                        SET is_expired=TRUE
                        WHERE username=%s
                        """,
                        (username,),
                    )
                    conn.commit()
                return False

            if expiry and datetime.now() > expiry:
                cur.execute(
                    """
                    UPDATE candidates
                    SET is_expired=TRUE
                    WHERE username=%s
                    """,
                    (username,),
                )
                conn.commit()
                return False

            return True


def create_candidate(username, password, full_name, email, created_by):

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    expiry = datetime.now() + timedelta(hours=48)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidates
                (
                    username,
                    password_hash,
                    full_name,
                    email,
                    created_by,
                    credential_expires_at
                )
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (username) DO NOTHING
                RETURNING id
                """,
                (username, hashed, full_name, email, created_by, expiry),
            )

            row = cur.fetchone()

        conn.commit()

    return row is not None


def verify_candidate(username, password):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash FROM candidates WHERE username=%s", (username,)
            )
            row = cur.fetchone()
    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row[0].encode())


def get_all_candidates():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH latest_scores AS (
                    SELECT DISTINCT ON (username)
                           username, overall_score, band, created_at AS scored_at
                    FROM scores
                    ORDER BY username, created_at DESC
                ),
                latest_sessions AS (
                    SELECT DISTINCT ON (username)
                           username, status, completed_at, created_at
                    FROM interview_sessions
                    ORDER BY username,
                             COALESCE(completed_at, started_at, created_at) DESC
                )
                SELECT c.username, c.full_name, c.email, c.created_at,
                       (
                           COALESCE(c.interview_done, FALSE)
                           OR EXISTS (
                               SELECT 1
                               FROM interview_sessions s
                               WHERE s.username = c.username
                                 AND (
                                     s.status = 'COMPLETED'
                                     OR s.completed_at IS NOT NULL
                                 )
                           )
                       ) AS interview_done,
                       COALESCE(ls.status, 'NOT_STARTED') AS interview_status,
                       ls.completed_at,
                       s.overall_score, s.band, s.scored_at
                FROM candidates c
                LEFT JOIN latest_sessions ls ON ls.username = c.username
                LEFT JOIN latest_scores s ON s.username = c.username
                ORDER BY c.created_at DESC
            """)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def delete_candidate(username):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT session_id FROM interview_sessions WHERE username=%s",
                (username,),
            )
            session_ids = [row[0] for row in cur.fetchall()]

            deleted = {
                "username": username,
                "sessions": len(session_ids),
                "proctoring_flags": 0,
                "scores": 0,
                "questions_answers": 0,
                "resume_data": 0,
                "interview_sessions": 0,
                "candidates": 0,
                "session_ids": session_ids,
            }

            if session_ids:
                cur.execute(
                    "DELETE FROM proctoring_flags WHERE session_id = ANY(%s)",
                    (session_ids,),
                )
                deleted["proctoring_flags"] = cur.rowcount

                cur.execute(
                    "DELETE FROM questions_answers WHERE session_id = ANY(%s)",
                    (session_ids,),
                )
                deleted["questions_answers"] = cur.rowcount

                cur.execute(
                    "DELETE FROM resume_data WHERE session_id = ANY(%s)",
                    (session_ids,),
                )
                deleted["resume_data"] = cur.rowcount

                cur.execute(
                    "DELETE FROM scores WHERE session_id = ANY(%s)",
                    (session_ids,),
                )
                deleted["scores"] = cur.rowcount

                cur.execute(
                    "DELETE FROM interview_sessions WHERE session_id = ANY(%s)",
                    (session_ids,),
                )
                deleted["interview_sessions"] = cur.rowcount

            cur.execute("DELETE FROM scores WHERE username=%s", (username,))
            deleted["scores"] += cur.rowcount

            cur.execute("DELETE FROM resume_data WHERE username=%s", (username,))
            deleted["resume_data"] += cur.rowcount

            cur.execute("DELETE FROM candidates WHERE username=%s", (username,))
            deleted["candidates"] = cur.rowcount

        conn.commit()

    return deleted


def mark_interview_done(username):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE candidates SET interview_done=TRUE, is_expired = TRUE WHERE username=%s",
                (username,),
            )
        conn.commit()


def mark_interview_started(username):
    """Expire credentials as soon as the candidate consumes their single attempt."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE candidates SET is_expired=TRUE WHERE username=%s",
                (username,),
            )
        conn.commit()


# ── Session ───────────────────────────────────────────────────────────────────


def save_session(session_id, username, status, expires_at):
    """Insert session row. Safe to call multiple times — ignores if already exists."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO interview_sessions
                    (session_id, username, status, expires_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_id) DO NOTHING
            """,
                (session_id, username, status, expires_at),
            )
        conn.commit()


def set_session_started(session_id):
    """Set started_at to now — called exactly once when interview begins."""
    from datetime import datetime

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE interview_sessions
                SET started_at = %s, status = 'IN_PROGRESS'
                WHERE session_id = %s AND started_at IS NULL
            """,
                (datetime.now(), session_id),
            )
        conn.commit()


def update_session_status(session_id, status, completed_at=None):
    """Update status and optionally completed_at. Safe to call on reruns —
    uses WHERE to avoid overwriting completed_at with NULL on repeated calls."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if completed_at:
                cur.execute(
                    """
                    UPDATE interview_sessions
                    SET status=%s, completed_at=%s
                    WHERE session_id=%s
                """,
                    (status, completed_at, session_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE interview_sessions
                    SET status=%s
                    WHERE session_id=%s
                """,
                    (status, session_id),
                )
            if status == "COMPLETED":
                cur.execute(
                    """
                    UPDATE candidates c
                    SET interview_done=TRUE, is_expired=TRUE
                    FROM interview_sessions s
                    WHERE s.session_id=%s
                      AND s.username = c.username
                    """,
                    (session_id,),
                )
        conn.commit()


# ── Resume ────────────────────────────────────────────────────────────────────


def save_resume_data(session_id, username, profile):
    """Insert resume. ON CONFLICT DO NOTHING so reruns don't duplicate."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resume_data
                    (session_id, username, raw_profile, skills, projects)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """,
                (
                    session_id,
                    username,
                    json.dumps(profile),
                    json.dumps(profile.get("skills", [])),
                    json.dumps(profile.get("projects", [])),
                ),
            )
        conn.commit()


# ── Questions + Answers ───────────────────────────────────────────────────────


def save_questions_answers(session_id, results: list):
    """
    Upsert questions+answers from scoring results.
    Uses (session_id, question_no) as the unique key.
    Requires the unique constraint — add it if missing:
      ALTER TABLE questions_answers
        ADD CONSTRAINT qa_session_qno_unique UNIQUE (session_id, question_no);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            for r in results:
                cur.execute(
                    """
                    INSERT INTO questions_answers
                        (session_id, question_no, question_type,
                         question_text, answer_text)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (session_id, question_no) DO UPDATE
                        SET answer_text   = EXCLUDED.answer_text,
                            question_type = EXCLUDED.question_type
                """,
                    (
                        session_id,
                        r.get("question_no"),
                        r.get("question_type", "general"),
                        r.get("question", ""),
                        r.get("answer", ""),
                    ),
                )
        conn.commit()


# ── Scores ────────────────────────────────────────────────────────────────────


def save_score(session_id, username, report: dict):
    """
    Upsert score row keyed on session_id.
    ON CONFLICT DO UPDATE so re-running scoring overwrites with latest results.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scores
                    (session_id, username, overall_score, band,
                     total_questions, scored, full_report)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE
                    SET overall_score   = EXCLUDED.overall_score,
                        band            = EXCLUDED.band,
                        total_questions = EXCLUDED.total_questions,
                        scored          = EXCLUDED.scored,
                        full_report     = EXCLUDED.full_report,
                        username        = EXCLUDED.username
            """,
                (
                    session_id,
                    username,
                    report["overall_score"],
                    report["band"],
                    report["total_questions"],
                    report["scored"],
                    json.dumps(report),
                ),
            )
        conn.commit()


def get_score_by_session(session_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT full_report FROM scores WHERE session_id=%s", (session_id,)
            )
            row = cur.fetchone()
    return row[0] if row else None


# ── Proctoring ────────────────────────────────────────────────────────────────


def save_proctoring(session_id, proctor: dict):
    """
    Upsert proctoring data — keyed on session_id so no matter how many times
    the finished screen rerenders, only ONE row exists per session.
    Requires unique constraint on session_id — add if missing:
      ALTER TABLE proctoring_flags
        ADD CONSTRAINT pf_session_unique UNIQUE (session_id);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO proctoring_flags
                    (session_id, fullscreen_warnings, tab_warnings,
                     face_warnings, pose_warnings, phone_warnings, locked,
                     lock_reason, full_log)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE
                    SET fullscreen_warnings = EXCLUDED.fullscreen_warnings,
                        tab_warnings        = EXCLUDED.tab_warnings,
                        face_warnings       = EXCLUDED.face_warnings,
                        pose_warnings       = EXCLUDED.pose_warnings,
                        phone_warnings      = EXCLUDED.phone_warnings,
                        locked              = EXCLUDED.locked,
                        lock_reason         = EXCLUDED.lock_reason,
                        full_log            = EXCLUDED.full_log
            """,
                (
                    session_id,
                    proctor.get("fullscreen_warnings", 0),
                    proctor.get("tab_warnings", 0),
                    proctor.get("face_warnings", 0),
                    proctor.get("pose_warnings", 0),
                    proctor.get("phone_warnings", 0),
                    proctor.get("locked", False),
                    proctor.get("lock_reason", ""),
                    json.dumps(proctor),
                ),
            )
        conn.commit()
