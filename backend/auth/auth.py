# backend/auth/auth.py
import streamlit as st
from backend.db.queries import verify_candidate, candidate_login_allowed

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # change this — or move to .env


def require_admin_login():
    """Returns True if admin is authenticated."""
    if st.session_state.get("admin_logged_in"):
        return True
    st.subheader("Admin login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            st.session_state["admin_logged_in"] = True
            st.rerun()
        else:
            st.error("Wrong credentials.")
    st.stop()


def require_candidate_login():
    """
    Returns (username, full_name) if logged in, else shows login form and stops.
    """
    if st.session_state.get("candidate_logged_in"):
        username = st.session_state["candidate_username"]
        current_session = st.session_state.get("interview_session") or {}
        active_attempt = (
            st.session_state.get("interview_started")
            and current_session.get("status") == "IN_PROGRESS"
        )

        if active_attempt or candidate_login_allowed(username):
            return (
                username,
                st.session_state["candidate_name"],
            )

        for key in ("candidate_logged_in", "candidate_username", "candidate_name"):
            st.session_state.pop(key, None)
        st.error(
            "These interview credentials have expired or the interview has already been completed."
        )
        st.stop()

    st.subheader("Candidate login")
    st.info("Use the credentials provided by your interviewer.")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if verify_candidate(u, p):
            if not candidate_login_allowed(u):
                st.error(
                    "These interview credentials have expired or the interview has already been completed."
                )
                st.stop()

            st.session_state["candidate_logged_in"] = True
            st.session_state["candidate_username"] = u
            st.session_state["candidate_name"] = u
            st.success("Logged in.")
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()
