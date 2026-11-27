
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os


API_BASE_URL = os.getenv("CURANEX_API_URL", "http://127.0.0.1:8000")


def api_request(method, path, **kwargs):
    """Call FastAPI and return a (data, error_message) pair for the UI."""
    try:
        response = requests.request(
            method,
            f"{API_BASE_URL}{path}",
            timeout=5,
            **kwargs,
        )
    except requests.RequestException:
        return None, "Cannot reach the backend. Start FastAPI and try again."

    if response.status_code == 204:
        return {}, None
    try:
        data = response.json()
    except ValueError:
        data = None
    if not response.ok:
        if isinstance(data, dict):
            return None, data.get("detail", "The backend could not complete this request.")
        return None, "The backend could not complete this request."
    return data, None

# -------------------------------
# PAGE CONFIGURATION
# -------------------------------

st.set_page_config(
    page_title="CuraNex AI",
    page_icon="💙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------
# CUSTOM CSS
# -------------------------------

st.markdown("""
<style>

.stApp {
    background-color: #F5F7FC;
}

[data-testid="stSidebar"] {
    background-color: #151E42;
}

[data-testid="stSidebar"] * {
    color: white;
}

.main-title {
    font-size: 30px;
    font-weight: 800;
    color: #172554;
}

.subtitle {
    color: #64748B;
    font-size: 15px;
}

.metric-card {
    background: white;
    padding: 22px;
    border-radius: 15px;
    border: 1px solid #E2E8F0;
    box-shadow: 0px 3px 12px rgba(0,0,0,0.04);
}

.metric-label {
    color: #64748B;
    font-size: 14px;
}

.metric-value {
    color: #172554;
    font-size: 28px;
    font-weight: bold;
}

.section-card {
    background: white;
    padding: 20px;
    border-radius: 15px;
    border: 1px solid #E2E8F0;
}

div.stButton > button {
    border-radius: 10px;
    border: none;
    background: #5746D8;
    color: white;
    font-weight: 600;
}

</style>
""", unsafe_allow_html=True)


# -------------------------------
# SIDEBAR
# -------------------------------

with st.sidebar:

    st.markdown("# 💙 CuraNex AI")

    st.caption("Smart Healthcare Platform")

    st.divider()

    page = st.radio(
        "MAIN MENU",
        [
            "Dashboard",
            "Patient Management",
            "Disease Prediction",
            "Medical Reports",
            "AI Assistant",
            "Health Monitoring",
            "Settings"
        ]
    )

    st.divider()

    st.markdown("### 💙 Your Health")
    st.markdown("Your Priority")

    st.caption("Intelligent Healthcare Platform")


# -------------------------------
# DASHBOARD HEADER
# -------------------------------

if page == "Dashboard":

    st.markdown(
        '<div class="main-title">Welcome to CuraNex AI 👋</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">Your intelligent healthcare dashboard</div>',
        unsafe_allow_html=True
    )

    st.write("")

    # Backend connection status

    try:
        response = requests.get(
            f"{API_BASE_URL}/health",
            timeout=2
        )

        backend_status = (
            "🟢 Connected" if response.ok
            else "🔴 Unavailable"
        )

    except requests.RequestException:
        backend_status = "🔴 Offline"

    st.caption(f"Backend Status: {backend_status}")
    patient_count, patient_count_error = api_request("GET", "/patients/count")

    # ---------------------------
    # METRIC CARDS
    # ---------------------------

    col1, col2, col3, col4 = st.columns(4)

    metrics = [
        (col1, "👥 Registered Patients", "128"),
        (col2, "❤️ Model Accuracy", "N/A"),
        (col3, "📄 Reports Analyzed", "0"),
        (col4, "🛡️ System Status", "Active")
    ]

    for col, label, value in metrics:

        if value == "128" and patient_count and not patient_count_error:
            value = str(patient_count["count"])

        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.write("")

    # ---------------------------
    # HEALTH OVERVIEW
    # ---------------------------

    left, right = st.columns([2, 1])

    with left:

        st.markdown("### 📊 Health Overview")

        health_data = pd.DataFrame({
            "Date": pd.date_range(
                "2026-11-01",
                periods=7
            ),
            "Glucose": [95, 98, 110, 105, 115, 112, 120],
            "Blood Pressure": [75, 78, 80, 76, 82, 79, 81],
            "Heart Rate": [65, 67, 70, 68, 72, 71, 74]
        })

        health_long = health_data.melt(
            id_vars="Date",
            var_name="Metric",
            value_name="Value"
        )

        fig = px.line(
            health_long,
            x="Date",
            y="Value",
            color="Metric",
            markers=True,
            title="Illustrative Health Trends"
        )

        fig.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            height=350
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with right:

        st.markdown("### 🩺 Risk Distribution")

        risk_data = pd.DataFrame({
            "Risk": ["Low", "Moderate", "High"],
            "Count": [60, 25, 15]
        })

        fig = px.pie(
            risk_data,
            names="Risk",
            values="Count",
            hole=0.6,
            color="Risk",
            color_discrete_map={
                "Low": "#22C55E",
                "Moderate": "#F59E0B",
                "High": "#EF4444"
            }
        )

        fig.update_layout(
            height=350,
            paper_bgcolor="white"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # ---------------------------
    # QUICK ACTIONS
    # ---------------------------

    st.markdown("### ⚡ Quick Actions")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("🧬 Disease Prediction"):
            st.session_state["selected_page"] = "Disease Prediction"
            st.rerun()

    with c2:
        if st.button("📄 Medical Reports"):
            st.session_state["selected_page"] = "Medical Reports"
            st.rerun()

    with c3:
        if st.button("🤖 AI Assistant"):
            st.session_state["selected_page"] = "AI Assistant"
            st.rerun()

    with c4:
        if st.button("📈 Health Monitoring"):
            st.session_state["selected_page"] = "Health Monitoring"
            st.rerun()

    # ---------------------------
    # HEALTH TIPS
    # ---------------------------

    st.markdown("### 💡 Health Tips")

    st.info(
        "Maintain regular health checkups, "
        "follow a balanced diet and stay active."
    )

    st.caption(
        "CuraNex AI is an educational decision-support "
        "prototype, not a medical diagnostic system."
    )


# -------------------------------
# OTHER PAGES
# -------------------------------

elif page == "Patient Management":

    st.title("👥 Patient Management")
    st.caption("Register, find, update, deactivate, or restore patient records.")

    active_count, count_error = api_request("GET", "/patients/count")
    if count_error:
        st.error(count_error)
        st.stop()

    st.metric("Active patients", active_count["count"])
    register_tab, directory_tab = st.tabs(["Register Patient", "Patient Directory"])

    with register_tab:
        st.subheader("Register a patient")
        with st.form("register_patient", clear_on_submit=True):
            left, right = st.columns(2)
            with left:
                full_name = st.text_input("Full name *", max_chars=120)
                age = st.number_input("Age *", min_value=0, max_value=130, value=18)
                gender = st.selectbox(
                    "Gender *",
                    ["Female", "Male", "Non-binary", "Other", "Prefer not to say"],
                )
            with right:
                email = st.text_input("Email")
                phone = st.text_input("Phone", max_chars=30)
            concern = st.text_area(
                "Primary concern / notes",
                max_chars=1000,
                help="For this educational prototype, do not enter highly sensitive information.",
            )
            submitted = st.form_submit_button("Register Patient")

        if submitted:
            payload = {
                "full_name": full_name,
                "age": age,
                "gender": gender,
                "email": email or None,
                "phone": phone or None,
                "concern": concern or None,
            }
            patient, error = api_request("POST", "/patients", json=payload)
            if error:
                st.error(error)
            else:
                st.success(f"{patient['full_name']} was registered (ID: {patient['id']}).")

    with directory_tab:
        show_inactive = st.checkbox("Include inactive patients")
        search = st.text_input("Search by name, email, or phone")
        params = {"include_inactive": show_inactive, "limit": 100}
        if search.strip():
            params["search"] = search.strip()
        patients, error = api_request("GET", "/patients", params=params)

        if error:
            st.error(error)
        elif not patients:
            st.info("No matching patients found.")
        else:
            display_rows = [
                {
                    "ID": patient["id"],
                    "Name": patient["full_name"],
                    "Age": patient["age"],
                    "Gender": patient["gender"].title(),
                    "Email": patient["email"] or "—",
                    "Phone": patient["phone"] or "—",
                    "Status": "Active" if patient["is_active"] else "Inactive",
                    "Created": patient["created_at"],
                }
                for patient in patients
            ]
            st.dataframe(pd.DataFrame(display_rows), hide_index=True, use_container_width=True)

            selected_id = st.selectbox(
                "Select a patient to manage",
                options=[patient["id"] for patient in patients],
                format_func=lambda patient_id: next(
                    f"#{patient['id']} — {patient['full_name']}"
                    for patient in patients
                    if patient["id"] == patient_id
                ),
            )
            selected = next(patient for patient in patients if patient["id"] == selected_id)

            st.subheader(f"Manage {selected['full_name']}")
            with st.form(f"edit_patient_{selected_id}"):
                edit_left, edit_right = st.columns(2)
                with edit_left:
                    edited_name = st.text_input("Full name *", value=selected["full_name"])
                    edited_age = st.number_input(
                        "Age *", min_value=0, max_value=130, value=selected["age"]
                    )
                    gender_options = [
                        "Female", "Male", "Non-binary", "Other", "Prefer not to say"
                    ]
                    stored_gender = selected["gender"].title()
                    gender_index = (
                        gender_options.index(stored_gender)
                        if stored_gender in gender_options else len(gender_options) - 1
                    )
                    edited_gender = st.selectbox("Gender *", gender_options, index=gender_index)
                with edit_right:
                    edited_email = st.text_input("Email", value=selected["email"] or "")
                    edited_phone = st.text_input("Phone", value=selected["phone"] or "")
                edited_concern = st.text_area(
                    "Primary concern / notes", value=selected["concern"] or "", max_chars=1000
                )
                save_changes = st.form_submit_button("Save Changes")

            if save_changes:
                payload = {
                    "full_name": edited_name,
                    "age": edited_age,
                    "gender": edited_gender,
                    "email": edited_email or None,
                    "phone": edited_phone or None,
                    "concern": edited_concern or None,
                }
                _, update_error = api_request("PATCH", f"/patients/{selected_id}", json=payload)
                if update_error:
                    st.error(update_error)
                else:
                    st.success("Patient record updated.")
                    st.rerun()

            if selected["is_active"]:
                if st.button("Deactivate Patient", type="secondary"):
                    _, deactivate_error = api_request("DELETE", f"/patients/{selected_id}")
                    if deactivate_error:
                        st.error(deactivate_error)
                    else:
                        st.success("Patient deactivated. The record was retained.")
                        st.rerun()
            elif st.button("Restore Patient"):
                _, restore_error = api_request("PATCH", f"/patients/{selected_id}/restore")
                if restore_error:
                    st.error(restore_error)
                else:
                    st.success("Patient restored.")
                    st.rerun()

elif page == "Disease Prediction":

    st.title("🧬 Disease Risk Prediction")
    st.info("ML prediction models will be integrated here.")

elif page == "Medical Reports":

    st.title("📄 Medical Report Analysis")

    uploaded_file = st.file_uploader(
        "Upload a medical report",
        type=["pdf", "png", "jpg", "jpeg"]
    )

    if uploaded_file:
        st.success("File uploaded successfully.")
        st.write("File name:", uploaded_file.name)

elif page == "AI Assistant":

    st.title("🤖 CuraNex AI Assistant")

    question = st.chat_input(
        "Ask a question about your uploaded report..."
    )

    if question:
        st.chat_message("user").write(question)

        st.chat_message("assistant").write(
            "The RAG-based AI assistant will be connected here."
        )

elif page == "Health Monitoring":

    st.title("📈 Health Monitoring")
    st.info("Patient health trends will appear here.")

elif page == "Settings":

    st.title("⚙️ Settings")
    st.info("Application settings will appear here.")
