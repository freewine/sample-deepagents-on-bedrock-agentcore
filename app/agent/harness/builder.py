"""Build a deep agent from an AgentSpec (named tools + skills)."""

import shutil
import tempfile
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver

from harness.gateway import load_gateway_tools
from harness.spec import AgentSpec
from model.load import load_model
from tools import LOCAL_TOOLS

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


async def resolve_tools(
    names: Sequence[str],
    local: Mapping[str, BaseTool],
    gateway_loader: Callable[[], Awaitable[list[BaseTool]]],
) -> list[BaseTool]:
    pool: dict[str, BaseTool] = {n: local[n] for n in names if n in local}
    if any(n not in pool for n in names):
        for t in await gateway_loader():
            pool.setdefault(t.name, t)
        pool = {**pool, **{n: local[n] for n in names if n in local}}
    missing = [n for n in names if n not in pool]
    if missing:
        available = sorted(set(local) | set(pool))
        raise ValueError(f"Unknown tools: {missing}. Available: {available}")
    return [pool[n] for n in names]


def stage_skills(names: Sequence[str], skills_dir: Path = SKILLS_DIR) -> Path | None:
    if not names:
        return None
    missing = [n for n in names if not (skills_dir / n).is_dir()]
    if missing:
        available = sorted(p.name for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []
        raise ValueError(f"Unknown skills: {missing}. Available: {available}")
    staged = Path(tempfile.mkdtemp())
    for n in names:
        shutil.copytree(skills_dir / n, staged / n)
    return staged


async def build_agent(spec: AgentSpec, *, model=None, gateway_loader=load_gateway_tools):
    tools = await resolve_tools(spec.tools, LOCAL_TOOLS, gateway_loader)
    kwargs = {}
    staged = stage_skills(spec.skills)
    if staged is not None:
        kwargs = {
            "backend": CompositeBackend(
                default=StateBackend(),
                routes={"/skills/": FilesystemBackend(root_dir=staged, virtual_mode=True)},
            ),
            "skills": ["/skills/"],
            "permissions": [
                FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny")
            ],
        }
    return create_deep_agent(
        model=model or load_model(),
        tools=tools,
        system_prompt=spec.system_prompt,
        checkpointer=InMemorySaver(),
        name=spec.name,
        **kwargs,
    )
