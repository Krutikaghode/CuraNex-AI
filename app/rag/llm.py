"""LLM and embedding providers behind one small interface.

Ollama runs locally, so patient text never leaves the machine. FakeProvider is
deterministic and dependency-free; tests and offline demos use it.
"""

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings


class LLMUnavailableError(RuntimeError):
    """The configured LLM backend cannot be reached or returned an error."""


class LLMProvider(Protocol):
    name: str
    chat_model: str
    embed_model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def chat(self, system: str, user: str) -> str: ...

    def status(self) -> dict: ...


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.chat_model = settings.ollama_model
        self.embed_model = settings.ollama_embed_model
        self.timeout = settings.llm_timeout_seconds

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = httpx.post(f"{self.base_url}{path}", json=payload, timeout=self.timeout)
        except httpx.HTTPError as error:
            raise LLMUnavailableError(
                f"Cannot reach Ollama at {self.base_url}. Start it with "
                "`docker compose --profile llm up` or `ollama serve`."
            ) from error
        if response.status_code == 404 and "not found" in response.text.lower():
            raise LLMUnavailableError(
                f"Ollama model missing. Run: ollama pull {payload.get('model')}"
            )
        if response.is_error:
            raise LLMUnavailableError(f"Ollama error {response.status_code}: {response.text[:200]}")
        return response.json()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        body = self._post("/api/embed", {"model": self.embed_model, "input": texts})
        return body["embeddings"]

    def chat(self, system: str, user: str) -> str:
        body = self._post(
            "/api/chat",
            {
                "model": self.chat_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": 0.1},
            },
        )
        return body["message"]["content"].strip()

    def status(self) -> dict:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=3)
            response.raise_for_status()
            available = {m["name"].split(":latest")[0] for m in response.json().get("models", [])}
        except (httpx.HTTPError, ValueError, KeyError):
            return {"reachable": False, "missing_models": [self.chat_model, self.embed_model]}
        wanted = [self.chat_model, self.embed_model]
        missing = [m for m in wanted if m not in available and f"{m}:latest" not in available]
        return {"reachable": True, "missing_models": missing}


_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are did does for from had has have how in is it of on or the to was were what "
    "when which who why with my her his their this that any".split()
)


class FakeProvider:
    """Hashed bag-of-words embeddings and an extractive "answer" built from the context."""

    name = "fake"
    chat_model = "fake-extractive"
    embed_model = "fake-hash-256"
    dimensions = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in _TOKEN.findall(text.lower()):
                if token in _STOPWORDS:
                    continue
                bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dimensions
                vector[bucket] += 1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors

    def chat(self, system: str, user: str) -> str:
        excerpts = re.findall(r"\[(\d+)\][^\n]*\n(.+?)(?=\n\[\d+\]|\nQuestion:|\Z)", user, re.S)
        if not excerpts:
            return "I could not find this in the patient's reports."
        number, text = excerpts[0]
        return f"According to the reports: {text.strip()[:300]} [{number}]"

    def status(self) -> dict:
        return {"reachable": True, "missing_models": []}


@lru_cache
def _provider(name: str) -> LLMProvider:
    if name == "fake":
        return FakeProvider()
    if name == "ollama":
        return OllamaProvider(get_settings())
    raise ValueError(f"Unknown CURANEX_LLM_PROVIDER: {name}")


def get_llm() -> LLMProvider:
    """FastAPI dependency."""
    return _provider(get_settings().llm_provider)
