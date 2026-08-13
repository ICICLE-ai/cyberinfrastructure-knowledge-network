"""Smoke coverage for llm_graph.py's LangGraph RAG workflow. util.graph/util.llm are mocked
(see conftest.py), so router/cypher-generation/answer-generation chains are all built on top of
MagicMocks -- this doesn't exercise real LLM reasoning, just confirms the graph wires together
and that run_langraph()'s success and error paths behave as written.
"""

from unittest.mock import MagicMock

import llm_graph


def test_workflow_compiles_to_a_runnable_app():
    assert llm_graph.app is not None
    assert hasattr(llm_graph.app, "stream")


def test_run_langraph_returns_generated_answer_on_success(monkeypatch):
    # CompiledStateGraph is a strict Pydantic model -- monkeypatching an attribute directly
    # onto the real instance raises ValueError ("no field 'stream'"). Replace the module-level
    # `app` name with a lightweight stand-in instead.
    def fake_stream(_inputs):
        yield {"gen_human_response": {"generated_answer": "The answer is 42."}}

    fake_app = MagicMock()
    fake_app.stream = fake_stream
    monkeypatch.setattr(llm_graph, "app", fake_app)

    result = llm_graph.run_langraph("How many experiments ran?", chat_history="")

    assert result == "The answer is 42."


def test_run_langraph_catches_exceptions_and_returns_friendly_message(monkeypatch):
    def raising_stream(_inputs):
        raise RuntimeError("graph execution failed")
        yield  # pragma: no cover - unreachable, makes this a generator function

    fake_app = MagicMock()
    fake_app.stream = raising_stream
    monkeypatch.setattr(llm_graph, "app", fake_app)

    result = llm_graph.run_langraph("How many experiments ran?", chat_history="")

    assert result == "There was an error generating the query."
