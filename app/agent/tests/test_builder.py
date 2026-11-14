import asyncio

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from harness.builder import build_agent, resolve_tools, stage_skills
from harness.spec import AgentSpec
from tools import LOCAL_TOOLS


@tool
def _gw(q: str) -> str:
    """gw"""
    return q


_gw.name = "web-search___WebSearch"


def make_loader():
    calls = []

    async def loader():
        calls.append(1)
        return [_gw]

    return loader, calls


def test_resolve_local_only_skips_gateway():
    loader, calls = make_loader()
    out = asyncio.run(resolve_tools(["add_numbers"], LOCAL_TOOLS, loader))
    assert [t.name for t in out] == ["add_numbers"]
    assert calls == []


def test_resolve_gateway_tool():
    loader, calls = make_loader()
    out = asyncio.run(
        resolve_tools(["add_numbers", "web-search___WebSearch"], LOCAL_TOOLS, loader)
    )
    assert [t.name for t in out] == ["add_numbers", "web-search___WebSearch"]
    assert len(calls) == 1


def test_resolve_unknown_tool_raises():
    loader, _ = make_loader()
    with pytest.raises(ValueError) as e:
        asyncio.run(resolve_tools(["nope"], LOCAL_TOOLS, loader))
    assert "nope" in str(e.value) and "add_numbers" in str(e.value)


def test_stage_skills_copies_only_selected(tmp_path):
    for n in ("a", "b"):
        (tmp_path / n).mkdir()
        (tmp_path / n / "SKILL.md").write_text("x")
    staged = stage_skills(["a"], tmp_path)
    assert sorted(p.name for p in staged.iterdir()) == ["a"]
    assert stage_skills([], tmp_path) is None


def test_stage_skills_unknown_raises(tmp_path):
    with pytest.raises(ValueError, match="zzz"):
        stage_skills(["zzz"], tmp_path)


def test_build_agent_smoke():
    fake = GenericFakeChatModel(messages=iter([AIMessage("hi")]))
    agent = asyncio.run(
        build_agent(AgentSpec("t", "p", tools=("add_numbers",)), model=fake)
    )
    assert hasattr(agent, "ainvoke")


def test_build_agent_with_skills(tmp_path, monkeypatch):
    (tmp_path / "s").mkdir()
    (tmp_path / "s" / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\nbody\n")
    import harness.builder as b

    monkeypatch.setattr(b, "SKILLS_DIR", tmp_path)
    monkeypatch.setattr(b, "stage_skills", lambda names: stage_skills(names, tmp_path))
    fake = GenericFakeChatModel(messages=iter([AIMessage("hi")]))
    agent = asyncio.run(b.build_agent(AgentSpec("t", "p", skills=("s",)), model=fake))
    assert hasattr(agent, "ainvoke")
