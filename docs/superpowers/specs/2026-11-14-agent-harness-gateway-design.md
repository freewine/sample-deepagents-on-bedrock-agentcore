# Agent Harness + AgentCore Gateway 集成设计

## 意图
把 agent 做成 harness：打造不同的 agent = 组装不同的 tools 和 skills。
首先接入已部署的 AgentCore Gateway `WebSearchGW`（web-search target）。不过度设计。

## 目标 / 非目标
- 目标：AgentSpec 声明式组装 tools + skills；Gateway 工具与本地工具统一按名字引用。
- 目标：一个 runtime 对应一个 agent，通过环境变量 `AGENT_NAME` 选择 spec（默认 `general`）。
- 非目标：subagent 配置、热加载、YAML 配置、多 agent 共用 runtime 路由。

## 约束
- Gateway `authorizerType: AWS_IAM` → 用 SigV4（service `bedrock-agentcore`）签名，而非 OAuth client_credentials。
- CDK 已为 runtime 注入 `AGENTCORE_GATEWAY_WEBSEARCHGW_URL` 与 `InvokeGateway` 权限；本地开发在 `agentcore/.env.local` 设置该 URL。
- Gateway 工具需异步加载 → agent 首次请求时懒构建并缓存。

## 方案（已选：一个 runtime 一个 agent）
- 选项 A（选中）：`AGENT_NAME` 环境变量选 spec；权限、扩缩容、观测按 agent 隔离。
- 选项 B：payload `agent` 字段路由；部署省事但共享 IAM 权限。

## 结构
```
app/agent/
  main.py              # 入口：按 AGENT_NAME 懒构建 agent、流式输出
  harness/spec.py      # AgentSpec(name, system_prompt, tools, skills)
  harness/gateway.py   # SigV4 httpx.Auth + langchain-mcp-adapters 拉取 Gateway 工具（缓存）
  harness/builder.py   # build_agent(spec)：解析工具名（本地优先，其次 Gateway；缺失报错）、skills → create_deep_agent
  tools/__init__.py    # 本地 @tool 注册表
  skills/web-research/SKILL.md
  agents/__init__.py   # AGENTS = {"general": AgentSpec(...)}
```
- Skills：`CompositeBackend(default=StateBackend, routes={"/skills/": 只读 FilesystemBackend(skills 目录)})`。
- 新增依赖：`langchain-mcp-adapters`。
- 未设置 Gateway URL 时：spec 引用了 Gateway 工具则报清晰错误。

## 留给实施者
- 确认 langchain-mcp-adapters 的分页处理与 auth 参数；FilesystemBackend 的只读/虚拟路径参数。
