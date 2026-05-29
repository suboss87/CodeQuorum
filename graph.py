from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agents import call_agent, call_synthesis, PRAGMATIST_PROMPT, PURIST_PROMPT, OPERATOR_PROMPT

REVIEWER_AGENTS = [
    ("pragmatist", PRAGMATIST_PROMPT),
    ("purist",     PURIST_PROMPT),
    ("operator",   OPERATOR_PROMPT),
]


class ReviewState(TypedDict):
    code: str
    pragmatist: list
    purist: list
    operator: list
    synthesis: dict


def agents_node(state: ReviewState) -> dict:
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {name: pool.submit(call_agent, prompt, state["code"]) for name, prompt in REVIEWER_AGENTS}
        return {name: f.result() for name, f in futures.items()}


def synthesis_node(state: ReviewState) -> dict:
    return {"synthesis": call_synthesis(state["pragmatist"], state["purist"], state["operator"])}


def build_graph():
    g = StateGraph(ReviewState)
    g.add_node("agents", agents_node)
    g.add_node("synthesis", synthesis_node)
    g.add_edge(START, "agents")
    g.add_edge("agents", "synthesis")
    g.add_edge("synthesis", END)
    return g.compile()


graph = build_graph()
