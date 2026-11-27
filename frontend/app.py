"""Streamlit entrypoint: page config, sidebar and navigation."""

import streamlit as st

from ui import DISCLAIMER, apply_styles

st.set_page_config(
    page_title="CuraNex AI",
    page_icon="💙",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_styles()

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
    st.caption(DISCLAIMER)

navigation.run()
