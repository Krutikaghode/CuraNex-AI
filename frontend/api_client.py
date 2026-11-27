"""Thin HTTP client the Streamlit pages use to talk to the FastAPI backend."""

import os

import requests

API_BASE_URL = os.getenv("CURANEX_API_URL", "http://127.0.0.1:8000")


def api_request(method: str, path: str, **kwargs):
    """Call the API and return a (data, error_message) pair for the UI."""
    try:
        response = requests.request(method, f"{API_BASE_URL}{path}", timeout=5, **kwargs)
    except requests.RequestException:
        return None, "Cannot reach the backend. Start the API and try again."

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


def backend_online() -> bool:
    data, error = api_request("GET", "/health")
    return error is None and bool(data) and data.get("status") == "ok"


def fetch_bytes(path: str) -> bytes | None:
    """Download a binary resource through the UI server (the browser cannot reach the API)."""
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=15)
    except requests.RequestException:
        return None
    return response.content if response.ok else None
