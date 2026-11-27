import streamlit as st

from api_client import api_request
from ui import DISCLAIMER

st.title("🤖 CuraNex AI Assistant")
st.caption("Ask questions about a patient's uploaded reports. Answers cite the report excerpts.")

status, status_error = api_request("GET", "/assistant/status")
if status_error:
    st.error(status_error)
    st.stop()
if not status["reachable"]:
    st.error(
        f"The language model ({status['provider']}) is not reachable. Start it with "
        "`docker compose --profile llm up`, or run `ollama serve` locally."
    )
    st.stop()
if status["missing_models"]:
    st.warning(
        "Missing models. Run: " + "; ".join(f"`ollama pull {m}`" for m in status["missing_models"])
    )
st.caption(f"Model: {status['chat_model']} · embeddings: {status['embed_model']} · runs locally")

patients, error = api_request("GET", "/patients", params={"limit": 100})
if error:
    st.error(error)
    st.stop()
if not patients:
    st.info("Register a patient and upload a report first.")
    st.stop()

by_id = {p["id"]: p for p in patients}
patient_id = st.selectbox(
    "Patient", options=list(by_id), format_func=lambda pid: f"#{pid} — {by_id[pid]['full_name']}"
)
reports, _ = api_request("GET", f"/patients/{patient_id}/reports")
processed = [r for r in reports or [] if r["status"] == "processed"]
if not processed:
    st.info("This patient has no processed reports. Upload one on the Medical Reports page.")
    st.stop()
st.caption(f"Searching {len(processed)} report(s): " + ", ".join(r["filename"] for r in processed))

history_key = f"chat_{patient_id}"
history = st.session_state.setdefault(history_key, [])

for turn in history:
    with st.chat_message(turn["role"]):
        st.write(turn["content"])
        for citation in turn.get("citations", []):
            page = f", page {citation['page']}" if citation["page"] else ""
            with st.expander(f"[{citation['number']}] {citation['filename']}{page}"):
                st.text(citation["excerpt"])

question = st.chat_input("Ask about this patient's reports, e.g. 'Which values were flagged high?'")
if question:
    history.append({"role": "user", "content": question})
    with st.spinner("Searching reports and drafting an answer..."):
        answer, ask_error = api_request(
            "POST",
            f"/patients/{patient_id}/assistant/ask",
            json={"question": question},
            timeout=180,
        )
    if ask_error:
        history.append({"role": "assistant", "content": f"⚠️ {ask_error}"})
    else:
        history.append(
            {"role": "assistant", "content": answer["answer"], "citations": answer["citations"]}
        )
    st.rerun()

if history and st.button("Clear conversation"):
    st.session_state[history_key] = []
    st.rerun()

st.caption(DISCLAIMER)
