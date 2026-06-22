import streamlit as st
import time
import json
from datetime import datetime
from pathlib import Path
import streamlit.components.v1 as components

from backend.resume.validator import validate_resume
from backend.utils.file_manager import save_resume
from backend.resume.parser import extract_text
from backend.resume.cleaner import clean_resume
from backend.resume.understand import understand_resume
from backend.questions.blueprint import build_blueprint
from backend.questions.generator import generate_questions
from backend.questions.validator import validate_questions
from backend.interview.session_manager import create_session
from backend.interview.interview_engine import initialize_interview
from backend.interview.question_manager import get_question
from backend.interview.mediarecorder_component import media_recorder_component
from backend.interview.post_interview import (
    start_post_interview_processing,
    get_post_interview_status,
)
from streamlit_autorefresh import st_autorefresh

from backend.db.database import init_db
from backend.db.queries import (
    save_session,
    save_resume_data,
    set_session_started,
    update_session_status,
    save_proctoring,
    mark_interview_done,
    mark_interview_started,
)
from backend.auth.auth import require_candidate_login

init_db()

if __name__ != "__portal__":
    st.set_page_config(page_title="AI Interview System", layout="wide")
st.title("AI Interview System")

# ── Candidate login gate ──────────────────────────────────────────────────────
username, _ = require_candidate_login()

PROCTOR_DIR = Path("storage/proctoring")


def voice_monitor_component(
    low_threshold: float = 0.015, consecutive_frames_limit: int = 120
):
    html_code = f"""
    <div style="background-color: #1a1c23; border-radius: 8px; padding: 12px; font-family: sans-serif; color: #ffffff; border: 1px solid #2d3139;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 14px; font-weight: 600; color: #a0aec0;">🎙️ Live Microphone Input Monitor</span>
            <div id="status-badge" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background-color: #2d3748; color: #cbd5e0;">Awaiting Mic...</div>
        </div>
        <canvas id="oscilloscope" style="width: 100%; height: 60px; background-color: #0f1115; border-radius: 6px; display: block;"></canvas>
        <div id="volume-alert" style="height: 20px; color: #fc8181; font-size: 13px; font-weight: bold; margin-top: 6px; text-align: center; transition: opacity 0.2s ease; opacity: 0;">
            ⚠️ Voice too low! Please speak a bit louder.
        </div>
    </div>
    <script>
    (async function initVoiceMonitor() {{
        const canvas = document.getElementById('oscilloscope');
        const canvasCtx = canvas.getContext('2d');
        const alertDiv = document.getElementById('volume-alert');
        const badge = document.getElementById('status-badge');
        const dpr = window.devicePixelRatio || 1;
        canvas.width = canvas.clientWidth * dpr;
        canvas.height = canvas.clientHeight * dpr;
        canvasCtx.scale(dpr, dpr);
        let audioContext, analyser, dataArray, bufferLength;
        let lowVolumeCounter = 0;
        const THRESHOLD = {low_threshold};
        const FRAME_LIMIT = {consecutive_frames_limit};
        try {{
            const stream = await navigator.mediaDevices.getUserMedia({{
                audio: {{ echoCancellation: true, noiseSuppression: true }}
            }});
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(stream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048;
            bufferLength = analyser.frequencyBinCount;
            dataArray = new Uint8Array(bufferLength);
            source.connect(analyser);
            badge.textContent = "Live Engine Active";
            badge.style.backgroundColor = "#22543d";
            badge.style.color = "#9ae6b4";
            drawOscilloscope();
        }} catch (err) {{
            badge.textContent = "Mic Blocked/Missing";
            badge.style.backgroundColor = "#742a2a";
            badge.style.color = "#fed7d7";
        }}
        function drawOscilloscope() {{
            requestAnimationFrame(drawOscilloscope);
            const width = canvas.clientWidth;
            const height = canvas.clientHeight;
            analyser.getByteTimeDomainData(dataArray);
            let totalDev = 0;
            for (let i = 0; i < bufferLength; i++) {{
                const v = (dataArray[i] / 128.0) - 1.0;
                totalDev += v * v;
            }}
            const rmsVolume = Math.sqrt(totalDev / bufferLength);
            if (rmsVolume < THRESHOLD) {{
                lowVolumeCounter++;
                if (lowVolumeCounter >= FRAME_LIMIT) alertDiv.style.opacity = "1";
            }} else {{
                lowVolumeCounter = 0;
                alertDiv.style.opacity = "0";
            }}
            canvasCtx.fillStyle = '#0f1115';
            canvasCtx.fillRect(0, 0, width, height);
            canvasCtx.strokeStyle = lowVolumeCounter >= FRAME_LIMIT ? '#e53e3e' : '#3182ce';
            canvasCtx.lineWidth = 2;
            canvasCtx.beginPath();
            const sliceWidth = width / bufferLength;
            let x = 0;
            for (let i = 0; i < bufferLength; i++) {{
                const v = dataArray[i] / 128.0;
                const y = (v * height) / 2;
                if (i === 0) canvasCtx.moveTo(x, y);
                else canvasCtx.lineTo(x, y);
                x += sliceWidth;
            }}
            canvasCtx.lineTo(width, height / 2);
            canvasCtx.stroke();
        }}
    }})();
    </script>
    """
    components.html(html_code, height=130)


def question_speaker_component(session_id: str, question_no: int, question: str):
    question_json = json.dumps(question)
    speech_key = json.dumps(f"spoken_question_{session_id}_{question_no}")
    html_code = f"""
    <div style="display:flex;align-items:center;gap:10px;font-family:sans-serif;">
        <button id="speakQuestion" type="button"
            style="border:1px solid #64748b;border-radius:7px;padding:8px 13px;
                   background:#f8fafc;color:#0f172a;font-weight:600;cursor:pointer;">
            Speaker: Replay question
        </button>
        <span id="speechStatus" style="font-size:13px;color:#64748b;"></span>
    </div>
    <script>
    (function() {{
        const question = {question_json};
        const speechKey = {speech_key};
        const button = document.getElementById("speakQuestion");
        const status = document.getElementById("speechStatus");
        let speechWindow = window;
        let storage = window.sessionStorage;

        try {{
            if (window.parent && window.parent.speechSynthesis) {{
                speechWindow = window.parent;
                storage = window.parent.sessionStorage;
            }}
        }} catch (err) {{
            speechWindow = window;
            storage = window.sessionStorage;
        }}

        function speakQuestion() {{
            if (!("speechSynthesis" in speechWindow)) {{
                status.textContent = "Text-to-speech is unavailable in this browser.";
                button.disabled = true;
                return;
            }}

            speechWindow.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(question);
            utterance.lang = "en-US";
            utterance.rate = 0.95;
            utterance.pitch = 1.0;
            utterance.onstart = () => status.textContent = "Speaking...";
            utterance.onend = () => status.textContent = "Finished";
            utterance.onerror = () => status.textContent = "Unable to play speech.";
            speechWindow.speechSynthesis.speak(utterance);
        }}

        button.addEventListener("click", speakQuestion);

        if (!storage.getItem(speechKey)) {{
            storage.setItem(speechKey, "1");
            setTimeout(speakQuestion, 250);
        }}
    }})();
    </script>
    """
    components.html(html_code, height=48)


def load_proctor_status(session_id: str) -> dict:
    path = PROCTOR_DIR / f"{session_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def persist_session(session: dict):
    session_path = Path("storage/sessions") / f"{session['session_id']}.json"
    session_path.write_text(json.dumps(session, indent=4), encoding="utf-8")


def show_post_interview_processing(session_id: str):
    status = get_post_interview_status(session_id)
    state = status.get("status", "queued")
    labels = {
        "queued": "Queued for transcription and scoring.",
        "transcribing": "Transcribing recorded answers.",
        "scoring": "Scoring transcribed answers.",
        "completed": "Automatic transcription and scoring completed.",
        "failed": "Automatic transcription/scoring failed.",
    }

    if state == "completed":
        st.success(labels[state])
        if status.get("overall_score") is not None:
            st.caption(
                f"Admin result: {status.get('overall_score')} / 10"
                f" ({status.get('band', 'Unbanded')})"
            )
    elif state == "failed":
        st.error(labels[state])
        with st.expander("Processing error"):
            st.code(status.get("error", "No error details were written."))
    else:
        st.info(labels.get(state, "Processing recorded responses."))
        st_autorefresh(interval=5000, key=f"post_interview_status_{session_id}")


# ── Session state defaults ────────────────────────────────────────────────────
DEFAULTS = {
    "interview_session": None,
    "interview_started": False,
    "question_index": 0,
    "phase": "READ",
    "phase_start": None,
    "question_recording_started": False,
    "refresh": False,
    "scoring_status": "idle",
    "scoring_results": {},
    "scoring_error": "",
    # ── DB write guards — prevent duplicate writes on reruns ──────────────────
    "db_session_saved": False,
    "db_started_set": False,
    "db_completed_saved": False,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ── Resume upload ─────────────────────────────────────────────────────────────
resume = st.file_uploader("Upload Resume", type=["pdf"])

if resume:
    try:
        if st.session_state["interview_session"] is None:
            validate_resume(resume)
            path = save_resume(resume)
            text = extract_text(path)
            cleaned = clean_resume(text)
            profile = understand_resume(cleaned)
            blueprint = build_blueprint(profile)
            questions = generate_questions(profile, blueprint)
            final_questions = validate_questions(questions)
            session = create_session(profile, final_questions, username=username)
            st.session_state["interview_session"] = session

            # ── DB: save session + resume once on creation ────────────────────
            save_session(
                session["session_id"],
                username,
                session["status"],
                session["expires_at"],
            )
            save_resume_data(session["session_id"], username, profile)
            st.session_state["db_session_saved"] = True

        session = st.session_state["interview_session"]
        profile = session["candidate"]
        questions = session["questions"]

        st.success("Resume Processed")

        with st.expander("Candidate Profile"):
            st.json(profile)

        st.subheader("Interview Session")
        col1, col2, col3 = st.columns(3)
        col1.metric("Status", session["status"])
        col2.metric("Questions", len(questions))
        col3.metric("Expires", session["expires_at"][:10])

        st.divider()

        # ── Pre-interview ─────────────────────────────────────────────────────
        if not st.session_state["interview_started"]:
            if st.button("Start Interview"):
                session = initialize_interview(session)
                st.session_state["interview_session"] = session
                st.session_state["interview_started"] = True
                st.session_state["phase"] = "READ"
                st.session_state["phase_start"] = time.time()

                # ── DB: set started_at exactly once ───────────────────────────
                if not st.session_state["db_started_set"]:
                    set_session_started(session["session_id"])
                    mark_interview_started(username)
                    st.session_state["db_started_set"] = True

                st.rerun()

        # ── Active interview ──────────────────────────────────────────────────
        else:
            index = st.session_state["question_index"]
            question = get_question(session, index)
            proctor_status = load_proctor_status(session["session_id"])

            if proctor_status.get("locked"):
                session["status"] = "TERMINATED"
                session["terminated_at"] = datetime.now().isoformat()
                session["termination_reason"] = proctor_status.get(
                    "lock_reason", "Interview terminated by proctoring rules."
                )
                session["proctoring"] = proctor_status
                persist_session(session)
                update_session_status(session["session_id"], "TERMINATED")
                save_proctoring(session["session_id"], proctor_status)
                mark_interview_done(username)
                start_post_interview_processing(session["session_id"])
                st.error("Interview terminated.")
                st.warning(session["termination_reason"])
                st.info(
                    "Recorded responses are being processed. Evaluation results "
                    "are available only to the administrator."
                )
                show_post_interview_processing(session["session_id"])
                st.stop()

            if question:
                st.progress((index + 1) / len(questions))
                st.subheader(f"Question {index + 1}")
                st.info(question)

                phase = st.session_state["phase"]
                if phase == "READ":
                    question_speaker_component(
                        session["session_id"],
                        index + 1,
                        question,
                    )

                camera_placeholder = st.empty()
                with camera_placeholder:
                    media_recorder_component(
                        session["session_id"],
                        index + 1,
                        phase == "ANSWER",
                        max_seconds=90 if phase == "ANSWER" else None,
                    )

                elapsed = int(time.time() - st.session_state["phase_start"])
                READ_TIME = 30
                ANSWER_TIME = 90

                if phase == "READ":
                    remaining = max(0, READ_TIME - elapsed)
                    st.warning(f"Read Time: {remaining}s")
                    st.info("Read carefully")
                    if remaining > 0:
                        st_autorefresh(interval=1000, key=f"read_timer_tick_q{index}")
                    if remaining <= 0:
                        st.session_state["phase"] = "ANSWER"
                        st.session_state["phase_start"] = time.time()
                        st.session_state["refresh"] = True
                        st.rerun()

                elif phase == "ANSWER":
                    st.success("Recording Active")
                    st.info("Live answer countdown is shown below the camera.")
                    st.caption(
                        "Use the recorder's Stop recording button first if you finish early."
                    )
                    voice_monitor_component(
                        low_threshold=0.042, consecutive_frames_limit=60
                    )
                    nxt = st.button("NEXT")
                    if nxt:
                        st.session_state["question_index"] += 1
                        st.session_state["phase"] = "READ"
                        st.session_state["phase_start"] = time.time()
                        st.rerun()

            # ── Interview finished ────────────────────────────────────────────
            else:
                session = st.session_state["interview_session"]

                # ── DB: save completion exactly once ──────────────────────────
                if not st.session_state["db_completed_saved"]:
                    completed_at = datetime.now().isoformat()
                    session["status"] = "COMPLETED"
                    session["completed_at"] = completed_at
                    session["proctoring"] = load_proctor_status(session["session_id"])
                    persist_session(session)

                    update_session_status(
                        session["session_id"], "COMPLETED", completed_at
                    )
                    save_proctoring(
                        session["session_id"], session.get("proctoring", {})
                    )
                    mark_interview_done(username)
                    st.session_state["interview_session"] = session
                    st.session_state["db_completed_saved"] = True

                start_post_interview_processing(session["session_id"])

                st.success("Interview completed. Thank you.")
                st.info(
                    "Your responses are being processed. Evaluation results are "
                    "available only to the administrator."
                )
                show_post_interview_processing(session["session_id"])

    except Exception as exc:
        st.error(str(exc))


# streamlit run streamlit_app.py --server.port 8501
