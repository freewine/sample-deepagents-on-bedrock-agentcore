# Sample DeepAgents on Bedrock AgentCore

A LangChain [Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)
agent on AgentCore Runtime, calling Claude through Amazon Bedrock. The agent is
built with `create_deep_agent`, keeps conversation history per Runtime
session, and streams its response.

## What's here

- `main.py`: the agent, built with `deepagents.create_deep_agent`. Besides the
  custom tools it gets the built-in Deep Agents tools: `write_todos` (planning),
  `ls`/`read_file`/`write_file`/`edit_file`/`glob`/`grep` (on the default
  `StateBackend`, a virtual filesystem kept in the session's graph state, not
  the container disk) and `task` (general-purpose subagent). `execute` is not
  usable because the default backend is not a sandbox. A `BedrockAgentCoreApp` wraps an async entrypoint
  that reads `prompt` from the payload, runs the agent, and streams each
  completed model message back as a JSON event of content blocks. An
  `InMemorySaver` checkpointer keyed on the Runtime session id carries history
  between turns.
- `model/load.py`: creates the Bedrock chat model with `init_chat_model`.
- `pyproject.toml`: Python dependencies, managed with
  [uv](https://docs.astral.sh/uv/). `agentcore create` has already run
  `uv sync` for you (unless you passed `--skip-install`), so `.venv/` is ready.

## Develop

Run the agent locally from the project root:

```bash
agentcore dev
agentcore invoke --runtime agent --local --payload '{"prompt":"What is 2 plus 3?"}'
```

Environment variables for local development go in `agentcore/.env.local`
(gitignored).

## Deploy

```bash
agentcore deploy
agentcore invoke --runtime agent --payload '{"prompt":"Hello!"}'
```

Traces are collected automatically: AgentCore Runtime starts the agent under
`opentelemetry-instrument`, which picks up `opentelemetry-instrumentation-langchain`
from the dependencies.

## Extending

Everything hangs off the `create_deep_agent` call in `main.py`.

- **Tools.** Add a function decorated with `@tool` and append it to `tools`.
- **Subagents.** Pass `subagents=[{"name": ..., "description": ..., "system_prompt": ..., "tools": [...]}]`
  to add specialised subagents the main agent can delegate to via `task`.
- **Filesystem backend.** Pass `backend=` (e.g. `FilesystemBackend`, `StoreBackend`,
  `CompositeBackend` from `deepagents.backends`) to change where files live; use a
  sandbox backend to enable `execute`.
- **Middleware.** Pass extra `langchain.agents.middleware` hooks as `middleware=[...]`.
- **Durable memory.** Replace `InMemorySaver()` with `AgentCoreMemorySaver`
  from `langgraph-checkpoint-aws` and add `actor_id` next to `thread_id` in the
  `configurable` config to persist history in AgentCore Memory.
- **Structured output.** Pass a Pydantic model as `response_format=` and read
  `structured_response` from the final state.

See the [Deep Agents documentation](https://docs.langchain.com/oss/python/deepagents/overview)
for the full `create_deep_agent` surface.
