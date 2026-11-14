import asyncio
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agents import AGENTS
from harness.builder import build_agent
from harness.spec import AgentSpec

app = BedrockAgentCoreApp()

_agent = None
_lock = asyncio.Lock()


def get_spec(name: str | None = None) -> AgentSpec:
    name = name or os.environ.get("AGENT_NAME", "general")
    try:
        return AGENTS[name]
    except KeyError:
        raise ValueError(f"Unknown agent {name!r}. Available: {sorted(AGENTS)}") from None


SPEC = get_spec()  # fail fast on an unknown AGENT_NAME


async def get_agent():
    global _agent
    if _agent is None:
        async with _lock:
            if _agent is None:
                _agent = await build_agent(SPEC)
    return _agent


@app.entrypoint
async def invoke(payload, context):
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not prompt:
        yield {"error": "payload must be a JSON object with a non-empty string 'prompt'"}
        return

    agent = await get_agent()
    session_id = context.session_id or "default-session"
    config = {"configurable": {"thread_id": session_id}}

    async with await agent.astream_events(
        {"messages": [{"role": "user", "content": prompt}]},
        config,
        version="v3",
    ) as stream:
        async for message in stream.messages:
            blocks = (await message.output).content_blocks
            if blocks:
                yield {"node": message.node, "content": blocks}


if __name__ == "__main__":
    app.run()
