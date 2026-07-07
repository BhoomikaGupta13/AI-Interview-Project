"""
portal.py — Unified entry for the AI Interview System.

Adds a sidebar switcher (Candidate ⇄ Admin) and a light/dark theme toggle
in the main content area. Both apps run inside this shell without touching
any backend logic.

Run with:
    streamlit run portal.py --server.port 8500
"""

import runpy
import streamlit as st

from backend.ui.theme import (
    apply_theme,
    render_theme_toggle,
    render_sidebar_brand,
    render_sidebar_switcher,
)

# Configure page ONCE at the portal level. Both child scripts check
# `if __name__ != "__portal__"` before calling st.set_page_config themselves,
# which prevents Streamlit's "set_page_config called twice" error.
st.set_page_config(
    page_title="InterviewAI — Portal",
    layout="wide",
    page_icon="🎙️",
    initial_sidebar_state="expanded",
)

# Persist selected role across reruns
if "portal_role" not in st.session_state:
    st.session_state["portal_role"] = "candidate"

# ── Sidebar: brand + login-type switcher ─────────────────────────────────────
apply_theme(st.session_state["portal_role"])
render_sidebar_brand(st.session_state["portal_role"])
new_role = render_sidebar_switcher(st.session_state["portal_role"])
if new_role != st.session_state["portal_role"]:
    st.session_state["portal_role"] = new_role
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(
    "Tip — use the light/dark switch in the main area to change appearance."
)

# ── Route to the selected sub-app ────────────────────────────────────────────
target = "streamlit_app.py" if st.session_state["portal_role"] == "candidate" else "admin_app.py"

# Run the module with __name__ set to "__portal__" so its guard skips set_page_config.
runpy.run_path(target, run_name="__portal__")
