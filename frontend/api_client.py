"""Thin HTTP client the Streamlit pages use to talk to the FastAPI backend.

The access token lives in this browser session's st.session_state only; it is never
written to disk or cookies.
"""

import os

import requests
import streamlit as st

API_BASE_URL = os.getenv("CURANEX_API_URL", "http://127.0.0.1:8000")
TOKEN_KEY = "access_token"
USER_KEY = "current_user"


def _headers() -> dict[str, str]:
    token = st.session_state.get(TOKEN_KEY)
    return {"Authorization": f"Bearer {token}"} if token else {}


def sign_out() -> None:
    st.session_state.pop(TOKEN_KEY, None)
    st.session_state.pop(USER_KEY, None)


def api_request(method: str, path: str, timeout: float = 10, **kwargs):
    """Call the API and return a (data, error_message) pair for the UI."""
    headers = {**_headers(), **kwargs.pop("headers", {})}
    try:
        response = requests.request(
            method, f"{API_BASE_URL}{path}", timeout=timeout, headers=headers, **kwargs
        )
    except requests.Timeout:
        return None, "The backend took too long to respond. Try again."
    except requests.RequestException:
        return None, "Cannot reach the backend. Start the API and try again."

    if response.status_code == 401 and st.session_state.get(TOKEN_KEY):
        sign_out()
        st.rerun()
    if response.status_code == 204:
        return {}, None
    try:
        data = response.json()
    except ValueError:
        data = None
    if not response.ok:
        detail = data.get("detail") if isinstance(data, dict) else None
        if isinstance(detail, list):  # FastAPI validation errors
            detail = "; ".join(item.get("msg", "") for item in detail)
        return None, detail or "The backend could not complete this request."
    return data, None


def sign_in(email: str, password: str) -> str | None:
    """Returns an error message, or None on success."""
    token, error = api_request(
        "POST", "/auth/token", data={"username": email, "password": password}
    )
    if error:
        return error
    st.session_state[TOKEN_KEY] = token["access_token"]
    user, error = api_request("GET", "/auth/me")
    if error:
        sign_out()
        return error
    st.session_state[USER_KEY] = user
    return None


def current_user() -> dict | None:
    return st.session_state.get(USER_KEY)


def backend_online() -> bool:
    data, error = api_request("GET", "/health")
    return error is None and bool(data) and data.get("status") == "ok"


def fetch_bytes(path: str) -> bytes | None:
    """Download a binary resource through the UI server (the browser cannot reach the API)."""
    try:
        response = requests.get(f"{API_BASE_URL}{path}", headers=_headers(), timeout=15)
    except requests.RequestException:
        return None
    return response.content if response.ok else None
