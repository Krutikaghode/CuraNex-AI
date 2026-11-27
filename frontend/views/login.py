import streamlit as st

from api_client import backend_online, sign_in
from ui import DISCLAIMER

st.markdown('<div class="main-title">💙 CuraNex AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Sign in to continue</div>', unsafe_allow_html=True)
st.write("")

_, middle, _ = st.columns([1, 2, 1])
with middle:
    if not backend_online():
        st.error("Cannot reach the backend. Start the API and refresh.")
    with st.form("login"):
        email = st.text_input("Email", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)
    if submitted:
        error = sign_in(email.strip(), password)
        if error:
            st.error(error)
        else:
            st.rerun()
    st.caption(
        "No account yet? An admin creates accounts in Settings, or the first admin is "
        "created from CURANEX_ADMIN_EMAIL / CURANEX_ADMIN_PASSWORD (see README)."
    )
    st.caption(DISCLAIMER)
