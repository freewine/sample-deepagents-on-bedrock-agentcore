import asyncio

import pytest

import main


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
    import importlib

    monkeypatch.setenv("AGENT_NAME", "nope")
    with pytest.raises(ValueError, match="nope"):
        importlib.reload(main)
    monkeypatch.delenv("AGENT_NAME")
    importlib.reload(main)


def test_get_agent_builds_once_concurrently(monkeypatch):
    calls = []

    async def fake_build(spec):
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

    async def fake_build(spec):
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
