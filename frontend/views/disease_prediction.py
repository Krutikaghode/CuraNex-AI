import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import api_request
from ui import DISCLAIMER

RISK_COLORS = {"low": "#22C55E", "moderate": "#F59E0B", "high": "#EF4444"}

st.title("🧬 Disease Risk Prediction")
st.caption("Diabetes risk from routine clinical measurements, with the factors behind each score.")

model, model_error = api_request("GET", "/models/diabetes")
if model_error:
    st.error(model_error)
    st.stop()

metrics = model["metrics"]
with st.expander(f"Model: {model['name']} v{model['version']}", expanded=False):
    cols = st.columns(4)
    cols[0].metric("ROC AUC", f"{metrics['roc_auc']:.2f}")
    cols[1].metric("Accuracy", f"{metrics['accuracy']:.0%}")
    cols[2].metric("Recall", f"{metrics['recall']:.0%}")
    cols[3].metric("Precision", f"{metrics['precision']:.0%}")
    st.caption(
        f"{model['algorithm']}, trained {model['trained_at'][:10]} on the Pima Indians Diabetes "
        f"dataset ({model['dataset']['rows']} rows; held-out test set of "
        f"{model['dataset']['test_rows']}). The training population is women of Pima heritage "
        "aged 21+, so scores for anyone else are illustrative only."
    )

patients, patients_error = api_request("GET", "/patients", params={"limit": 100})
if patients_error:
    st.error(patients_error)
    st.stop()
if not patients:
    st.info("Register a patient first on the Patient Management page.")
    st.stop()

by_id = {p["id"]: p for p in patients}
patient_id = st.selectbox(
    "Patient",
    options=list(by_id),
    format_func=lambda pid: f"#{pid} — {by_id[pid]['full_name']} ({by_id[pid]['age']} y)",
)
patient = by_id[patient_id]

with st.form("diabetes_form"):
    st.markdown("**Measurements** (leave optional fields empty if not measured)")
    left, mid, right = st.columns(3)
    with left:
        glucose = st.number_input("Glucose, 2 h OGTT (mg/dL) *", 1.0, 400.0, 110.0, step=1.0)
        bmi = st.number_input("BMI *", 1.0, 80.0, 27.0, step=0.1)
        age = st.number_input("Age", 0, 130, int(patient["age"]))
    with mid:
        blood_pressure = st.number_input("Diastolic BP (mm Hg)", 1.0, 200.0, None, step=1.0)
        insulin = st.number_input("Insulin, 2 h (mu U/mL)", 1.0, 1000.0, None, step=1.0)
        skin_thickness = st.number_input("Triceps skin fold (mm)", 1.0, 100.0, None, step=1.0)
    with right:
        pregnancies = st.number_input("Pregnancies", 0, 25, None, step=1)
        diabetes_pedigree = st.number_input(
            "Diabetes pedigree function",
            0.0,
            3.0,
            None,
            step=0.01,
            help="Family-history score from the dataset; typical values 0.1–1.0.",
        )
    submitted = st.form_submit_button("Predict risk")

if submitted:
    payload = {
        "glucose": glucose,
        "bmi": bmi,
        "age": age,
        "blood_pressure": blood_pressure,
        "insulin": insulin,
        "skin_thickness": skin_thickness,
        "pregnancies": pregnancies,
        "diabetes_pedigree": diabetes_pedigree,
    }
    result, error = api_request(
        "POST", f"/patients/{patient_id}/predictions/diabetes", json=payload
    )
    if error:
        st.error(error)
    else:
        st.session_state["last_prediction"] = result

result = st.session_state.get("last_prediction")
if result and result["patient_id"] == patient_id:
    st.divider()
    score, factors = st.columns([1, 2])
    with score:
        level = result["risk_level"]
        st.metric("Estimated diabetes risk", f"{result['probability']:.0%}")
        st.markdown(
            f"<span style='background:{RISK_COLORS[level]};color:white;padding:4px 12px;"
            f"border-radius:12px;font-weight:600'>{level.upper()} RISK</span>",
            unsafe_allow_html=True,
        )
    with factors:
        contrib = pd.DataFrame(result["contributions"])
        contrib["direction"] = contrib["impact"].map(
            lambda v: "raises risk" if v > 0 else "lowers risk"
        )
        contrib["shown"] = contrib.apply(
            lambda r: (
                f"{r['label']} = {r['value']:g}"
                if r["value"] is not None and pd.notna(r["value"])
                else f"{r['label']} (not measured)"
            ),
            axis=1,
        )
        fig = px.bar(
            contrib.iloc[::-1],
            x="impact",
            y="shown",
            color="direction",
            orientation="h",
            color_discrete_map={"raises risk": "#EF4444", "lowers risk": "#22C55E"},
            title="What drove this score (SHAP, log-odds)",
        )
        fig.update_layout(height=320, yaxis_title=None, xaxis_title=None, legend_title=None)
        st.plotly_chart(fig, use_container_width=True)

history, history_error = api_request("GET", f"/patients/{patient_id}/predictions")
if history:
    st.subheader("History")
    frame = pd.DataFrame(history)
    frame["created_at"] = pd.to_datetime(frame["created_at"])
    if len(frame) > 1:
        fig = px.line(
            frame.sort_values("created_at"),
            x="created_at",
            y="probability",
            markers=True,
            range_y=[0, 1],
        )
        fig.update_layout(height=250, xaxis_title=None, yaxis_title="Risk")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        frame[["created_at", "probability", "risk_level", "model_version"]].rename(
            columns={
                "created_at": "When",
                "probability": "Risk",
                "risk_level": "Level",
                "model_version": "Model version",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

st.caption(DISCLAIMER)
