# Sample DeepAgents on Bedrock AgentCore

A LangChain [Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)
agent on AgentCore Runtime, calling Claude through Amazon Bedrock. The agent is
built with `create_deep_agent`, keeps conversation history per Runtime
session, and streams its response.

## What's here

One runtime runs one agent. An agent is an `AgentSpec` (system prompt plus
named tools and skills); the `AGENT_NAME` env var (default `general`) picks
which one.

- `main.py`: `BedrockAgentCoreApp` with an async entrypoint that reads `prompt`
  from the payload, lazily builds the selected agent on first request (cached,
  retried if the build fails), and streams each completed model message back
  as a JSON event of content blocks. An `InMemorySaver` keyed on the Runtime
  session id carries history between turns.
- `agents/`: the registry `AGENTS`, mapping name to `AgentSpec`.
- `harness/`: `AgentSpec`, the builder (`build_agent`, resolves tools and
  stages skills), and the AgentCore Gateway MCP client (SigV4-signed).
- `tools/`: local tools, registered in `LOCAL_TOOLS`.
- `skills/<name>/SKILL.md`: skills, mounted read-only at `/skills/`.
- `model/load.py`: creates the Bedrock chat model with `init_chat_model`.
- `pyproject.toml`: Python dependencies, managed with
  [uv](https://docs.astral.sh/uv/).

The agent also gets the built-in Deep Agents tools (`write_todos`, virtual
filesystem tools, `task`). `execute` is not usable because the default backend
is not a sandbox.

## Develop

Run the agent locally from the project root:

```bash
agentcore dev
agentcore invoke --runtime agent --local --payload '{"prompt":"What is 2 plus 3?"}'
```

If `invoke --local` is unavailable, call the server directly (the port is
printed by `agentcore dev`; 8081 observed):

```bash
curl -N -X POST http://localhost:<port>/invocations -H 'Content-Type: application/json' -d '{"prompt":"..."}'
```

Environment variables for local development go in `agentcore/.env.local`
(gitignored). Set `AGENTCORE_GATEWAY_WEBSEARCHGW_URL` there to use Gateway tools
locally.

## Deploy

```bash
agentcore deploy
agentcore invoke --runtime agent --payload '{"prompt":"Hello!"}'
```

Traces are collected automatically: AgentCore Runtime starts the agent under
`opentelemetry-instrument`, which picks up `opentelemetry-instrumentation-langchain`
from the dependencies.

## Extending

- **New agent.** Add an `AgentSpec` to `agents/__init__.py`. Declare
  the new runtime in `agentcore/agentcore.json` (same `codeLocation: app/agent`
  and `entrypoint: main.py`, different `name`), then give it `AGENT_NAME` in
  `agentcore/cdk/lib/cdk-stack.ts`:
  `runtime('<name>').addEnvironmentVariable('AGENT_NAME', '<spec-name>')`.
  An unknown `AGENT_NAME` fails at startup.
- **Local tool.** Add a `@tool` function under `tools/`, register it in
  `LOCAL_TOOLS`, and list its name in the spec's `tools`.
- **Skill.** Add `skills/<name>/SKILL.md` (with `name`/`description`
  frontmatter) and list `<name>` in the spec's `skills`.
- **Gateway tool.** Put the MCP tool name (e.g. `web-search___WebSearch`)
  directly in the spec's `tools`. The Gateway URL comes from
  `AGENTCORE_GATEWAY_WEBSEARCHGW_URL` (set in `agentcore/.env.local` locally).
- **Durable memory.** Replace `InMemorySaver()` in `harness/builder.py` with
  `AgentCoreMemorySaver` from `langgraph-checkpoint-aws` and add `actor_id`
  next to `thread_id` in the `configurable` config.

See the [Deep Agents documentation](https://docs.langchain.com/oss/python/deepagents/overview)
for the full `create_deep_agent` surface.
