# admin_app.py
# Run with:  streamlit run admin_app.py --server.port 8502

import json
import streamlit as st
import pandas as pd
from backend.auth.auth import require_admin_login
from backend.db.queries import (
    get_all_candidates,
    create_candidate,
    get_score_by_session,
)
from backend.db.database import init_db, get_conn

init_db()

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

        df = pd.DataFrame(cleaned_rows)

        # Clean up overall score visualization in the master list dataframe view
        if "overall_score" in df.columns:
            df["overall_score"] = df["overall_score"].apply(
                lambda x: f"{x:.2f} / 10" if pd.notnull(x) else "Not Scored"
            )

        summary_cols = [
            "username",
            "full_name",
            "email",
            "interview_done",
            "overall_score",
            "band",
            "scored_at",
        ]
        st.dataframe(
            df[[c for c in summary_cols if c in df.columns]],
            use_container_width=True,
        )

        st.divider()
        st.subheader("Per-candidate detail")
        selected = st.selectbox(
            "Select candidate to view full report",
            options=[r["username"] for r in cleaned_rows],
        )

        if selected:
            matching = [r for r in cleaned_rows if r["username"] == selected]
            if matching and matching[0].get("overall_score") is not "Not Scored":

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

                    # 2. Per-Question Score Matrix Table Breakdown
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

                    # 4. Deep Expandable Feedback Breakdown (Kept under interactive accordions)
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
# admin_app.py (Inside Tab 2: Create candidate component section)

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
        else:
            # 1. Commit the tracking login row parameters to PostgreSQL
            ok = create_candidate(
                username_input, password_input, full_name_input, email_input, "admin"
            )

            if ok:
                st.success(
                    f"Candidate profile **{username_input}** committed successfully to PostgreSQL."
                )

                # ── NEW AUTOMATED EMAIL DISPATCH TRIGGER ──────────────────────
                with st.spinner(
                    "📧 Syncing secure message dispatch with SMTP relays..."
                ):
                    from backend.utils.mailer import send_welcome_email

                    mail_sent = send_welcome_email(
                        candidate_email=email_input,
                        full_name=full_name_input,
                        username=username_input,
                        password_plain=password_input,  # Sends plain text so they know their temporary login pass
                    )

                if mail_sent:
                    st.success(
                        f"📩 Invitation credentials successfully routed to candidate inbox ({email_input})."
                    )
                else:
                    st.warning(
                        "⚠️ Profile created, but SMTP relay dropped email delivery. Check terminal logs."
                    )
                # ──────────────────────────────────────────────────────────────

                st.code(f"Username: {username_input}\nPassword: {password_input}")
            else:
                st.warning(
                    f"Username '{username_input}' already exists in candidates base database."
                )


# streamlit run admin_app.py --server.port 8502
