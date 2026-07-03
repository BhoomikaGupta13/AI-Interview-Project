import json
import os
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

JOB_DIR = Path("storage/post_interview_jobs")
JOB_DIR.mkdir(parents=True, exist_ok=True)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="post-interview")
_guard = threading.Lock()
_active_sessions: set[str] = set()

# Retry knobs for the atomic rename step. On Windows, os.replace() can raise
# PermissionError (WinError 5) if something else — most commonly OneDrive's
# sync engine, an antivirus scanner, or a search indexer — has a transient
# handle open on the destination file. These locks normally clear within
# milliseconds, so a short retry-with-backoff is enough; it is NOT a sign of
# a logic race in this module (writes for a given session are already
# strictly sequential — see _write_status callers).
_REPLACE_MAX_ATTEMPTS = 6
_REPLACE_BASE_DELAY_S = 0.05


def _status_path(session_id: str) -> Path:
    return JOB_DIR / f"{session_id}.json"


def _write_status(session_id: str, status: str, **details) -> None:
    payload = {
        "session_id": session_id,
        "status": status,
        "updated_at": datetime.now().isoformat(),
        **details,
    }
    path = _status_path(session_id)
    # Unique temp filename per write: cheap insurance against two writers
    # ever targeting the same temp path, even though current call sites are
    # already serialized per session.
    temp_path = path.with_suffix(f".{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    temp_path.write_text(json.dumps(payload, indent=4), encoding="utf-8")

    last_err = None
    for attempt in range(1, _REPLACE_MAX_ATTEMPTS + 1):
        try:
            temp_path.replace(path)
            return
        except PermissionError as e:
            last_err = e
            if attempt == _REPLACE_MAX_ATTEMPTS:
                break
            time.sleep(_REPLACE_BASE_DELAY_S * attempt)

    # All retries exhausted — clean up the orphaned temp file so it doesn't
    # pile up, then surface the real error.
    try:
        temp_path.unlink(missing_ok=True)
    except OSError:
        pass
    raise last_err


def _score_exists(session_id: str) -> bool:
    from backend.db.queries import get_score_by_session

    return get_score_by_session(session_id) is not None


def get_post_interview_status(session_id: str) -> dict:
    path = _status_path(session_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _run_post_interview(session_id: str) -> None:
    try:
        _write_status(session_id, "transcribing")

        from backend.transcription.main import InterviewPipeline

        InterviewPipeline().process_session(session_id)

        _write_status(session_id, "scoring")

        from backend.scoring import ScoringPipeline

        report = ScoringPipeline().score_session(session_id)
        _write_status(
            session_id,
            "completed",
            overall_score=report.get("overall_score"),
            band=report.get("band"),
        )
    except Exception:
        error = traceback.format_exc()
        try:
            _write_status(session_id, "failed", error=error)
        except Exception:
            # If even the failure write can't land (e.g. retries exhausted
            # under sustained file-lock contention), don't let that mask
            # the original error or crash silently inside the worker thread.
            print(
                f"[PostInterview] Session {session_id} ALSO failed to write "
                f"'failed' status:\n{traceback.format_exc()}"
            )
        print(f"[PostInterview] Session {session_id} failed:\n{error}")
    finally:
        with _guard:
            _active_sessions.discard(session_id)


def start_post_interview_processing(session_id: str) -> bool:
    """Queue transcription and scoring once for a completed interview."""
    with _guard:
        current_status = get_post_interview_status(session_id).get("status")
        if (
            session_id in _active_sessions
            or current_status in {"queued", "transcribing", "scoring", "completed"}
            or _score_exists(session_id)
        ):
            return False
        _active_sessions.add(session_id)

    _write_status(session_id, "queued")
    try:
        _executor.submit(_run_post_interview, session_id)
    except Exception:
        with _guard:
            _active_sessions.discard(session_id)
        raise
    return True
