"""Streamlit entrypoint: page config, sign-in gate, sidebar and navigation."""

import streamlit as st

from api_client import current_user, sign_out
from ui import DISCLAIMER, apply_styles

st.set_page_config(
    page_title="CuraNex AI",
    page_icon="💙",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_styles()

user = current_user()
if user is None:
    st.navigation([st.Page("views/login.py", title="Sign in", icon="🔐")]).run()
    st.stop()

PAGES = {
    "Main menu": [
        st.Page("views/dashboard.py", title="Dashboard", icon="🏠", default=True),
        st.Page("views/patients.py", title="Patient Management", icon="👥"),
        st.Page("views/disease_prediction.py", title="Disease Prediction", icon="🧬"),
        st.Page("views/medical_reports.py", title="Medical Reports", icon="📄"),
        st.Page("views/ai_assistant.py", title="AI Assistant", icon="🤖"),
        st.Page("views/health_monitoring.py", title="Health Monitoring", icon="📈"),
        st.Page("views/settings.py", title="Settings", icon="⚙️"),
    ]
}

with st.sidebar:
    st.markdown("# 💙 CuraNex AI")
    st.caption("Smart Healthcare Platform")

navigation = st.navigation(PAGES)

with st.sidebar:
    st.divider()
    st.caption(f"Signed in as **{user['full_name']}** ({user['role']})")
    if st.button("Sign out", use_container_width=True):
        sign_out()
        st.rerun()
    st.caption(DISCLAIMER)

navigation.run()
