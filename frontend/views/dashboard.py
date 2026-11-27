import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import api_request, backend_online
from ui import DISCLAIMER, metric_card

st.markdown('<div class="main-title">Welcome to CuraNex AI 👋</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Your intelligent healthcare dashboard</div>', unsafe_allow_html=True
)
st.write("")

online = backend_online()
st.caption(f"Backend status: {'🟢 Connected' if online else '🔴 Offline'}")

count_data, count_error = api_request("GET", "/patients/count") if online else (None, "offline")
patients = str(count_data["count"]) if count_data and not count_error else "—"
model, _ = api_request("GET", "/models/diabetes") if online else (None, "offline")
model_auc = f"{model['metrics']['roc_auc']:.2f} AUC" if model else "N/A"
summary, _ = api_request("GET", "/predictions/summary") if online else (None, "offline")

for col, (label, value) in zip(
    st.columns(4),
    [
        ("👥 Registered Patients", patients),
        ("❤️ Diabetes Model", model_auc),
        ("📄 Reports Analyzed", "N/A"),  # Phase 3
        ("🛡️ System Status", "Active" if online else "Degraded"),
    ],
):
    with col:
        metric_card(label, value)

st.write("")
left, right = st.columns([2, 1])
with left:
    st.markdown("### 📊 Health Overview")
    st.info("Vitals trends appear here once health monitoring is built (Phase 5).")
with right:
    st.markdown("### 🩺 Diabetes Risk Distribution")
    if summary and summary["patients_scored"]:
        risk = pd.DataFrame(
            {
                "Risk": ["Low", "Moderate", "High"],
                "Patients": [summary["low"], summary["moderate"], summary["high"]],
            }
        )
        risk = risk[risk["Patients"] > 0]
        fig = px.pie(
            risk,
            names="Risk",
            values="Patients",
            hole=0.6,
            color="Risk",
            color_discrete_map={"Low": "#22C55E", "Moderate": "#F59E0B", "High": "#EF4444"},
        )
        fig.update_layout(height=320, paper_bgcolor="white", margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Latest prediction for {summary['patients_scored']} active patient(s).")
    else:
        st.info("No predictions yet. Run one from Disease Prediction.")

st.markdown("### ⚡ Quick Actions")
actions = [
    ("👥 Patients", "views/patients.py"),
    ("🧬 Disease Prediction", "views/disease_prediction.py"),
    ("📄 Medical Reports", "views/medical_reports.py"),
    ("🤖 AI Assistant", "views/ai_assistant.py"),
]
for col, (label, target) in zip(st.columns(len(actions)), actions):
    with col:
        if st.button(label, use_container_width=True):
            st.switch_page(target)

st.markdown("### 💡 Health Tips")
st.info("Maintain regular health checkups, follow a balanced diet and stay active.")
st.caption(DISCLAIMER)
