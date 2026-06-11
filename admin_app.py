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

init_db()


def _is_valid_email(email: str) -> bool:
    """
    Quick client-side syntax pre-check using the same library as the mailer,
    so the error surfaces immediately without a network call.
    The mailer will then also run a live DNS/MX check before any SMTP attempt.
    """
    from email_validator import validate_email, EmailNotValidError

    try:
        validate_email(email.strip(), check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


if __name__ != "__portal__":
    st.set_page_config(page_title="Admin — AI Interview System", layout="wide")
st.title("Admin panel")

require_admin_login()

st.sidebar.success(f"Logged in as admin")
if st.sidebar.button("Logout"):
    st.session_state["admin_logged_in"] = False
    st.rerun()

tab1, tab2 = st.tabs(["Candidates", "Create candidate"])

# ── Tab 1: All candidates ─────────────────────────────────────────────────────
with tab1:
    st.subheader("All candidates")
    rows = get_all_candidates()

    if not rows:
        st.info("No candidates yet.")
    else:
        # ABSOLUTE FIX: Strip out the raw full_report string immediately so it CANNOT leak onto the screen
        cleaned_rows = []
        for r in rows:
            rc = r.copy()
            if "full_report" in rc:
                del rc["full_report"]  # Delete the raw text dump completely
            cleaned_rows.append(rc)

        header_cols = st.columns([2, 3, 3, 2, 2, 1])
        header_cols[0].markdown("**Username**")
        header_cols[1].markdown("**Name**")
        header_cols[2].markdown("**Email**")
        header_cols[3].markdown("**Interview**")
        header_cols[4].markdown("**Score**")
        header_cols[5].markdown("**Delete**")

        for r in cleaned_rows:
            username = r["username"]
            full_name = r.get("full_name") or "-"
            email = r.get("email") or "-"
            status = r.get("interview_status") or "NOT_STARTED"
            done = (
                "Completed"
                if r.get("interview_done")
                else status.replace("_", " ").title()
            )
            score = (
                f"{r['overall_score']:.2f} / 10"
                if r.get("overall_score") is not None
                else "Not Scored"
            )
            if r.get("band"):
                score = f"{score} ({r['band']})"
            pending_key = f"confirm_delete_{username}"

            row_cols = st.columns([2, 3, 3, 2, 2, 1])
            row_cols[0].markdown(f"**{username}**")
            row_cols[1].write(full_name)
            row_cols[2].write(email)
            row_cols[3].write(done)
            row_cols[4].write(score)
            with row_cols[5]:
                if st.button("Delete", key=f"delete_{username}"):
                    st.session_state[pending_key] = True

            if st.session_state.get(pending_key):
                st.warning(
                    f"Confirm deletion of candidate credentials for '{username}'. "
                    "This cannot be undone."
                )
                confirm_col, cancel_col = st.columns([1, 5])
                if confirm_col.button("Confirm", key=f"confirm_{username}"):
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

        st.divider()
        st.subheader("Per-candidate detail")
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

                    # Parse string to dict safely if it's stored as text
                    if isinstance(report, str):
                        report = json.loads(report)

                    # 1. Top-Level Metrics Header
                    st.markdown(f"### 📊 Performance Summary for `{selected}`")
                    st.markdown(f"**Session Identifier:** `{session_id}`")

                    st.markdown(
                        f"#### **Overall Score:** {report.get('overall_score', 0.0)} / 10 — "
                        f"**:{'green' if report.get('band')=='Strong' else 'blue' if report.get('band')=='Good' else 'orange' if report.get('band')=='Average' else 'red'}[{report.get('band', 'Weak')}]**"
                    )

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Questions", report.get("total_questions", 0))
                    m2.metric("Successfully Scored", report.get("scored", 0))
                    m3.metric("Candidate Band", report.get("band", "Weak"))

                    # ── REAL-TIME PROCTORING MONITORING BLOCK ──
                    st.divider()
                    st.subheader("🛡️ Anti-Cheating & Proctoring Report")

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
                        label="Fullscreen Breaks",
                        value=f"{proctor_data.get('fullscreen_warnings', 0)} / 2",
                    )
                    p2.metric(
                        label="Tab Switches",
                        value=f"{proctor_data.get('tab_warnings', 0)} / 3",
                    )
                    p3.metric(
                        label="Facial Anomalies",
                        value=f"{proctor_data.get('face_warnings', 0)} / 3",
                    )
                    p4.metric(
                        label="Device Detections (Phones)",
                        value=f"{proctor_data.get('phone_warnings', 0)} / 2",
                        delta=(
                            "Violation Logged"
                            if proctor_data.get("phone_warnings", 0) > 0
                            else None
                        ),
                        delta_color="inverse",
                    )

                    if proctor_data.get("locked"):
                        st.error(
                            f"🚨 **Session Terminated/Locked Out:** {proctor_data.get('lock_reason', 'Security breach threshold reached.')}"
                        )
                    else:
                        st.success(
                            "✅ Session context is clear. No terminal lock thresholds breached."
                        )

                    # 2. Per-Question Score Matrix Table Breakdown
                    st.divider()
                    st.subheader("📋 Per-Question Score Matrix")

                    matrix_data = []
                    for r in report.get("results", []):
                        raw_sim = r.get("similarity", 0.0)
                        raw_llm = r.get("llm_score", 0.0)
                        raw_depth = r.get("depth_score", 0.0)

                        sim_score = raw_sim if raw_sim > 1.0 else raw_sim * 10
                        llm_score = raw_llm if raw_llm > 1.0 else raw_llm * 10
                        depth_score = raw_depth if raw_depth > 1.0 else raw_depth * 10

                        matrix_data.append(
                            {
                                "Q#": r.get("question_no"),
                                "Category": str(
                                    r.get("question_type", "general")
                                ).upper(),
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

                    # 3. Clean, Non-intrusive Report Download Link Button
                    st.subheader("📥 Export Performance Data")
                    report_string = json.dumps(report, indent=4)

                    st.download_button(
                        label="📄 Download Complete Technical Evaluation (JSON)",
                        data=report_string,
                        file_name=f"Evaluation_Report_{selected}_{session_id}.json",
                        mime="application/json",
                        use_container_width=True,
                    )

                    st.divider()

                    # 4. Deep Expandable Feedback Breakdown
                    st.subheader("🔍 Contextual Answer & Critique Logs")
                    for r in report.get("results", []):
                        q_no = r["question_no"]
                        score = r.get("score", 0)
                        band = r.get("band", "")
                        icon = "✅" if r.get("status") == "success" else "❌"

                        with st.expander(
                            f"{icon} Question {q_no} — Finished with {score} / 10 ({band})"
                        ):
                            st.markdown(f"**Question Prompt:** *{r['question']}*")
                            st.markdown(
                                f"**Clean Answer Text:** \"{r.get('answer','')}\""
                            )
                            st.divider()

                            if r.get("feedback"):
                                st.markdown(
                                    f"**📝 Core Evaluator Feedback:** {r['feedback']}"
                                )
                            if r.get("strengths"):
                                st.markdown("**✅ Evaluated Strengths:**")
                                for s in r["strengths"]:
                                    st.markdown(f"- {s}")
                            if r.get("improvements"):
                                st.markdown("**⚠️ Areas for Improvement:**")
                                for imp in r["improvements"]:
                                    st.markdown(f"- {imp}")
                            if r.get("depth_feedback"):
                                st.markdown(
                                    f"**🔍 Senior Judge Depth Critique:** {r['depth_feedback']}"
                                )
            else:
                st.info("No scores or evaluated session data found for this candidate.")

# ── Tab 2: Create candidate ───────────────────────────────────────────────────
# Replace ONLY the with tab2: block inside admin_app.py

with tab2:
    st.subheader("Create candidate credentials")
    with st.form("create_candidate_form"):
        username_input = st.text_input("Username (login ID)")
        password_input = st.text_input("Password", type="password")
        full_name_input = st.text_input("Full name")
        email_input = st.text_input("Email")
        submitted = st.form_submit_button("Create")

    if submitted:
        if not username_input or not password_input or not email_input:
            st.error(
                "Username, password, and destination email address fields are required."
            )
        elif not _is_valid_email(email_input):
            st.error(
                "⚠️ Invalid email address format. "
                "Please enter a valid address (e.g. name@domain.com)."
            )
        else:
            # ── UPGRADED ORDER OF OPERATIONS (Email verification triggers FIRST) ──
            with st.spinner(
                "📧 Verifying deliverability and coordinating SMTP connection..."
            ):
                from backend.utils.mailer import send_welcome_email

                # Call our updated mailer function that returns a success flag and message payload
                mail_sent, server_message = send_welcome_email(
                    candidate_email=email_input,
                    full_name=full_name_input,
                    username=username_input,
                    password_plain=password_input,
                )

            if mail_sent:
                # ONLY if the email domain is verified and delivered, write to PostgreSQL
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
                        f"Email sent, but Username '{username_input}' already exists in candidates base database."
                    )
            else:
                # If mail_sent is False, prevent database insertion entirely and show why
                st.error(f"❌ **Registration Denied:** {server_message}")
