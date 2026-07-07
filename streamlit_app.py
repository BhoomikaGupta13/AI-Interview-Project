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

# ── UI theme (new) ────────────────────────────────────────────────────────────
from backend.ui.theme import (
    apply_theme,
    render_theme_toggle,
    render_sidebar_brand,
    render_hero,
    section_title,
    card_open,
    card_close,
    chip,
    _palette,
)

init_db()

if __name__ != "__portal__":
    st.set_page_config(
        page_title="AI Interview System",
        layout="wide",
        page_icon="🎙️",
        initial_sidebar_state="expanded",
    )

# ── Theme + top-bar toggle ────────────────────────────────────────────────────
apply_theme("candidate")
render_sidebar_brand("candidate")
render_theme_toggle(key="theme_toggle_candidate")

# ── Candidate login gate ──────────────────────────────────────────────────────
username, _ = require_candidate_login()

# ── Hero header ───────────────────────────────────────────────────────────────
render_hero(
    eyebrow="Candidate Session",
    title="AI Interview System",
    subtitle=(
        "A calm, distraction-free interview experience. Upload your résumé, take a moment "
        "to breathe, and we will guide you through each question with a live recorder."
    ),
    right_badge=f"Signed in as {username}",
    right_icon="fa-user-astronaut",
)

PROCTOR_DIR = Path("storage/proctoring")


# ─────────────────────────────────────────────────────────────────────────────
# Voice monitor (themed to match app palette)
# ─────────────────────────────────────────────────────────────────────────────
def voice_monitor_component(
    low_threshold: float = 0.015, consecutive_frames_limit: int = 120
):
    p = _palette()
    html_code = f"""
    <div style="background:{p['surface']}; border-radius:14px; padding:14px 16px;
                font-family: 'Manrope', sans-serif; color:{p['ink']};
                border:1px solid {p['border']}; box-shadow: {p['shadow']};">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <span style="font-size:13px; font-weight:700; color:{p['ink_soft']};
                         letter-spacing:.02em; display:inline-flex; align-items:center; gap:.5rem;">
                <span style="width:8px; height:8px; border-radius:50%;
                             background:{p['accent']}; box-shadow: 0 0 0 4px rgba(15,118,110,.15);
                             animation: pulse 1.4s infinite ease-in-out;"></span>
                Live Microphone Input Monitor
            </span>
            <div id="status-badge" style="font-size:11px; padding:4px 10px; border-radius:999px;
                                          background:{p['chip_bg']}; color:{p['chip_ink']};
                                          font-weight:700; letter-spacing:.04em;">Awaiting Mic...</div>
        </div>
        <canvas id="oscilloscope" style="width:100%; height:60px; background:{p['bg_soft']};
                                         border:1px solid {p['border']};
                                         border-radius:10px; display:block;"></canvas>
        <div id="volume-alert" style="height:20px; color:{p['danger']}; font-size:13px;
                                      font-weight:700; margin-top:8px; text-align:center;
                                      transition:opacity .2s ease; opacity:0;">
            ⚠ Voice too low — please speak a little louder.
        </div>
        <style>
          @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.35}} }}
        </style>
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
            drawOscilloscope();
        }} catch (err) {{
            badge.textContent = "Mic Blocked / Missing";
            badge.style.background = "rgba(185,28,28,.10)";
            badge.style.color = "{p['danger']}";
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
            canvasCtx.fillStyle = '{p['bg_soft']}';
            canvasCtx.fillRect(0, 0, width, height);
            canvasCtx.strokeStyle = lowVolumeCounter >= FRAME_LIMIT ? '{p['danger']}' : '{p['accent']}';
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
    components.html(html_code, height=140)


def question_speaker_component(session_id: str, question_no: int, question: str):
    p = _palette()
    question_json = json.dumps(question)
    speech_key = json.dumps(f"spoken_question_{session_id}_{question_no}")
    html_code = f"""
    <div style="display:flex; align-items:center; gap:12px; font-family:'Manrope',sans-serif;">
        <button id="speakQuestion" type="button"
            style="border:1px solid {p['border']}; border-radius:12px; padding:9px 15px;
                   background:{p['surface_2']}; color:{p['ink']}; font-weight:600;
                   cursor:pointer; display:inline-flex; align-items:center; gap:.5rem;
                   box-shadow: 0 1px 2px rgba(11,37,69,.04); transition: all .15s ease;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                 stroke="{p['accent']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
              <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
            </svg>
            Replay question
        </button>
        <span id="speechStatus" style="font-size:13px; color:{p['muted']};"></span>
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
    components.html(html_code, height=52)


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
    "db_session_saved": False,
    "db_started_set": False,
    "db_completed_saved": False,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ── Resume upload ─────────────────────────────────────────────────────────────
section_title("Upload your résumé to begin", icon="fa-file-arrow-up")
st.caption(
    "PDF only • We use it to tailor the interview to your background. Nothing is shared publicly."
)
resume = st.file_uploader(" ", type=["pdf"], label_visibility="collapsed")

if resume:
    try:
        if st.session_state["interview_session"] is None:
            with st.spinner("Analysing résumé and crafting your personalised interview…"):
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

        st.markdown(
            f"""<div style="margin:.5rem 0 1rem 0;">{chip("Résumé processed", "")}
                {chip(f"{len(questions)} questions ready", "muted")}
                {chip(f"Session {session['session_id'][:8]}", "muted")}</div>""",
            unsafe_allow_html=True,
        )

        with st.expander("View extracted candidate profile"):
            st.json(profile)

        section_title("Interview session overview", icon="fa-clipboard-check")
        col1, col2, col3 = st.columns(3)
        col1.metric("Status", session["status"])
        col2.metric("Questions", len(questions))
        col3.metric("Expires", session["expires_at"][:10])

        st.divider()

        # ── Pre-interview ─────────────────────────────────────────────────────
        if not st.session_state["interview_started"]:
            card_open("Ready when you are", icon="fa-play")
            st.markdown(
                "<p style='color:var(--ink-soft); margin:.2rem 0 1rem 0;'>"
                "Once you start, each question has a short reading window followed by a live recording phase. "
                "Find a quiet spot, check your camera and microphone, and take a deep breath."
                "</p>",
                unsafe_allow_html=True,
            )
            if st.button("Start interview →", type="primary"):
                session = initialize_interview(session)
                st.session_state["interview_session"] = session
                st.session_state["interview_started"] = True
                st.session_state["phase"] = "READ"
                st.session_state["phase_start"] = time.time()

                if not st.session_state["db_started_set"]:
                    set_session_started(session["session_id"])
                    mark_interview_started(username)
                    st.session_state["db_started_set"] = True

                st.rerun()
            card_close()

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
                progress_ratio = (index + 1) / len(questions)
                st.markdown(
                    f"""<div style="display:flex; justify-content:space-between;
                                   align-items:center; margin-bottom:.4rem;">
                        <span style="color:var(--ink-soft); font-weight:600;">
                            Question {index + 1} of {len(questions)}
                        </span>
                        <span class="ai-chip">{int(progress_ratio * 100)}% complete</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
                st.progress(progress_ratio)

                card_open(f"Question {index + 1}", icon="fa-comment-dots")
                st.markdown(
                    f"<p style='font-size:1.05rem; line-height:1.55; color:var(--ink); margin:.2rem 0 .8rem 0;'>{question}</p>",
                    unsafe_allow_html=True,
                )

                phase = st.session_state["phase"]
                if phase == "READ":
                    question_speaker_component(
                        session["session_id"],
                        index + 1,
                        question,
                    )
                card_close()

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
                    st.markdown(
                        f"""<div class="ai-card" style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <div style="font-family:'Fraunces',serif; font-size:1.2rem; color:var(--ink);">
                                    Read time — <b>{remaining}s</b>
                                </div>
                                <div style="color:var(--ink-soft); font-size:.9rem;">
                                    Take a breath and read the question carefully.
                                </div>
                            </div>
                            {chip("Reading phase", "muted")}
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    if remaining > 0:
                        st_autorefresh(interval=1000, key=f"read_timer_tick_q{index}")
                    if remaining <= 0:
                        st.session_state["phase"] = "ANSWER"
                        st.session_state["phase_start"] = time.time()
                        st.session_state["refresh"] = True
                        st.rerun()

                elif phase == "ANSWER":
                    st.markdown(
                        f"""<div class="ai-card" style="border-color: color-mix(in oklab, var(--accent) 40%, var(--border));">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div style="display:flex; align-items:center; gap:.7rem;">
                                    <span style="width:10px; height:10px; border-radius:50%; background:{_palette()['danger']};
                                                 box-shadow: 0 0 0 6px rgba(185,28,28,.15); animation: pulse 1.2s infinite;"></span>
                                    <div>
                                        <div style="font-family:'Fraunces',serif; font-size:1.15rem;">Recording active</div>
                                        <div style="color:var(--ink-soft); font-size:.88rem;">
                                            Live countdown is shown under the camera. Use the recorder's Stop button if you finish early.
                                        </div>
                                    </div>
                                </div>
                                {chip("Answering", "")}
                            </div>
                            <style>@keyframes pulse {{0%,100%{{opacity:1}} 50%{{opacity:.4}}}}</style>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    voice_monitor_component(
                        low_threshold=0.042, consecutive_frames_limit=60
                    )
                    st.markdown("<div style='height:.6rem;'></div>", unsafe_allow_html=True)
                    nxt = st.button("Next question →", type="primary", use_container_width=False)
                    if nxt:
                        st.session_state["question_index"] += 1
                        st.session_state["phase"] = "READ"
                        st.session_state["phase_start"] = time.time()
                        st.rerun()

            # ── Interview finished ────────────────────────────────────────────
            else:
                session = st.session_state["interview_session"]

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

                card_open("Interview completed", icon="fa-circle-check")
                st.markdown(
                    "<p style='color:var(--ink-soft);'>"
                    "Thank you for your time. Your responses are being transcribed and scored. "
                    "Evaluation results are available only to the administrator."
                    "</p>",
                    unsafe_allow_html=True,
                )
                card_close()
                show_post_interview_processing(session["session_id"])

    except Exception as exc:
        st.error(str(exc))


# streamlit run streamlit_app.py --server.port 8501
