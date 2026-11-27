"""LangGraph workflow that routes a free-form question to the right capability.

    route ──► reports  ──┐
          ├─► risk     ──┤
          ├─► vitals   ──┼─► compose ──► END
          └─► overview ──┘   (overview runs risk + vitals + a report summary)

Only the router and the report Q&A use the LLM. Risk and vitals answers are rendered from
stored data with fixed templates, so numbers in those answers can never be hallucinated.
"""

import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.db.models import Patient
from app.rag import service as rag
from app.rag.llm import LLMProvider
from app.services import predictions as prediction_service
from app.services import vitals as vitals_service

Intent = Literal["reports", "risk", "vitals", "overview"]
INTENTS: tuple[str, ...] = ("reports", "risk", "vitals", "overview")

ROUTER_PROMPT = """Classify the user's question about a patient into exactly one category:
- risk: diabetes risk score, prediction, likelihood of developing diabetes
- vitals: blood pressure, heart rate, glucose readings, SpO2, temperature, weight, trends, alerts
- reports: anything in uploaded lab reports or documents (results, medications, advice)
- overview: a general summary of the patient's status, or several of the above
Reply with the single category word only."""

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "overview": (
        "overview",
        "summary",
        "summarise",
        "summarize",
        "overall",
        "everything",
        "status",
        "how is",
    ),
    "risk": ("risk", "prediction", "predict", "likelihood", "chance", "probability", "score"),
    "vitals": (
        "vital",
        "blood pressure",
        " bp",
        "heart rate",
        "pulse",
        "spo2",
        "oxygen",
        "temperature",
        "weight",
        "trend",
        "alert",
        "reading",
    ),
}


class AgentState(TypedDict, total=False):
    question: str
    intent: Intent
    router: str  # "llm" or "keywords"
    sections: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    answer: str
    steps: list[str]


def keyword_intent(question: str) -> Intent:
    text = f" {question.lower()} "
    for intent in ("overview", "risk", "vitals"):
        if any(keyword in text for keyword in _KEYWORDS[intent]):
            return intent  # type: ignore[return-value]
    return "reports"


def _parse_intent(reply: str) -> Intent | None:
    """Accept only a reply that is (essentially) one category word."""
    words = re.findall(r"[a-z]+", reply.lower())
    if not words or len(words) > 3 or words[0] not in INTENTS:
        return None
    return words[0]  # type: ignore[return-value]


def _risk_section(db: Session, patient: Patient) -> dict:
    history = prediction_service.list_for_patient(db, patient.id, limit=2)
    if not history:
        text = "No diabetes risk prediction has been run for this patient yet."
    else:
        latest = history[0]
        top = [c for c in latest.contributions if c["impact"] > 0][:3]
        drivers = ", ".join(
            f"{c['label']} ({c['value']:g})"
            if c["value"] is not None
            else f"{c['label']} (not measured)"
            for c in top
        )
        text = (
            f"Latest diabetes risk: {latest.probability:.0%} ({latest.risk_level}), "
            f"from {latest.created_at:%Y-%m-%d}."
        )
        if drivers:
            text += f" Main factors raising it: {drivers}."
        if len(history) > 1:
            change = latest.probability - history[1].probability
            text += f" Change since the previous prediction: {change:+.0%}."
    return {"title": "Diabetes risk", "text": text}


def _vitals_section(db: Session, patient: Patient) -> dict:
    analysis = vitals_service.analyse(db, patient.id, days=30)
    if analysis["readings"] == 0:
        return {"title": "Vitals (30 days)", "text": "No vitals recorded in the last 30 days."}
    parts = []
    for metric in analysis["metrics"]:
        if not metric["readings"]:
            continue
        line = f"{metric['label']} {metric['latest']:g} {metric['unit']} ({metric['status']})"
        if metric["trend_per_30d"] is not None and metric["trend_r2"] and metric["trend_r2"] > 0.3:
            line += f", trend {metric['trend_per_30d']:+.1f}/30d"
        parts.append(line)
    text = f"{analysis['readings']} readings. Latest: " + "; ".join(parts) + "."
    if analysis["alerts"]:
        text += " Alerts: " + " ".join(analysis["alerts"])
    else:
        text += " No alerts."
    return {"title": "Vitals (30 days)", "text": text}


def build_graph(db: Session, patient: Patient, llm: LLMProvider):
    """Compile a graph bound to one request's DB session, patient and LLM."""

    def route(state: AgentState) -> AgentState:
        steps = [*state.get("steps", [])]
        intent: Intent | None = None
        try:
            intent = _parse_intent(llm.chat(ROUTER_PROMPT, state["question"]))
        except Exception:  # router failures fall back to keywords, never fail the request
            intent = None
        if intent:
            steps.append(f"route: LLM chose '{intent}'")
            return {"intent": intent, "router": "llm", "steps": steps}
        intent = keyword_intent(state["question"])
        steps.append(f"route: keyword fallback chose '{intent}'")
        return {"intent": intent, "router": "keywords", "steps": steps}

    def reports(state: AgentState) -> AgentState:
        answer = rag.ask(db, patient, state["question"], llm)
        return {
            "sections": [{"title": "From the reports", "text": answer.answer}],
            "citations": [c.__dict__ for c in answer.citations],
            "steps": [*state["steps"], f"reports: searched {answer.reports_searched} report(s)"],
        }

    def risk(state: AgentState) -> AgentState:
        return {
            "sections": [_risk_section(db, patient)],
            "steps": [*state["steps"], "risk: read latest stored prediction"],
        }

    def vitals(state: AgentState) -> AgentState:
        return {
            "sections": [_vitals_section(db, patient)],
            "steps": [*state["steps"], "vitals: analysed last 30 days"],
        }

    def overview(state: AgentState) -> AgentState:
        summary = rag.ask(db, patient, "Which results in the reports are flagged abnormal?", llm)
        return {
            "sections": [
                _risk_section(db, patient),
                _vitals_section(db, patient),
                {"title": "From the reports", "text": summary.answer},
            ],
            "citations": [c.__dict__ for c in summary.citations],
            "steps": [*state["steps"], "overview: risk + vitals + report summary"],
        }

    def compose(state: AgentState) -> AgentState:
        sections = state.get("sections", [])
        if len(sections) == 1:
            answer = sections[0]["text"]
        else:
            answer = "\n\n".join(f"**{s['title']}**: {s['text']}" for s in sections)
        return {
            "answer": answer,
            "citations": state.get("citations", []),
            "steps": [*state["steps"], "compose"],
        }

    graph = StateGraph(AgentState)
    graph.add_node("route", route)
    for name, node in (
        ("reports", reports),
        ("risk", risk),
        ("vitals", vitals),
        ("overview", overview),
    ):
        graph.add_node(name, node)
        graph.add_edge(name, "compose")
    graph.add_node("compose", compose)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", lambda state: state["intent"], list(INTENTS))
    graph.add_edge("compose", END)
    return graph.compile()


def run_agent(db: Session, patient: Patient, question: str, llm: LLMProvider) -> AgentState:
    return build_graph(db, patient, llm).invoke({"question": question, "steps": []})
