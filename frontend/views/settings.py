import pandas as pd
import streamlit as st

from api_client import api_request, current_user

st.title("⚙️ Settings")
user = current_user()

st.subheader("Your account")
st.write(f"**{user['full_name']}** · {user['email']} · role: {user['role']}")

status, _ = api_request("GET", "/assistant/status")
model, _ = api_request("GET", "/models/diabetes")
st.subheader("System")
cols = st.columns(2)
with cols[0]:
    if model:
        st.write(f"Diabetes model: `{model['name']}` v{model['version']}")
with cols[1]:
    if status:
        state = "reachable" if status["reachable"] else "not reachable"
        st.write(f"Assistant: `{status['provider']}` / `{status['chat_model']}` ({state})")

if user["role"] != "admin":
    st.stop()

st.subheader("Users")
users, error = api_request("GET", "/auth/users")
if error:
    st.error(error)
    st.stop()
st.dataframe(
    pd.DataFrame(users)[["id", "email", "full_name", "role", "is_active", "last_login_at"]],
    hide_index=True,
    use_container_width=True,
)

with st.form("create_user", clear_on_submit=True):
    st.markdown("**Add a user**")
    c1, c2 = st.columns(2)
    with c1:
        email = st.text_input("Email")
        name = st.text_input("Full name")
    with c2:
        password = st.text_input("Temporary password (min 10 chars)", type="password")
        role = st.selectbox("Role", ["clinician", "admin"])
    if st.form_submit_button("Create user"):
        _, create_error = api_request(
            "POST",
            "/auth/users",
            json={"email": email, "full_name": name, "password": password, "role": role},
        )
        if create_error:
            st.error(create_error)
        else:
            st.success(f"Created {email}.")
            st.rerun()

others = [u for u in users if u["id"] != user["id"]]
if others:
    target = st.selectbox(
        "Activate or deactivate",
        options=[u["id"] for u in others],
        format_func=lambda uid: next(
            f"{u['email']} ({'active' if u['is_active'] else 'inactive'})"
            for u in others
            if u["id"] == uid
        ),
    )
    selected = next(u for u in others if u["id"] == target)
    label = "Deactivate" if selected["is_active"] else "Activate"
    if st.button(label):
        _, toggle_error = api_request(
            "PATCH", f"/auth/users/{target}", json={"is_active": not selected["is_active"]}
        )
        if toggle_error:
            st.error(toggle_error)
        else:
            st.rerun()
