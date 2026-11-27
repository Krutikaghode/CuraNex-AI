from datetime import UTC, datetime, time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from api_client import api_request
from ui import DISCLAIMER

STATUS_ICON = {"normal": "🟢", "low": "🔵", "high": "🔴", "no-data": "⚪"}

st.title("📈 Health Monitoring")
st.caption("Track vitals, flag out-of-range values and changes from each patient's own baseline.")

patients, error = api_request("GET", "/patients", params={"limit": 100})
if error:
    st.error(error)
    st.stop()
if not patients:
    st.info("Register a patient first on the Patient Management page.")
    st.stop()

by_id = {p["id"]: p for p in patients}
left, right = st.columns([3, 1])
with left:
    patient_id = st.selectbox(
        "Patient",
        options=list(by_id),
        format_func=lambda pid: f"#{pid} — {by_id[pid]['full_name']}",
    )
with right:
    window = st.selectbox("Window", [7, 30, 90, 365], index=1, format_func=lambda d: f"{d} days")

with st.expander("➕ Record a reading"):
    with st.form("record_vitals", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            day = st.date_input("Date", value=datetime.now().date())
            glucose = st.number_input("Glucose (mg/dL)", 20.0, 600.0, None)
            spo2 = st.number_input("SpO2 (%)", 50.0, 100.0, None)
        with c2:
            at = st.time_input("Time", value=datetime.now().time().replace(second=0, microsecond=0))
            systolic = st.number_input("Systolic BP", 50.0, 260.0, None)
            diastolic = st.number_input("Diastolic BP", 30.0, 160.0, None)
        with c3:
            heart_rate = st.number_input("Heart rate (bpm)", 20.0, 250.0, None)
            temperature = st.number_input("Temperature (°C)", 30.0, 44.0, None)
            weight = st.number_input("Weight (kg)", 1.0, 400.0, None)
        notes = st.text_input("Notes", max_chars=500)
        if st.form_submit_button("Save reading"):
            recorded = datetime.combine(day, at or time(0)).astimezone(UTC)
            _, save_error = api_request(
                "POST",
                f"/patients/{patient_id}/vitals",
                json={
                    "recorded_at": recorded.isoformat(),
                    "glucose": glucose,
                    "systolic_bp": systolic,
                    "diastolic_bp": diastolic,
                    "heart_rate": heart_rate,
                    "spo2": spo2,
                    "temperature_c": temperature,
                    "weight_kg": weight,
                    "notes": notes or None,
                },
            )
            if save_error:
                st.error(save_error)
            else:
                st.success("Reading saved.")

analysis, analysis_error = api_request(
    "GET", f"/patients/{patient_id}/vitals/analysis", params={"days": window}
)
if analysis_error:
    st.error(analysis_error)
    st.stop()

if analysis["readings"] == 0:
    st.info("No readings in this window.")
    if st.button("Generate 30 days of demo vitals"):
        _, demo_error = api_request("POST", f"/patients/{patient_id}/vitals/demo", json={})
        if demo_error:
            st.error(demo_error)
        st.rerun()
    st.stop()

if analysis["alerts"]:
    st.error("**Alerts**\n\n" + "\n".join(f"- {a}" for a in analysis["alerts"]))
else:
    st.success("No alerts in this window.")

metrics = [m for m in analysis["metrics"] if m["readings"]]
for row_start in range(0, len(metrics), 4):
    for col, m in zip(st.columns(4), metrics[row_start : row_start + 4]):
        trend = m["trend_per_30d"]
        col.metric(
            f"{STATUS_ICON[m['status']]} {m['label']}",
            f"{m['latest']:g} {m['unit']}",
            delta=f"{trend:+.1f} / 30 d" if trend is not None else None,
            delta_color="off",
        )

readings, _ = api_request("GET", f"/patients/{patient_id}/vitals", params={"days": window})
frame = pd.DataFrame(readings or [])
frame["recorded_at"] = pd.to_datetime(frame["recorded_at"])

chosen = st.selectbox(
    "Chart",
    options=[m["metric"] for m in metrics],
    format_func=lambda k: next(m["label"] for m in metrics if m["metric"] == k),
)
meta = next(m for m in metrics if m["metric"] == chosen)
series = frame[["recorded_at", chosen]].dropna()
fig = go.Figure()
if meta["reference_low"] is not None or meta["reference_high"] is not None:
    low = meta["reference_low"] if meta["reference_low"] is not None else series[chosen].min()
    high = meta["reference_high"] if meta["reference_high"] is not None else series[chosen].max()
    fig.add_hrect(y0=low, y1=high, fillcolor="#22C55E", opacity=0.08, line_width=0)
fig.add_trace(
    go.Scatter(x=series["recorded_at"], y=series[chosen], mode="lines+markers", name=meta["label"])
)
fig.update_layout(
    height=360,
    yaxis_title=f"{meta['label']} ({meta['unit']})",
    margin=dict(t=20),
    plot_bgcolor="white",
    paper_bgcolor="white",
)
st.plotly_chart(fig, use_container_width=True)
st.caption("Shaded band: general adult reference range.")

with st.expander("All readings"):
    st.dataframe(frame.drop(columns=["patient_id"]), hide_index=True, use_container_width=True)

st.caption(DISCLAIMER)
