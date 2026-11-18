# Repository Guidelines

## Project Structure & Module Organization

- `app/agent/` contains the Python LangChain Deep Agents runtime. `main.py` handles requests and streaming; `harness/` builds agents, connects Gateway tools, and configures checkpoints.
- `app/agent/agents/` registers agent specifications; `tools/` registers local tools; `model/` configures the Bedrock model. Skills live in `skills/<name>/SKILL.md`.
- `app/agent/tests/` contains unit tests.
- `agentcore/agentcore.json` declares deployment resources. `agentcore/cdk/lib/cdk-stack.ts` defines custom AWS infrastructure; `bin/cdk.ts` is the CDK entry point.

## Build, Test, and Development Commands

Use Python 3.14+, uv, Node.js/npm, and the AgentCore CLI.

From `app/agent/`:

- `uv sync` installs locked Python dependencies, including pytest.
- `uv run pytest` runs the test suite.
- `uv run pytest tests/test_builder.py` runs focused builder tests.

From `agentcore/cdk/`:

- `npm ci` installs locked Node dependencies.
- `npm run build` compiles and type-checks TypeScript.

From the repository root:

- `agentcore dev` starts the local runtime.
- `agentcore invoke --runtime agent --local --payload '{"prompt":"Hello!"}'` exercises it locally.
- `agentcore build` synthesizes CloudFormation templates.
- `agentcore deploy` deploys resources to AWS; review infrastructure changes first.

## Coding Style & Naming Conventions

Follow existing code: Python uses four-space indentation, snake_case functions/modules, PascalCase classes, and uppercase registry constants. Add type hints to interfaces. TypeScript uses two-space indentation, single quotes, semicolons, and strict compiler checks. No formatter or linter is configured. Register new tools in `LOCAL_TOOLS` and agents in `AGENTS`; use descriptive skill directory names such as `web-research`.

## Testing Guidelines

Use pytest with `test_*.py` files and `test_*` functions. Follow existing fake-model, monkeypatch, and `asyncio.run` patterns to avoid live AWS calls in unit tests. Cover changed behavior and failure paths, especially tool resolution, session handling, and checkpoint selection. No coverage threshold is configured. Run pytest for Python changes and the TypeScript build for CDK changes.

## Commit & Pull Request Guidelines

History uses Conventional Commit prefixes such as `feat:` and `docs:` with concise imperative summaries. Follow that pattern. PRs should describe behavior changes, link relevant issues, and list validation commands/results. Explain AWS resource, IAM, and configuration changes explicitly.

## Security & Configuration

Keep local settings in gitignored `agentcore/.env.local`; never commit credentials. Without `CHECKPOINT_TABLE`, local state uses an in-memory saver. Review session-lifetime constraints in `app/agent/README.md` before enabling checkpoint TTL.
