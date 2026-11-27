"""Shared styling and small UI helpers."""

import streamlit as st

CSS = """
<style>
.stApp { background-color: #F5F7FC; }
[data-testid="stSidebar"] { background-color: #151E42; }
[data-testid="stSidebar"] * { color: white; }
.main-title { font-size: 30px; font-weight: 800; color: #172554; }
.subtitle { color: #64748B; font-size: 15px; }
.metric-card {
    background: white; padding: 22px; border-radius: 15px;
    border: 1px solid #E2E8F0; box-shadow: 0px 3px 12px rgba(0,0,0,0.04);
}
.metric-label { color: #64748B; font-size: 14px; }
.metric-value { color: #172554; font-size: 28px; font-weight: bold; }
div.stButton > button {
    border-radius: 10px; border: none; background: #5746D8;
    color: white; font-weight: 600;
}
</style>
"""

DISCLAIMER = (
    "CuraNex AI is an educational decision-support prototype, not a medical "
    "diagnostic system. Use synthetic data only."
)


def apply_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def coming_soon(phase: str, what: str) -> None:
    st.info(f"{what} arrives in {phase} of the roadmap (see README).")
