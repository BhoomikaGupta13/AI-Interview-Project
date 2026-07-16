import runpy
import streamlit as st

# ── Import the authoritative styling tools ──────────────────────────────────
from backend.ui.theme import (
    apply_theme,
    render_hero,
    card_open,
    card_close,
)

# Configure page at the portal root level
st.set_page_config(
    page_title="AI Interview Portal",
    layout="wide",
    page_icon="🎙️",
    initial_sidebar_state="expanded",
)

ROLE_APPS = {
    "Candidate login": "streamlit_app.py",
    "Admin login": "admin_app.py",
}


def reset_role_state():
    for key in (
        "portal_role",
        "admin_logged_in",
        "candidate_logged_in",
        "candidate_username",
        "candidate_name",
    ):
        st.session_state.pop(key, None)


# Inject the deep navy + teal accents stylesheet instantly
apply_theme("candidate")

# ── Phase 1: Show Selection Dash if no role is chosen yet ────────────────────
if "portal_role" not in st.session_state:
    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

    # Render polished hero banner matching admin/candidate states
    render_hero(
        eyebrow="System Gateway",
        title="AI Interview Portal",
        subtitle="Welcome. Please pick your destination below to proceed into the application environment.",
        right_badge="System Online",
        right_icon="fa-circle-check",
    )

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        card_open("Candidate Workspace", icon="fa-user-astronaut")
        st.markdown(
            "<p style='color:var(--ink-soft); margin:.2rem 0 1.5rem 0; min-height: 55px;'>"
            "Proceed here to complete your scheduled voice and interface evaluations, verify audio setups, and view instructions."
            "</p>",
            unsafe_allow_html=True,
        )
        if st.button("Candidate login →", use_container_width=True, type="primary"):
            st.session_state["portal_role"] = "Candidate login"
            st.rerun()
        card_close()

    with col2:
        card_open("Admin Console", icon="fa-shield-halved")
        st.markdown(
            "<p style='color:var(--ink-soft); margin:.2rem 0 1.5rem 0; min-height: 55px;'>"
            "Proceed here to review candidate rosters, evaluate metrics anomalies, manage testing logs, and check proctor flags."
            "</p>",
            unsafe_allow_html=True,
        )
        if st.button("Admin login →", use_container_width=True):
            st.session_state["portal_role"] = "Admin login"
            st.rerun()
        card_close()

    st.stop()

# ── Phase 2: Execution Side-Chaining ─────────────────────────────────────────
st.sidebar.caption("Portal Dynamic Context")
st.sidebar.write(st.session_state["portal_role"])
if st.sidebar.button("Change login type", use_container_width=True):
    reset_role_state()
    st.rerun()

# Execute sub-app as an embedded layout
runpy.run_path(ROLE_APPS[st.session_state["portal_role"]], run_name="__portal__")
