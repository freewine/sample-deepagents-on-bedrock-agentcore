# Sample DeepAgents

A sample [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)
application running on Amazon Bedrock AgentCore. It uses Claude through Amazon
Bedrock, searches the web through an IAM-authenticated AgentCore Gateway, and
streams model responses.

The default `general` agent includes an arithmetic tool and a web-research skill.
Each Runtime session maps to a LangGraph thread, with deployed conversation state
stored in DynamoDB and large checkpoints offloaded to S3.

## Repository Structure

| Path | Purpose |
| --- | --- |
| `app/agent/main.py` | Runtime entry point and response streaming |
| `app/agent/agents/` | Named agent specifications |
| `app/agent/harness/` | Agent construction, Gateway client, and checkpoint storage |
| `app/agent/tools/` | Local tool registry |
| `app/agent/skills/` | Agent skills defined in `SKILL.md` files |
| `app/agent/model/` | Bedrock model configuration |
| `app/agent/tests/` | Python unit tests |
| `agentcore/agentcore.json` | Runtime and Gateway declarations |
| `agentcore/cdk/` | AWS CDK infrastructure |

## Prerequisites

- Python 3.14+ and [uv](https://docs.astral.sh/uv/).
- Node.js and npm for the CDK application.
- The AgentCore CLI, providing the `agentcore` command.
- AWS credentials and a region configured for Bedrock and AgentCore, with access
  to the model configured in [model/load.py](app/agent/model/load.py).
- A deployed web-search Gateway for the default agent, including during local
  development.

## Setup

Install dependencies from the repository root:

```bash
uv sync --project app/agent
npm ci --prefix agentcore/cdk
```

Create `agentcore/.env.local` with your local configuration:

```dotenv
AWS_REGION=us-east-1
AGENTCORE_GATEWAY_WEBSEARCHGW_URL=https://<gateway-host>/mcp
```

Replace the region and Gateway URL with your deployment's values. Keep credentials
out of committed files. The default agent loads its Gateway tools when first
built, so a missing or inaccessible Gateway prevents requests from succeeding.
To develop without Gateway tools, remove the Gateway tool from the selected
agent specification.

## Run Locally

From the repository root:

```bash
agentcore dev
```

In another terminal:

```bash
agentcore invoke --runtime agent --local --payload '{"prompt":"What is 2 plus 3?"}'
```

Requests require a non-empty `prompt` and a Runtime session ID. The session ID
identifies the conversation's checkpoint thread. Responses stream as JSON events
containing model content blocks.

Without `CHECKPOINT_TABLE`, local development uses in-memory checkpoints and
loses history on restart. Set `CHECKPOINT_TABLE` and `CHECKPOINT_BUCKET` in
`agentcore/.env.local` to use deployed storage.

## Test and Build

Run these commands from the repository root:

```bash
uv run --project app/agent pytest app/agent/tests
npm run build --prefix agentcore/cdk
agentcore build
```

These run the pytest suite, compile and type-check the CDK application, and
synthesize CloudFormation templates, respectively. Unit tests use fakes and
mocks for external services.

## Deploy

Review the runtime, Gateway, and CDK configuration for your AWS target, then run:

```bash
agentcore deploy
agentcore status
agentcore invoke --runtime agent --payload '{"prompt":"Find recent news about Amazon Bedrock."}'
```

Deployment creates AWS resources, including checkpoint storage and observability
resources. The checkpoint table and bucket use retention policies. Checkpoints
do not expire by default; read the
[checkpoint documentation](app/agent/README.md#state) before enabling TTL.

## Extend and Contribute

Register agents in `app/agent/agents/__init__.py`, local tools in `LOCAL_TOOLS`,
and skills under `app/agent/skills/<name>/SKILL.md`. `AGENT_NAME` selects the agent
specification and defaults to `general`.

See the [agent guide](app/agent/README.md) for runtime behavior and extension
instructions, the [CDK guide](agentcore/cdk/README.md) for infrastructure changes,
and [Repository Guidelines](AGENTS.md) for contributor conventions.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](./LICENSE) for
the full text.