from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agents import call_agent, call_synthesis, PRAGMATIST_PROMPT, PURIST_PROMPT, OPERATOR_PROMPT


class ReviewState(TypedDict):
    code: str
    pragmatist: list
    purist: list
    operator: list
    synthesis: dict


def pragmatist_node(state: ReviewState) -> dict:
    return {"pragmatist": call_agent(PRAGMATIST_PROMPT, state["code"])}


def purist_node(state: ReviewState) -> dict:
    return {"purist": call_agent(PURIST_PROMPT, state["code"])}


def operator_node(state: ReviewState) -> dict:
    return {"operator": call_agent(OPERATOR_PROMPT, state["code"])}


def synthesis_node(state: ReviewState) -> dict:
    return {"synthesis": call_synthesis(state["pragmatist"], state["purist"], state["operator"])}


def build_graph():
    g = StateGraph(ReviewState)
    g.add_node("pragmatist", pragmatist_node)
    g.add_node("purist", purist_node)
    g.add_node("operator", operator_node)
    g.add_node("synthesis", synthesis_node)
    # Fan-out: all three reviewers start simultaneously
    g.add_edge(START, "pragmatist")
    g.add_edge(START, "purist")
    g.add_edge(START, "operator")
    # Fan-in: synthesis waits for all three before running
    g.add_edge("pragmatist", "synthesis")
    g.add_edge("purist", "synthesis")
    g.add_edge("operator", "synthesis")
    g.add_edge("synthesis", END)
    return g.compile()


graph = build_graph()
