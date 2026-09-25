"""Minimal model execution graph; routing nodes will be added in a later phase."""

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from .base import Generation, LLMProvider, Turn


class ModelState(TypedDict):
    provider: LLMProvider
    messages: list[Turn]
    max_tokens: int
    generation: NotRequired[Generation]


def _generate(state: ModelState):
    return {"generation": state["provider"].generate(state["messages"], max_tokens=state["max_tokens"])}


def _build_graph():
    graph = StateGraph(ModelState)
    graph.add_node("generate", _generate)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", END)
    return graph.compile()


MODEL_GRAPH = _build_graph()


def run_model(provider: LLMProvider, messages: list[Turn], max_tokens: int) -> Generation:
    """Execute an already authorized provider; future routing belongs before generate."""
    state = MODEL_GRAPH.invoke({"provider": provider, "messages": messages, "max_tokens": max_tokens})
    return state["generation"]
