from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    name: str
    system_prompt: str
    tools: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
