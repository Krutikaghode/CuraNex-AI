import httpx
import pymupdf
import pytest

from app.core.config import Settings
from app.main import app
from app.rag.chunking import chunk_text
from app.rag.llm import FakeProvider, LLMUnavailableError, OllamaProvider, get_llm

LAB_PAGE = """LAB REPORT - Metabolic panel
Fasting plasma glucose: 132 mg/dL (reference 70-99) HIGH
HbA1c: 6.9 percent (reference below 5.7) HIGH
Serum creatinine: 0.9 mg/dL (reference 0.6-1.1) normal"""
LIPID_PAGE = """LIPID PROFILE
Total cholesterol: 228 mg/dL
LDL cholesterol: 145 mg/dL borderline high
HDL cholesterol: 41 mg/dL"""


def pdf(*pages: str) -> bytes:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    return document.tobytes()


def patient_with_report(client, email: str, *pages: str) -> int:
    payload = {"full_name": "Asha Sharma", "age": 40, "gender": "Female", "email": email}
    patient_id = client.post("/patients", json=payload).json()["id"]
    response = client.post(
        f"/patients/{patient_id}/reports",
        files={"file": ("labs.pdf", pdf(*pages), "application/pdf")},
    )
    assert response.json()["status"] == "processed"
    return patient_id


def ask(client, patient_id: int, question: str):
    return client.post(f"/patients/{patient_id}/assistant/ask", json={"question": question})


# --- chunking ---------------------------------------------------------------


def test_chunking_keeps_page_numbers_and_size():
    text = (
        "--- Page 1 ---\n"
        + "\n".join(f"line {i} " * 8 for i in range(40))
        + ("\n\n--- Page 2 ---\nsecond page")
    )
    chunks = chunk_text(text, size=300, overlap=50)
    assert all(len(c.text) <= 300 for c in chunks)
    assert chunks[0].page == 1 and chunks[-1].page == 2
    assert chunks[-1].text == "second page"
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_chunking_hard_wraps_long_lines_and_validates_overlap():
    chunks = chunk_text("x" * 1000, size=300, overlap=50)
    assert all(len(c.text) <= 300 for c in chunks) and len(chunks) >= 4
    with pytest.raises(ValueError):
        chunk_text("abc", size=100, overlap=100)


def test_fake_embeddings_rank_related_text_higher():
    fake = FakeProvider()
    query, related, unrelated = fake.embed(["hba1c value", "HbA1c: 6.9 percent", "LDL 145"])
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))  # noqa: E731
    assert dot(query, related) > dot(query, unrelated)


# --- API --------------------------------------------------------------------


def test_answer_is_grounded_and_cited(client):
    patient_id = patient_with_report(client, "a@example.com", LAB_PAGE, LIPID_PAGE)
    response = ask(client, patient_id, "What was the HbA1c result?")
    assert response.status_code == 200
    body = response.json()
    assert body["reports_searched"] == 1
    top = body["citations"][0]
    assert "HbA1c" in top["excerpt"]
    assert top["filename"] == "labs.pdf" and top["page"] == 1
    assert "[1]" in body["answer"]
    assert body["provider"] == "fake"

    ldl = ask(client, patient_id, "What is the LDL cholesterol?").json()
    assert ldl["citations"][0]["page"] == 2


def test_retrieval_is_scoped_to_the_patient(client):
    first = patient_with_report(client, "a@example.com", LAB_PAGE)
    second = patient_with_report(client, "b@example.com", LIPID_PAGE)
    body = ask(client, second, "What was the HbA1c result?").json()
    assert all("HbA1c" not in c["excerpt"] for c in body["citations"])
    assert ask(client, first, "HbA1c").json()["citations"]


def test_patient_without_reports(client):
    payload = {"full_name": "Ravi Kumar", "age": 50, "gender": "Male"}
    patient_id = client.post("/patients", json=payload).json()["id"]
    body = ask(client, patient_id, "Any abnormal values?").json()
    assert body["citations"] == []
    assert "no processed reports" in body["answer"]


def test_validation_and_missing_patient(client):
    assert ask(client, 999, "What was the HbA1c?").status_code == 404
    patient_id = patient_with_report(client, "a@example.com", LAB_PAGE)
    assert ask(client, patient_id, "hi").status_code == 422


def test_index_endpoint_and_reindex_on_model_change(client, monkeypatch):
    patient_id = patient_with_report(client, "a@example.com", LAB_PAGE)
    assert client.post(f"/patients/{patient_id}/assistant/index").json() == {"reports_indexed": 1}
    calls = []
    original = FakeProvider.embed

    def counting_embed(self, texts):
        calls.append(len(texts))
        return original(self, texts)

    monkeypatch.setattr(FakeProvider, "embed", counting_embed)
    ask(client, patient_id, "HbA1c")
    assert calls == [1]  # only the question; chunks were already indexed

    monkeypatch.setattr(FakeProvider, "embed_model", "fake-hash-v2")
    calls.clear()
    ask(client, patient_id, "HbA1c")
    assert len(calls) == 2  # report re-embedded for the new model, then the question


def test_llm_unavailable_returns_503(client):
    class Down(FakeProvider):
        def embed(self, texts):
            raise LLMUnavailableError("Cannot reach Ollama")

    patient_id = patient_with_report(client, "a@example.com", LAB_PAGE)
    app.dependency_overrides[get_llm] = Down
    response = ask(client, patient_id, "HbA1c?")
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]
    report = client.get(f"/patients/{patient_id}/reports").json()[0]
    assert report["status"] == "processed"


def test_status_endpoint(client):
    body = client.get("/assistant/status").json()
    assert body == {
        "provider": "fake",
        "chat_model": "fake-extractive",
        "embed_model": "fake-hash-256",
        "reachable": True,
        "missing_models": [],
    }


# --- Ollama client ------------------------------------------------------------


def test_ollama_client_maps_errors(monkeypatch):
    provider = OllamaProvider(Settings(ollama_base_url="http://ollama.test"))

    def refused(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", refused)
    with pytest.raises(LLMUnavailableError, match="Cannot reach Ollama"):
        provider.embed(["x"])

    def missing(url, json, timeout):
        return httpx.Response(404, json={"error": f"model '{json['model']}' not found"})

    monkeypatch.setattr(httpx, "post", missing)
    with pytest.raises(LLMUnavailableError, match="ollama pull nomic-embed-text"):
        provider.embed(["x"])


def test_ollama_client_happy_path(monkeypatch):
    provider = OllamaProvider(Settings(ollama_base_url="http://ollama.test"))
    seen = {}

    def fake_post(url, json, timeout):
        seen[url] = json
        if url.endswith("/api/embed"):
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2]] * len(json["input"])})
        return httpx.Response(200, json={"message": {"content": " Answer [1] "}})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert provider.embed(["a", "b"]) == [[0.1, 0.2], [0.1, 0.2]]
    assert provider.chat("system", "user") == "Answer [1]"
    chat = seen["http://ollama.test/api/chat"]
    assert chat["stream"] is False and chat["messages"][0]["role"] == "system"


def test_eval_harness_runs_with_fake_provider(monkeypatch):
    from app.core.config import get_settings
    from app.rag.evaluate import run

    monkeypatch.setattr(get_settings(), "llm_provider", "fake")
    result = run()
    retrieved, total = map(int, result["summary"]["retrieval_hit"].split("/"))
    assert total == 8
    assert retrieved >= 6  # even bag-of-words retrieval finds most facts
