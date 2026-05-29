from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agents import call_agent, call_synthesis, PRAGMATIST_PROMPT, PURIST_PROMPT, OPERATOR_PROMPT, DEFAULT_MODEL

REVIEWER_AGENTS = [
    ("pragmatist", PRAGMATIST_PROMPT),
    ("purist",     PURIST_PROMPT),
    ("operator",   OPERATOR_PROMPT),
]


class ReviewState(TypedDict):
    code: str
    model: str
    pragmatist: list
    purist: list
    operator: list
    synthesis: dict


def agents_node(state: ReviewState) -> dict:
    model = state.get("model", DEFAULT_MODEL)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            name: pool.submit(call_agent, prompt, state["code"], model)
            for name, prompt in REVIEWER_AGENTS
        }
        return {name: f.result() for name, f in futures.items()}


def synthesis_node(state: ReviewState) -> dict:
    model = state.get("model", DEFAULT_MODEL)
    return {"synthesis": call_synthesis(state["pragmatist"], state["purist"], state["operator"], model)}


def build_graph():
    g = StateGraph(ReviewState)
    g.add_node("agents", agents_node)
    g.add_node("synthesis", synthesis_node)
    g.add_edge(START, "agents")
    g.add_edge("agents", "synthesis")
    g.add_edge("synthesis", END)
    return g.compile()


graph = build_graph()
