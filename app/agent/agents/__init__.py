"""Agent registry: one AgentSpec per agent, selected at runtime by AGENT_NAME."""

from harness.spec import AgentSpec

AGENTS: dict[str, AgentSpec] = {
    "general": AgentSpec(
        name="general",
        system_prompt=(
            "You are a helpful assistant. Use tools when appropriate. "
            "You can search the web with the web-search___WebSearch tool for current "
            "events and up-to-date information. When you use web results, cite your "
            "sources by including the links in your answer."
        ),
        tools=("add_numbers", "web-search___WebSearch"),
        skills=("web-research",),
    ),
}
