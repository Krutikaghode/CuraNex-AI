import pandas as pd
import streamlit as st

from api_client import api_request, fetch_bytes
from ui import DISCLAIMER

METHOD_LABELS = {
    "text": "PDF text layer",
    "ocr": "OCR",
    "mixed": "Text layer + OCR",
    "none": "Not extracted",
}

st.title("📄 Medical Report Analysis")
st.caption("Upload lab reports or scans. Text is extracted (with OCR for scans) for the assistant.")

patients, error = api_request("GET", "/patients", params={"limit": 100})
if error:
    st.error(error)
    st.stop()
if not patients:
    st.info("Register a patient first on the Patient Management page.")
    st.stop()

by_id = {p["id"]: p for p in patients}
patient_id = st.selectbox(
    "Patient", options=list(by_id), format_func=lambda pid: f"#{pid} — {by_id[pid]['full_name']}"
)

with st.form("upload_report", clear_on_submit=True):
    uploaded = st.file_uploader(
        "Upload a report (PDF, PNG or JPEG, up to 10 MB)", type=["pdf", "png", "jpg", "jpeg"]
    )
    st.caption("Use synthetic or sample reports only. Do not upload real patient documents.")
    submitted = st.form_submit_button("Upload and extract")

if submitted and uploaded is not None:
    with st.spinner("Extracting text..."):
        report, upload_error = api_request(
            "POST",
            f"/patients/{patient_id}/reports",
            files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
        )
    if upload_error:
        st.error(upload_error)
    elif report["status"] == "processed":
        st.success(
            f"{report['filename']}: {report['page_count']} page(s) read via "
            f"{METHOD_LABELS[report['extraction_method']]}."
        )
        if report["error"]:
            st.warning(report["error"])
    else:
        st.warning(f"{report['filename']} was stored but no text was extracted: {report['error']}")

reports, list_error = api_request("GET", f"/patients/{patient_id}/reports")
if list_error:
    st.error(list_error)
    st.stop()
if not reports:
    st.info("No reports uploaded for this patient yet.")
    st.stop()

st.subheader("Reports")
table = pd.DataFrame(
    [
        {
            "ID": r["id"],
            "File": r["filename"],
            "Pages": r["page_count"],
            "Method": METHOD_LABELS[r["extraction_method"]],
            "Status": r["status"].title(),
            "Uploaded": pd.to_datetime(r["created_at"]).strftime("%Y-%m-%d %H:%M"),
        }
        for r in reports
    ]
)
st.dataframe(table, hide_index=True, use_container_width=True)

selected_id = st.selectbox(
    "View extracted text",
    options=[r["id"] for r in reports],
    format_func=lambda rid: next(
        f"#{r['id']} — {r['filename']}" for r in reports if r["id"] == rid
    ),
)
detail, detail_error = api_request("GET", f"/reports/{selected_id}")
if detail_error:
    st.error(detail_error)
else:
    original = fetch_bytes(f"/reports/{selected_id}/file")
    if original is not None:
        st.download_button(
            "Download original",
            original,
            file_name=detail["filename"],
            mime=detail["content_type"],
        )
    st.text_area("Extracted text", detail["text"] or "(no text)", height=320, disabled=True)

st.caption(DISCLAIMER)
