# admin_app.py
# Run with: streamlit run admin_app.py --server.port 8502

import json
import streamlit as st
import pandas as pd
from backend.auth.auth import require_admin_login
from backend.db.queries import (
    get_all_candidates,
    create_candidate,
    delete_candidate,
    get_score_by_session,
)
from backend.db.database import init_db, get_conn

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
)

init_db()


def _is_valid_email(email: str) -> bool:
    """
    Quick client-side syntax pre-check using the same library as the mailer,
    so the error surfaces immediately without a network call.
    """
    from email_validator import validate_email, EmailNotValidError

    try:
        validate_email(email.strip(), check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


if __name__ != "__portal__":
    st.set_page_config(
        page_title="Admin — AI Interview System",
        layout="wide",
        page_icon="🛠️",
        initial_sidebar_state="expanded",
    )

# ── Theme + top-bar toggle ────────────────────────────────────────────────────
apply_theme("admin")
render_sidebar_brand("admin")
render_theme_toggle(key="theme_toggle_admin")

# ── Auth ──────────────────────────────────────────────────────────────────────
require_admin_login()

# ── Sidebar admin identity + logout ──────────────────────────────────────────
st.sidebar.markdown("### Session")
st.sidebar.markdown(
    """<div class="ai-chip" style="width:100%; justify-content:center; padding:.5rem;">
        <i class="fa-solid fa-user-shield" style="margin-right:.4rem;"></i>Logged in as admin</div>""",
    unsafe_allow_html=True,
)
st.sidebar.write("")
if st.sidebar.button("Log out", use_container_width=True):
    st.session_state["admin_logged_in"] = False
    st.rerun()

# ── Hero ──────────────────────────────────────────────────────────────────────
render_hero(
    eyebrow="Admin Console",
    title="Interview Operations",
    subtitle=(
        "Review candidate performance, inspect proctoring signals, and manage credentials — "
        "all in one calm, focused workspace."
    ),
    right_badge="Access: Administrator",
    right_icon="fa-shield-halved",
)

tab1, tab2 = st.tabs(["📋 Candidates", "➕ Create candidate"])

# ─────────────────────────────────────────────────────────────────────────────
# Tab 1: All candidates
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    section_title("All candidates", icon="fa-users")
    rows = get_all_candidates()

    if not rows:
        st.info("No candidates yet. Create the first one from the “Create candidate” tab.")
    else:
        # Strip out raw full_report to prevent leakage
        cleaned_rows = []
        for r in rows:
            rc = r.copy()
            if "full_report" in rc:
                del rc["full_report"]
            cleaned_rows.append(rc)

        # Roster header
        card_open(icon="fa-table-list")
        header_cols = st.columns([2, 3, 3, 2, 2, 1])
        for col, label in zip(header_cols, ["Username", "Name", "Email", "Interview", "Score", ""]):
            col.markdown(
                f"<div style='font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; "
                f"color:var(--muted); font-weight:800;'>{label}</div>",
                unsafe_allow_html=True,
            )

        for r in cleaned_rows:
            username = r["username"]
            full_name = r.get("full_name") or "—"
            email = r.get("email") or "—"
            status = r.get("interview_status") or "NOT_STARTED"

            if r.get("interview_done"):
                status_chip = chip("Completed", "")
            elif status == "IN_PROGRESS":
                status_chip = chip("In progress", "warn")
            elif status == "TERMINATED":
                status_chip = chip("Terminated", "danger")
            else:
                status_chip = chip("Not started", "muted")

            if r.get("overall_score") is not None:
                score_val = f"{r['overall_score']:.2f} / 10"
                band = r.get("band")
                band_kind = {
                    "Strong": "",
                    "Good": "",
                    "Average": "warn",
                    "Weak": "danger",
                }.get(band, "muted")
                score_html = f"<b style='font-family:Fraunces,serif;'>{score_val}</b>"
                if band:
                    score_html += " " + chip(band, band_kind)
            else:
                score_html = "<span style='color:var(--muted);'>Not scored</span>"

            pending_key = f"confirm_delete_{username}"

            row_cols = st.columns([2, 3, 3, 2, 2, 1])
            row_cols[0].markdown(f"**{username}**")
            row_cols[1].write(full_name)
            row_cols[2].write(email)
            row_cols[3].markdown(status_chip, unsafe_allow_html=True)
            row_cols[4].markdown(score_html, unsafe_allow_html=True)
            with row_cols[5]:
                if st.button("🗑", key=f"delete_{username}", help="Delete candidate"):
                    st.session_state[pending_key] = True

            if st.session_state.get(pending_key):
                st.warning(
                    f"Confirm deletion of candidate credentials for **{username}**. "
                    "This cannot be undone."
                )
                confirm_col, cancel_col, _ = st.columns([1, 1, 5])
                if confirm_col.button("Confirm", key=f"confirm_{username}", type="primary"):
                    deleted = delete_candidate(username)
                    st.session_state.pop(pending_key, None)
                    if deleted.get("candidates"):
                        st.success(f"Deleted candidate '{username}'.")
                    else:
                        st.warning(f"Candidate '{username}' was not found.")
                    st.rerun()
                if cancel_col.button("Cancel", key=f"cancel_{username}"):
                    st.session_state.pop(pending_key, None)
                    st.rerun()
        card_close()

        st.divider()
        section_title("Per-candidate detail", icon="fa-magnifying-glass-chart")
        selected = st.selectbox(
            "Select candidate to view full report",
            options=[r["username"] for r in cleaned_rows],
        )

        if selected:
            matching = [r for r in cleaned_rows if r["username"] == selected]
            if matching and matching[0].get("overall_score") is not None:

                # Fetch full_report from the scores table on demand
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT session_id, full_report 
                            FROM scores 
                            WHERE username=%s 
                            ORDER BY created_at DESC LIMIT 1
                            """,
                            (selected,),
                        )
                        db_row = cur.fetchone()

                if db_row:
                    session_id, report = db_row
                    if isinstance(report, str):
                        report = json.loads(report)

                    band = report.get("band", "Weak")
                    band_kind = {
                        "Strong": "",
                        "Good": "",
                        "Average": "warn",
                        "Weak": "danger",
                    }.get(band, "muted")

                    # 1. Performance summary card
                    card_open(icon="fa-chart-line", title=f"Performance summary — {selected}")
                    st.markdown(
                        f"""<div style="display:flex; align-items:flex-end; justify-content:space-between; flex-wrap:wrap; gap:1rem;">
                            <div>
                                <div style="font-family:'Fraunces',serif; font-size:2.6rem; font-weight:600; color:var(--ink); line-height:1;">
                                    {report.get('overall_score', 0.0)}<span style="color:var(--muted); font-size:1.3rem;"> / 10</span>
                                </div>
                                <div style="margin-top:.5rem;">{chip(band, band_kind)}</div>
                            </div>
                            <div style="text-align:right;">
                                <div style="font-size:.75rem; color:var(--muted); letter-spacing:.12em; text-transform:uppercase; font-weight:700;">Session</div>
                                <code style="background:var(--bg-soft); padding:.3rem .55rem; border-radius:8px; font-size:.82rem;">{session_id}</code>
                            </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    card_close()

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total questions", report.get("total_questions", 0))
                    m2.metric("Successfully scored", report.get("scored", 0))
                    m3.metric("Candidate band", band)

                    # 2. Proctoring
                    section_title("Anti-cheating & proctoring", icon="fa-shield-halved")

                    with get_conn() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT fullscreen_warnings, tab_warnings, face_warnings, phone_warnings, locked, lock_reason
                                FROM proctoring_flags 
                                WHERE session_id = %s
                                """,
                                (session_id,),
                            )
                            proctor_row = cur.fetchone()

                    if proctor_row:
                        proctor_data = {
                            "fullscreen_warnings": proctor_row[0],
                            "tab_warnings": proctor_row[1],
                            "face_warnings": proctor_row[2],
                            "phone_warnings": proctor_row[3],
                            "locked": proctor_row[4],
                            "lock_reason": proctor_row[5],
                        }
                    else:
                        proctor_data = {
                            "fullscreen_warnings": 0,
                            "tab_warnings": 0,
                            "face_warnings": 0,
                            "phone_warnings": 0,
                            "locked": False,
                            "lock_reason": "",
                        }

                    p1, p2, p3, p4 = st.columns(4)
                    p1.metric(
                        label="Fullscreen breaks",
                        value=f"{proctor_data.get('fullscreen_warnings', 0)} / 2",
                    )
                    p2.metric(
                        label="Tab switches",
                        value=f"{proctor_data.get('tab_warnings', 0)} / 3",
                    )
                    p3.metric(
                        label="Facial anomalies",
                        value=f"{proctor_data.get('face_warnings', 0)} / 3",
                    )
                    p4.metric(
                        label="Phone detections",
                        value=f"{proctor_data.get('phone_warnings', 0)} / 2",
                        delta=(
                            "Violation logged"
                            if proctor_data.get("phone_warnings", 0) > 0
                            else None
                        ),
                        delta_color="inverse",
                    )

                    if proctor_data.get("locked"):
                        st.error(
                            f"🚨 **Session terminated / locked:** "
                            f"{proctor_data.get('lock_reason', 'Security breach threshold reached.')}"
                        )
                    else:
                        st.success("✅ Session context is clear. No terminal lock thresholds breached.")

                    # 3. Per-Question Score Matrix
                    section_title("Per-question score matrix", icon="fa-table-cells")

                    matrix_data = []
                    for r in report.get("results", []):
                        raw_sim = r.get("similarity", 0.0)
                        raw_llm = r.get("llm_score", 0.0)
                        raw_depth = r.get("depth_score", 0.0)
                        answer_words = len(str(r.get("answer", "")).split())

                        sim_score = raw_sim if raw_sim > 1.0 else raw_sim * 10
                        llm_score = raw_llm if raw_llm > 1.0 else raw_llm * 10
                        depth_score = raw_depth if raw_depth > 1.0 else raw_depth * 10
                        if answer_words < 4 and llm_score == 0 and depth_score == 0:
                            sim_score = 0.0

                        matrix_data.append(
                            {
                                "Q#": r.get("question_no"),
                                "Category": str(r.get("question_type", "general")).upper(),
                                "Final Score": f"{r.get('score', 0.0)} / 10",
                                "Band": r.get("band", "Weak"),
                                "Similarity Overlap": f"{sim_score:.2f} / 10",
                                "LLM Grammar & Logic": f"{llm_score:.2f} / 10",
                                "Senior Judge Depth": f"{depth_score:.2f} / 10",
                            }
                        )

                    st.dataframe(
                        pd.DataFrame(matrix_data),
                        use_container_width=True,
                        hide_index=True,
                    )

                    # 4. Export
                    section_title("Export performance data", icon="fa-download")
                    report_string = json.dumps(report, indent=4)
                    st.download_button(
                        label="📄 Download complete technical evaluation (JSON)",
                        data=report_string,
                        file_name=f"Evaluation_Report_{selected}_{session_id}.json",
                        mime="application/json",
                        use_container_width=True,
                    )

                    st.divider()

                    # 5. Contextual answers & critique
                    section_title("Contextual answer & critique logs", icon="fa-list-check")
                    for r in report.get("results", []):
                        q_no = r["question_no"]
                        score = r.get("score", 0)
                        band = r.get("band", "")
                        icon = "✅" if r.get("status") == "success" else "❌"

                        with st.expander(
                            f"{icon} Question {q_no} — Scored {score} / 10 ({band})"
                        ):
                            st.markdown(
                                "<div style='color:var(--muted); font-size:.72rem; "
                                "letter-spacing:.12em; text-transform:uppercase; font-weight:800;'>Prompt</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(f"*{r['question']}*")

                            st.markdown(
                                "<div style='color:var(--muted); font-size:.72rem; margin-top:.6rem;"
                                "letter-spacing:.12em; text-transform:uppercase; font-weight:800;'>Candidate answer</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(f'"{r.get("answer","")}"')

                            st.divider()

                            if r.get("feedback"):
                                st.markdown(f"**📝 Core evaluator feedback:** {r['feedback']}")
                            if r.get("strengths"):
                                st.markdown("**✅ Evaluated strengths:**")
                                for s in r["strengths"]:
                                    st.markdown(f"- {s}")
                            if r.get("improvements"):
                                st.markdown("**⚠️ Areas for improvement:**")
                                for imp in r["improvements"]:
                                    st.markdown(f"- {imp}")
                            if r.get("depth_feedback"):
                                st.markdown(f"**🔍 Senior judge depth critique:** {r['depth_feedback']}")
            else:
                st.info("No scores or evaluated session data found for this candidate.")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2: Create candidate
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    section_title("Create candidate credentials", icon="fa-user-plus")
    card_open()
    st.markdown(
        "<p style='color:var(--ink-soft); margin:0 0 1rem 0;'>"
        "New candidates will receive a welcome email with their login credentials before their record is committed."
        "</p>",
        unsafe_allow_html=True,
    )

    with st.form("create_candidate_form"):
        c1, c2 = st.columns(2)
        with c1:
            username_input = st.text_input("Username (login ID)", placeholder="jane.doe")
            full_name_input = st.text_input("Full name", placeholder="Jane Doe")
        with c2:
            password_input = st.text_input("Password", type="password", placeholder="Set a strong password")
            email_input = st.text_input("Email", placeholder="jane@example.com")
        submitted = st.form_submit_button("Create candidate", type="primary")
    card_close()

    if submitted:
        if not username_input or not password_input or not email_input:
            st.error("Username, password, and destination email address fields are required.")
        elif not _is_valid_email(email_input):
            st.error(
                "⚠️ Invalid email address format. Please enter a valid address (e.g. name@domain.com)."
            )
        else:
            with st.spinner("📧 Verifying deliverability and coordinating SMTP connection…"):
                from backend.utils.mailer import send_welcome_email

                mail_sent, server_message = send_welcome_email(
                    candidate_email=email_input,
                    full_name=full_name_input,
                    username=username_input,
                    password_plain=password_input,
                )

            if mail_sent:
                ok = create_candidate(
                    username_input,
                    password_input,
                    full_name_input,
                    email_input,
                    "admin",
                )

                if ok:
                    st.success(f"📩 {server_message}")
                    st.success(
                        f"Candidate profile **{username_input}** committed successfully to PostgreSQL."
                    )
                    st.code(f"Username: {username_input}\nPassword: {password_input}")
                else:
                    st.warning(
                        f"Email sent, but username '{username_input}' already exists in candidates database."
                    )
            else:
                st.error(f"❌ **Registration denied:** {server_message}")
