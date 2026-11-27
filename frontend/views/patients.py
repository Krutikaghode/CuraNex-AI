import pandas as pd
import streamlit as st

from api_client import api_request

GENDER_OPTIONS = ["Female", "Male", "Non-binary", "Other", "Prefer not to say"]

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
                gender_options = GENDER_OPTIONS
                stored_gender = selected["gender"].title()
                gender_index = (
                    gender_options.index(stored_gender)
                    if stored_gender in gender_options
                    else len(gender_options) - 1
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
