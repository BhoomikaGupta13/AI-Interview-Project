import json
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path


JOB_DIR = Path("storage/post_interview_jobs")
JOB_DIR.mkdir(parents=True, exist_ok=True)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="post-interview")
_guard = threading.Lock()
_active_sessions: set[str] = set()


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
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
    temp_path.replace(path)


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
        _write_status(session_id, "failed", error=error)
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
