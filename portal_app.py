import runpy

import streamlit as st


st.set_page_config(page_title="AI Interview Portal", layout="wide")


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


if "portal_role" not in st.session_state:
    st.title("AI Interview Portal")
    st.subheader("Choose login type")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Candidate login", use_container_width=True):
            st.session_state["portal_role"] = "Candidate login"
            st.rerun()
    with col2:
        if st.button("Admin login", use_container_width=True):
            st.session_state["portal_role"] = "Admin login"
            st.rerun()

    st.stop()


st.sidebar.caption("Portal")
st.sidebar.write(st.session_state["portal_role"])
if st.sidebar.button("Change login type"):
    reset_role_state()
    st.rerun()

runpy.run_path(ROLE_APPS[st.session_state["portal_role"]], run_name="__portal__")
