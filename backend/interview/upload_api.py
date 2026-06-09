from pathlib import Path
import logging

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

upload_router = APIRouter()

BASE_DIR = Path("storage/recordings")
BASE_DIR.mkdir(parents=True, exist_ok=True)


def _json(content: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=content, status_code=status_code)


def _valid_session(session: str) -> bool:
    return bool(session) and not any(c in session for c in ["/", "\\", ".."])


@upload_router.options("/upload_recording")
async def upload_recording_options():
    return Response(status_code=200)


@upload_router.post("/upload_recording")
async def upload_recording(
    session: str = Form(default=""),
    question: str = Form(default=""),
    recording: UploadFile | None = File(default=None),
):
    """
    Receives a recorded .webm blob from the browser MediaRecorder and saves it.

    Expected multipart/form-data fields:
        session   - the session UUID
        question  - the question number, such as "1" or "2"
        recording - the .webm binary file

    Saved to:
        storage/recordings/<session_id>/q<question_no>.webm
    """
    try:
        session = session.strip()
        question = question.strip()

        if not session:
            return _json({"status": "failed", "message": "missing: session"}, 400)
        if not question:
            return _json({"status": "failed", "message": "missing: question"}, 400)
        if recording is None:
            return _json(
                {"status": "failed", "message": "missing: recording file"}, 400
            )

        if not _valid_session(session):
            return _json({"status": "failed", "message": "invalid session id"}, 400)

        folder = BASE_DIR / session
        folder.mkdir(parents=True, exist_ok=True)
        save_path = folder / f"q{question}.webm"

        with save_path.open("wb") as f:
            f.write(await recording.read())

        size_kb = save_path.stat().st_size / 1024
        logger.info(
            "Saved recording | session=%s | question=%s | path=%s | size=%.1f KB",
            session,
            question,
            save_path,
            size_kb,
        )

        return {
            "status": "success",
            "path": str(save_path),
            "size_kb": round(size_kb, 1),
        }

    except Exception as exc:
        logger.exception("Error saving recording")
        return _json({"status": "error", "message": str(exc)}, 500)
