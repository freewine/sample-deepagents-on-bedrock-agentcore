import asyncio
import importlib
from types import SimpleNamespace

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import main
from harness.builder import build_agent
from harness.spec import AgentSpec


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    main._agent = None
    monkeypatch.setattr(main, "_lock", asyncio.Lock())
    monkeypatch.delenv("AGENT_NAME", raising=False)
    yield
    main._agent = None


def test_get_spec_default():
    assert main.get_spec().name == "general"


def test_get_spec_unknown_lists_available():
    with pytest.raises(ValueError, match="general"):
        main.get_spec("nope")


def test_unknown_agent_name_fails_at_import(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "nope")
    with pytest.raises(ValueError, match="nope"):
        importlib.reload(main)
    monkeypatch.delenv("AGENT_NAME")
    importlib.reload(main)


def test_get_agent_builds_once_concurrently(monkeypatch):
    calls = []

    async def fake_build(spec, **kwargs):
        calls.append(spec)
        await asyncio.sleep(0.01)
        return object()

    monkeypatch.setattr(main, "build_agent", fake_build)

    async def run():
        return await asyncio.gather(*[main.get_agent() for _ in range(5)])

    results = asyncio.run(run())
    assert len(calls) == 1
    assert all(r is results[0] for r in results)


def test_get_agent_retries_after_failure(monkeypatch):
    calls = []
    agent = object()

    async def fake_build(spec, **kwargs):
        calls.append(spec)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return agent

    monkeypatch.setattr(main, "build_agent", fake_build)

    async def run():
        with pytest.raises(RuntimeError):
            await main.get_agent()
        return await main.get_agent()

    assert asyncio.run(run()) is agent
    assert len(calls) == 2


def collect(payload, context):
    async def run():
        return [e async for e in main.invoke(payload, context)]

    return asyncio.run(run())


def ctx(session_id="s" * 33):
    return SimpleNamespace(session_id=session_id, request_headers=None)


def test_invoke_requires_session_id(monkeypatch):
    monkeypatch.setattr(main, "get_agent", None)  # must not be reached
    out = collect({"prompt": "hi"}, ctx(session_id=None))
    assert out == [{"error": "missing runtime session id"}]


def test_invoke_end_to_end_persists_thread(monkeypatch):
    class Model(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    agent = asyncio.run(
        build_agent(
            AgentSpec("t", "p"),
            model=Model(messages=iter([AIMessage("answer")])),
        )
    )

    async def fake_get_agent():
        return agent

    monkeypatch.setattr(main, "get_agent", fake_get_agent)
    session = "s" * 33
    out = collect({"prompt": "hello"}, ctx(session_id=session))
    assert any(b.get("text") == "answer" for e in out for b in e.get("content", []))
    state = asyncio.run(agent.aget_state({"configurable": {"thread_id": session}}))
    assert [m.text for m in state.values["messages"]] == ["hello", "answer"]
