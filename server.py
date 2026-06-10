"""
FastAPI upload server for AI Interview System.

Run from PROJECT ROOT:
    python server.py

Install:
    pip install fastapi uvicorn python-multipart

Health check: http://127.0.0.1:5001/ping
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

import cv2
from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import numpy as np
import uvicorn
from backend.proctoring.vision_processor import process_proctoring_frame, detector
from backend.db.queries import save_proctoring, get_conn

MAX_FACE_WARNINGS = 3
MAX_PHONE_WARNINGS = 2


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Interview Upload Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path("storage/recordings")
BASE_DIR.mkdir(parents=True, exist_ok=True)

PROCTOR_DIR = Path("storage/proctoring")
PROCTOR_DIR.mkdir(parents=True, exist_ok=True)


def _valid_session(session: str) -> bool:
    return bool(session) and not any(c in session for c in ["/", "\\", ".."])


def _proctor_path(session: str) -> Path:
    return PROCTOR_DIR / f"{session}.json"


def _load_proctor(session: str) -> dict[str, Any]:
    path = _proctor_path(session)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "session_id": session,
        "locked": False,
        "lock_reason": "",
        "fullscreen_warnings": 0,
        "tab_warnings": 0,
        "face_warnings": 0,
        "pose_warnings": 0,
        "face_detection_available": None,
        "face_state": "ok",
        "flags": [],
        "events": [],
    }


def _save_proctor(session: str, data: dict[str, Any]) -> None:
    _proctor_path(session).write_text(
        json.dumps(data, indent=4),
        encoding="utf-8",
    )


def _json(data: dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=data, status_code=status_code)


@app.post("/detect_faces")
async def detect_faces(
    request: Request,
    frame: UploadFile | None = File(default=None),
    session: str = Form(default=""),
):
    """
    Unified face + phone proctoring endpoint.
    Session is accepted as a form field (primary) or parsed from referer (fallback).
    Uses process_proctoring_frame() for phone detection — same engine, same thresholds.
    """
    try:
        if not frame:
            return {"status": "failed", "faces": 0, "phone_detected": False}

        # 1. Read raw bytes — pass directly to process_proctoring_frame (avoids double decode)
        raw = await frame.read()

        # 2. Run BOTH face + phone detection through the single authoritative pipeline
        result = process_proctoring_frame(raw, phone_conf_threshold=0.28)

        if result.get("status") != "success":
            return {"status": "failed", "faces": 0, "phone_detected": False}

        faces = result["faces"]
        phone_detected = result["phone_detected"]

        # 3. Resolve Session ID: form field is most reliable; referer is fallback
        session = session.strip()
        if not session:
            referer = request.headers.get("referer", "")
            if "session=" in referer:
                session = referer.split("session=")[-1].split("&")[0].strip()

        # 4. Persist warnings if session is resolvable
        if session and _valid_session(session):
            data = _load_proctor(session)

            # --- Phone warning (evaluated first; independent of face state) ---
            if phone_detected:
                previous_phone_state = data.get("phone_state", "ok")
                if previous_phone_state == "ok":
                    # Only increment on state transition (ok → detected), not every frame
                    data["phone_warnings"] = data.get("phone_warnings", 0) + 1
                    data["phone_state"] = "detected"
                    logger.warning(
                        f"[Proctor] Phone warning #{data['phone_warnings']} for session {session}"
                    )
                    if data["phone_warnings"] >= MAX_PHONE_WARNINGS:
                        data["locked"] = True
                        data["lock_reason"] = (
                            "Interview locked after unauthorized device (phone) detected."
                        )
            else:
                # Phone no longer in frame — reset state so next appearance counts again
                data["phone_state"] = "ok"

            # --- Face warning (independent of phone) ---
            face_state = "ok"
            if faces == 0:
                face_state = "no_face"
            elif faces > 1:
                face_state = "multiple_faces"

            previous_face_state = data.get("face_state", "ok")
            data["face_state"] = face_state
            if face_state != "ok" and previous_face_state == "ok":
                data["face_warnings"] += 1
                if data["face_warnings"] >= MAX_FACE_WARNINGS:
                    data["locked"] = True
                    data["lock_reason"] = (
                        "Interview locked after repeated face violations."
                    )

            _save_proctor(session, data)

        # 5. Return detection result + current proctor snapshot to the frontend
        proctor_data = (
            _load_proctor(session) if (session and _valid_session(session)) else {}
        )
        return {
            "status": "success",
            "faces": faces,
            "phone_detected": phone_detected,
            "proctor": proctor_data,
        }

    except Exception as exc:
        logger.exception("Error in secure detect_faces endpoint execution loop")
        return {
            "status": "error",
            "message": str(exc),
            "faces": 1,
            "phone_detected": False,
        }


@app.get("/ping")
async def ping():
    return {"status": "ok", "message": "FastAPI is running."}


@app.get("/proctor_status")
async def proctor_status(session: str = ""):
    session = session.strip()
    if not _valid_session(session):
        return _json({"status": "failed", "message": "invalid session"}, 400)
    return {"status": "success", "proctor": _load_proctor(session)}


@app.options("/proctor_event")
async def proctor_event_options():
    return Response(status_code=200)


@app.post("/proctor_event")
async def proctor_event(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)

    session = (payload.get("session") or "").strip()
    question = str(payload.get("question") or "").strip()
    event_type = (payload.get("event_type") or "").strip()
    details = payload.get("details") or {}

    if not _valid_session(session) or not event_type:
        return _json({"status": "failed", "message": "missing or invalid fields"}, 400)

    data = _load_proctor(session)
    event = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "event_type": event_type,
        "details": details,
    }
    data["events"].append(event)

    if event_type == "fullscreen_exit":
        data["fullscreen_warnings"] += 1
        if data["fullscreen_warnings"] >= 2:
            data["locked"] = True
            data["lock_reason"] = "Interview closed after 2 fullscreen exit warnings."

    elif event_type == "tab_switch":
        tab_reason = details.get("reason") if isinstance(details, dict) else ""
        recent_fullscreen_exit = False
        if tab_reason in ["window_blur", "iframe_blur"]:
            for previous in reversed(data["events"][:-1]):
                if previous.get("event_type") != "fullscreen_exit":
                    continue
                try:
                    previous_time = datetime.fromisoformat(previous["timestamp"])
                    current_time = datetime.fromisoformat(event["timestamp"])
                    recent_fullscreen_exit = (
                        abs((current_time - previous_time).total_seconds()) < 2.5
                    )
                except Exception:
                    recent_fullscreen_exit = False
                break

        if recent_fullscreen_exit:
            event["ignored"] = True
            event["ignore_reason"] = (
                "Suppressed blur/visibility event caused by fullscreen exit."
            )
            _save_proctor(session, data)
            return {"status": "success", "proctor": data}

        data["tab_warnings"] += 1
        if data["tab_warnings"] >= 3:
            data["locked"] = True
            data["lock_reason"] = "Interview locked after 3 tab switching warnings."

    elif event_type == "face_detection_unavailable":
        data["face_detection_available"] = False
        _save_proctor(session, data)
        return {"status": "success", "proctor": data}

    elif event_type == "face_ok":
        data["face_detection_available"] = True
        data["face_state"] = "ok"

    elif event_type in ["no_face", "multiple_faces", "looking_away"]:
        data["face_detection_available"] = True
        previous_face_state = data.get("face_state", "ok")
        data["face_state"] = event_type

        if previous_face_state == "ok":
            data["face_warnings"] += 1
            if event_type == "looking_away":
                data["pose_warnings"] = data.get("pose_warnings", 0) + 1
            flag = {
                "timestamp": event["timestamp"],
                "question": question,
                "event_type": event_type,
                "details": details,
            }
            data["flags"].append(flag)
        else:
            event["ignored"] = True
            event["ignore_reason"] = (
                "Face violation already active until exactly one face is stable."
            )

    _save_proctor(session, data)
    return {"status": "success", "proctor": data}


@app.options("/append_chunk")
async def append_chunk_options():
    return Response(status_code=200)


@app.post("/append_chunk")
async def append_chunk(
    session: str = Form(default=""),
    question: str = Form(default=""),
    chunk_num: str = Form(default="0"),
    chunk: UploadFile | None = File(default=None),
):
    try:
        session = session.strip()
        question = question.strip()
        chunk_num = chunk_num.strip() or "0"

        if not session or not question or chunk is None:
            return _json({"status": "failed", "message": "missing fields"}, 400)

        if not _valid_session(session):
            return _json({"status": "failed", "message": "invalid session"}, 400)

        folder = BASE_DIR / session
        folder.mkdir(parents=True, exist_ok=True)
        save_path = folder / f"q{question}.webm"

        mode = "wb" if chunk_num == "1" else "ab"
        with save_path.open(mode) as f:
            f.write(await chunk.read())

        total_kb = round(save_path.stat().st_size / 1024, 1)
        logger.info(
            "Chunk %s appended -> %s  (total %.1f KB)",
            chunk_num,
            save_path,
            total_kb,
        )

        return {
            "status": "success",
            "path": str(save_path),
            "chunk": chunk_num,
            "total_kb": total_kb,
        }

    except Exception as exc:
        logger.exception("Error appending chunk")
        return _json({"status": "error", "message": str(exc)}, 500)


@app.options("/upload_recording")
async def upload_recording_options():
    return Response(status_code=200)


@app.post("/upload_recording")
async def upload_recording(
    session: str = Form(default=""),
    question: str = Form(default=""),
    recording: UploadFile | None = File(default=None),
):
    try:
        session = session.strip()
        question = question.strip()

        if not session or not question or recording is None:
            return _json({"status": "failed", "message": "missing fields"}, 400)

        if not _valid_session(session):
            return _json({"status": "failed", "message": "invalid session"}, 400)

        folder = BASE_DIR / session
        folder.mkdir(parents=True, exist_ok=True)
        save_path = folder / f"q{question}.webm"

        with save_path.open("wb") as f:
            f.write(await recording.read())

        size_kb = round(save_path.stat().st_size / 1024, 1)
        logger.info("Full upload saved %s (%s KB)", save_path, size_kb)

        return {"status": "success", "path": str(save_path), "size_kb": size_kb}

    except Exception as exc:
        logger.exception("Error in upload_recording")
        return _json({"status": "error", "message": str(exc)}, 500)


if __name__ == "__main__":
    print("=" * 55)
    print("  FastAPI server -> http://0.0.0.0:5001")
    print("  Ping check     -> http://127.0.0.1:5001/ping")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")

# python server.py
