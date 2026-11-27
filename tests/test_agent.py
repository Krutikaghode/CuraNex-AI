import pymupdf
import pytest

from app.agents.graph import _parse_intent, keyword_intent
from app.main import app
from app.rag.llm import FakeProvider, LLMUnavailableError, get_llm

REPORT = "LAB REPORT\nHbA1c: 6.9 percent HIGH\nLDL cholesterol: 145 mg/dL"


def setup_patient(client, *, report=True, prediction=True, vitals=True) -> int:
    payload = {"full_name": "Asha Sharma", "age": 52, "gender": "Female"}
    patient_id = client.post("/patients", json=payload).json()["id"]
    if report:
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), REPORT)
        client.post(
            f"/patients/{patient_id}/reports",
            files={"file": ("labs.pdf", document.tobytes(), "application/pdf")},
        )
    if prediction:
        client.post(
            f"/patients/{patient_id}/predictions/diabetes", json={"glucose": 185, "bmi": 39}
        )
    if vitals:
        client.post(f"/patients/{patient_id}/vitals/demo", json={})
    return patient_id


def ask(client, patient_id, question):
    return client.post(f"/patients/{patient_id}/agent/ask", json={"question": question})


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        ("What is her diabetes risk score?", "risk"),
        ("How has her blood pressure trended?", "vitals"),
        ("Any alerts on heart rate?", "vitals"),
        ("Give me an overall summary", "overview"),
        ("What medications is she on?", "reports"),
        ("What was the HbA1c?", "reports"),
    ],
)
def test_keyword_router(question, intent):
    assert keyword_intent(question) == intent


def test_llm_reply_parsing_is_strict():
    assert _parse_intent("risk") == "risk"
    assert _parse_intent("Vitals.") == "vitals"
    assert _parse_intent("I could not find this in the patient's reports.") is None
    assert _parse_intent("") is None


def test_risk_route_uses_stored_prediction(client):
    patient_id = setup_patient(client, report=False, vitals=False)
    body = ask(client, patient_id, "What is the diabetes risk?").json()
    assert body["intent"] == "risk" and body["router"] == "keywords"
    assert "Latest diabetes risk" in body["answer"] and "(high)" in body["answer"]
    assert "Glucose" in body["answer"]
    assert body["steps"][-1] == "compose"


def test_vitals_route_reports_alerts(client):
    patient_id = setup_patient(client, report=False, prediction=False)
    body = ask(client, patient_id, "Show me her vitals").json()
    assert body["intent"] == "vitals"
    assert "30 readings" in body["answer"] and "Alerts:" in body["answer"]


def test_reports_route_returns_citations(client):
    patient_id = setup_patient(client, prediction=False, vitals=False)
    body = ask(client, patient_id, "What was the HbA1c?").json()
    assert body["intent"] == "reports"
    assert body["citations"] and "HbA1c" in body["citations"][0]["excerpt"]


def test_overview_combines_everything(client):
    patient_id = setup_patient(client)
    body = ask(client, patient_id, "Give me an overview of this patient").json()
    assert body["intent"] == "overview"
    assert [s["title"] for s in body["sections"]] == [
        "Diabetes risk",
        "Vitals (30 days)",
        "From the reports",
    ]
    assert body["citations"]


def test_missing_data_is_stated_not_invented(client):
    patient_id = setup_patient(client, report=False, prediction=False, vitals=False)
    body = ask(client, patient_id, "overall summary please").json()
    texts = " ".join(s["text"] for s in body["sections"])
    assert "No diabetes risk prediction" in texts
    assert "No vitals recorded" in texts
    assert "no processed reports" in texts


def test_llm_router_is_used_when_it_answers_cleanly(client):
    class Router(FakeProvider):
        def chat(self, system, user):
            return "vitals" if "Classify" in system else super().chat(system, user)

    patient_id = setup_patient(client, report=False, prediction=False)
    app.dependency_overrides[get_llm] = Router
    body = ask(client, patient_id, "How is she doing lately?").json()
    assert body["intent"] == "vitals" and body["router"] == "llm"


def test_non_llm_routes_work_when_llm_is_down(client):
    class Down(FakeProvider):
        def chat(self, system, user):
            raise LLMUnavailableError("Cannot reach Ollama")

        def embed(self, texts):
            raise LLMUnavailableError("Cannot reach Ollama")

    patient_id = setup_patient(client, vitals=False)
    app.dependency_overrides[get_llm] = Down
    assert ask(client, patient_id, "diabetes risk?").status_code == 200
    assert ask(client, patient_id, "what was the HbA1c?").status_code == 503
    assert ask(client, 999, "risk?").status_code == 404
