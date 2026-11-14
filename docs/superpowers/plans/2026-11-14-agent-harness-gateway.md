# Agent Harness + Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 agent 改造成 harness（AgentSpec 组装 tools + skills），并接入 AgentCore Gateway `WebSearchGW` 的 web-search 工具。

**Architecture:** `AgentSpec` 声明 tools/skills 名字；`builder` 先查本地工具注册表、再查 Gateway 工具（经 SigV4 签名的 MCP streamable HTTP，`langchain-mcp-adapters` 加载）；选中的 skills 复制到临时目录，用 `CompositeBackend` 把 `/skills/` 路由过去。`main.py` 按 `AGENT_NAME` 在首次请求时懒构建 agent 并缓存。

**Tech Stack:** Python 3.14, deepagents 0.7.38, langchain-mcp-adapters (~= 0.3.2), botocore SigV4, httpx, bedrock-agentcore, pytest。

**Spec:** `docs/superpowers/specs/2026-11-14-agent-harness-gateway-design.md`

## Global Constraints

- 所有代码在 `app/agent/`，模块以该目录为根导入（`from harness.spec import AgentSpec`）；命令都在 `app/agent/` 下执行。
- Gateway 认证：SigV4，service `bedrock-agentcore`，region 从 URL host 解析（`*.gateway.bedrock-agentcore.<region>.amazonaws.com`）。不使用 OAuth。
- Gateway URL 环境变量：`AGENTCORE_GATEWAY_WEBSEARCHGW_URL`。
- Agent 选择环境变量：`AGENT_NAME`，默认 `general`。
- `/skills/` 对 agent 只读：`FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny")`。
- 工作区里 `agentcore/` 下有用户已 staged 的改动，**不得混入提交**：每次提交用 `git commit -m ... -- <paths>`。
- 不要写 `agentcore/.env.local` 以外的密钥；`.env.local` 已 gitignore。

## Review Focus

1. spec 引用了 Gateway 工具但未设置 `AGENTCORE_GATEWAY_WEBSEARCHGW_URL` → 抛出带变量名的明确错误（Task 2 测试）。
2. spec 引用不存在的工具/skill 名 → `ValueError`，消息含缺失名字和可用名字（Task 3 测试）。
3. `AGENT_NAME` 不存在 → 错误消息列出可用 agent（Task 4 测试）。
4. 并发的首批请求 → agent 只构建一次（`asyncio.Lock`）（Task 4 测试）。
5. 首次构建失败（Gateway 不可达）→ 不缓存失败结果，下次请求重试（Task 4 测试）。

---

### Task 1: 依赖、测试基建、AgentSpec、本地工具注册表

**Files:**
- Modify: `app/agent/pyproject.toml`
- Create: `app/agent/harness/__init__.py`（空）, `app/agent/harness/spec.py`, `app/agent/tools/__init__.py`, `app/agent/tests/__init__.py`（空）, `app/agent/tests/test_spec.py`
- Modify: `app/agent/main.py`（删除 `add_numbers`，改为 `from tools import LOCAL_TOOLS`；其余暂不动）

**Interfaces:**
- Produces: `@dataclass(frozen=True) class AgentSpec: name: str; system_prompt: str; tools: tuple[str, ...] = (); skills: tuple[str, ...] = ()`
- Produces: `tools.LOCAL_TOOLS: dict[str, BaseTool]`，包含 `add_numbers`（从 main.py 原样迁移）。

- [ ] **Step 1:** pyproject 加依赖 `"langchain-mcp-adapters ~= 0.3.2"`，加 `[dependency-groups] dev = ["pytest"]` 和 `[tool.pytest.ini_options] pythonpath = ["."]`；运行 `uv sync`，预期成功。
- [ ] **Step 2: 写测试** `tests/test_spec.py`：
  - `test_local_tools_registry`: `assert LOCAL_TOOLS["add_numbers"].invoke({"a": 2, "b": 3}) == 5`
  - `test_spec_defaults`: `AgentSpec(name="x", system_prompt="p").tools == ()` 且 `.skills == ()`
- [ ] **Step 3:** `uv run pytest tests/test_spec.py -v` → FAIL（模块不存在）。
- [ ] **Step 4:** 实现 `harness/spec.py`、`tools/__init__.py`，修改 main.py 引用 `list(LOCAL_TOOLS.values())`。
- [ ] **Step 5:** `uv run pytest -v` → PASS；`uv run python -c "import main"` 不报错。
- [ ] **Step 6:** 提交 `git add` 上述文件 + `uv.lock`；`git commit -m "feat: add AgentSpec and local tool registry" -- app/agent`

### Task 2: Gateway 客户端（SigV4 + 工具加载）

**Files:**
- Create: `app/agent/harness/gateway.py`, `app/agent/tests/test_gateway.py`

**Interfaces:**
- Produces: `class SigV4Auth(httpx.Auth)`，`__init__(self, region: str, service: str = "bedrock-agentcore")`；`auth_flow` 用 `botocore.session.get_session().get_credentials()` 和 `botocore.auth.SigV4Auth` 对 method/url/headers/body 签名，把签名后的 headers（`Authorization`, `X-Amz-Date`, 有则 `X-Amz-Security-Token`）写回 request。凭证在每次请求时取（runtime 角色凭证会轮换）。
- Produces: `region_from_url(url: str) -> str`
- Produces: `GATEWAY_URL_ENV = "AGENTCORE_GATEWAY_WEBSEARCHGW_URL"`
- Produces: `async def load_gateway_tools() -> list[BaseTool]`：读环境变量，缺失时 `raise RuntimeError(f"{GATEWAY_URL_ENV} is not set ...")`；用 `MultiServerMCPClient({"gateway": {"transport": "streamable_http", "url": url, "auth": SigV4Auth(region)}})` 的 `get_tools()`。实施时确认该版本的 adapter 会处理 `nextCursor` 分页，不会就自己循环 `session.list_tools(cursor)`。

- [ ] **Step 1: 写测试**（用 `monkeypatch.setenv` 设 `AWS_ACCESS_KEY_ID=AKIDEXAMPLE`、`AWS_SECRET_ACCESS_KEY=secret`、`AWS_SESSION_TOKEN=tok`）：
  - `test_region_from_url`: `region_from_url("https://x.gateway.bedrock-agentcore.ap-northeast-1.amazonaws.com/mcp") == "ap-northeast-1"`
  - `test_sigv4_signs_request`: 构造 `httpx.Request("POST", url, content=b"{}")`，跑 `next(SigV4Auth("ap-northeast-1").auth_flow(req))`；断言 `Authorization` 以 `AWS4-HMAC-SHA256` 开头且包含 `/ap-northeast-1/bedrock-agentcore/aws4_request`，`X-Amz-Security-Token == "tok"`
  - `test_missing_url_raises`: `monkeypatch.delenv(GATEWAY_URL_ENV, raising=False)`；`asyncio.run(load_gateway_tools())` 抛 `RuntimeError`，消息含 `AGENTCORE_GATEWAY_WEBSEARCHGW_URL`
- [ ] **Step 2:** `uv run pytest tests/test_gateway.py -v` → FAIL。
- [ ] **Step 3:** 实现 `harness/gateway.py`。
- [ ] **Step 4:** `uv run pytest -v` → PASS。
- [ ] **Step 5: 真实连通性验证**（需要本机 AWS 凭证有 InvokeGateway 权限）：`AGENTCORE_GATEWAY_WEBSEARCHGW_URL=<your-gateway-url> uv run python -c "import asyncio; from harness.gateway import load_gateway_tools; print([t.name for t in asyncio.run(load_gateway_tools())])"` → 预期列表含 `web-search___WebSearch`（以及 `x_amz_bedrock_agentcore_search`）。把实际工具名记下来，Task 4 要用。失败（403 等）就停下来报告，别硬改。
- [ ] **Step 6:** `git add` 后 `git commit -m "feat: gateway MCP client with SigV4" -- app/agent`

### Task 3: Builder（解析工具 + skills → create_deep_agent）

**Files:**
- Create: `app/agent/harness/builder.py`, `app/agent/tests/test_builder.py`

**Interfaces:**
- Consumes: `AgentSpec`、`LOCAL_TOOLS`、`load_gateway_tools`
- Produces: `SKILLS_DIR: Path = <app/agent>/skills`
- Produces: `async def resolve_tools(names: Sequence[str], local: Mapping[str, BaseTool], gateway_loader: Callable[[], Awaitable[list[BaseTool]]]) -> list[BaseTool]`：先查本地；只有存在本地找不到的名字时才调用 `gateway_loader`（且只调一次）；仍缺失则 `ValueError`，消息列出缺失名和全部可用名。按 `names` 顺序返回。
- Produces: `def stage_skills(names: Sequence[str], skills_dir: Path = SKILLS_DIR) -> Path | None`：空列表返回 `None`；否则 `tempfile.mkdtemp()`，把每个 `skills_dir/<name>` `shutil.copytree` 进去；有缺失则 `ValueError`（列出缺失和可用名）。（用复制而不是直接挂 `skills/` 目录，是因为 deepagents 的 skill source 必须是父目录，直接挂会暴露所有 skill。）
- Produces: `async def build_agent(spec: AgentSpec, *, model=None, gateway_loader=load_gateway_tools) -> CompiledStateGraph`：`model` 默认 `load_model()`；有 skills 时 `backend=CompositeBackend(default=StateBackend(), routes={"/skills/": FilesystemBackend(root_dir=staged, virtual_mode=True)})`、`skills=["/skills/"]`、`permissions=` 用 Global Constraints 里那条只读规则；没有 skills 时这三个参数都不传。`checkpointer=InMemorySaver()`、`name=spec.name`。

- [ ] **Step 1: 写测试**（Gateway 用假 loader：返回一个名为 `web-search___WebSearch` 的 `@tool`，并统计调用次数）：
  - `test_resolve_local_only_skips_gateway`: `resolve_tools(["add_numbers"], LOCAL_TOOLS, loader)` → 名字是 `["add_numbers"]`，loader 调用 0 次
  - `test_resolve_gateway_tool`: `["add_numbers", "web-search___WebSearch"]` → 两个都在，loader 调用 1 次
  - `test_resolve_unknown_tool_raises`: `["nope"]` → `ValueError`，消息含 `"nope"` 和 `"add_numbers"`
  - `test_stage_skills_copies_only_selected`: 在 `tmp_path` 下建 `a/SKILL.md`、`b/SKILL.md`；`stage_skills(["a"], tmp_path)` 得到的目录只包含 `a`
  - `test_stage_skills_unknown_raises`: `stage_skills(["zzz"], tmp_path)` → `ValueError`，消息含 `"zzz"`
  - `test_build_agent_smoke`: 用 `langchain_core.language_models.fake_chat_models.GenericFakeChatModel(messages=iter([AIMessage("hi")]))` 做 model，`await build_agent(AgentSpec("t", "p", tools=("add_numbers",)), model=fake)` 返回对象带 `ainvoke`
- [ ] **Step 2:** `uv run pytest tests/test_builder.py -v` → FAIL。
- [ ] **Step 3:** 实现 `harness/builder.py`。
- [ ] **Step 4:** `uv run pytest -v` → PASS（如果 fake model 不支持 `bind_tools`，换成实现了 `bind_tools` 的子类，返回 self）。
- [ ] **Step 5:** `git commit -m "feat: harness builder" -- app/agent`

### Task 4: Agent 注册表、web-research skill、main.py 懒构建、文档

**Files:**
- Create: `app/agent/agents/__init__.py`, `app/agent/skills/web-research/SKILL.md`, `app/agent/tests/test_main.py`
- Modify: `app/agent/main.py`, `app/agent/README.md`
- Modify (不提交): `agentcore/.env.local`

**Interfaces:**
- Consumes: `AgentSpec`、`build_agent`
- Produces: `agents.AGENTS: dict[str, AgentSpec]`，内含 `"general"`：`tools=("add_numbers", "web-search___WebSearch")`（以 Task 2 Step 5 的实际名字为准），`skills=("web-research",)`，system prompt 要说明可以联网搜索、回答要给出处。
- Produces（main.py）：`def get_spec(name: str | None = None) -> AgentSpec`（默认 `os.environ.get("AGENT_NAME", "general")`；名字不存在就 `KeyError`/`ValueError`，消息列出可用名）；`async def get_agent()`：用模块级 `_agent` 缓存和 `asyncio.Lock`，构建失败时不缓存。`invoke` 改成 `agent = await get_agent()`，流式逻辑不变。

- [ ] **Step 1:** 写 `skills/web-research/SKILL.md`：frontmatter 里 `name: web-research`，description 写清楚什么时候用（问时事、需要最新信息或出处时）；正文写步骤：拆分查询 → 调 `web-search___WebSearch` → 交叉验证 → 带链接作答。
- [ ] **Step 2: 写测试** `tests/test_main.py`（monkeypatch `main.build_agent` 为计数的 async 假函数）：
  - `test_get_spec_default`: 未设置 `AGENT_NAME` 时 `get_spec().name == "general"`
  - `test_get_spec_unknown_lists_available`: `get_spec("nope")` 抛错，消息含 `"general"`
  - `test_get_agent_builds_once_concurrently`: `asyncio.gather(*[get_agent() for _ in range(5)])` → build 调用 1 次，5 个结果是同一个对象
  - `test_get_agent_retries_after_failure`: 第一次 build 抛异常 → `get_agent()` 抛异常；第二次 build 成功 → 返回 agent（共调用 2 次）
  - （每个测试前重置 `main._agent = None`）
- [ ] **Step 3:** `uv run pytest tests/test_main.py -v` → FAIL。
- [ ] **Step 4:** 实现 `agents/__init__.py`，改 `main.py`。
- [ ] **Step 5:** `uv run pytest -v` → 全部 PASS。
- [ ] **Step 6:** 在 `agentcore/.env.local` 追加 `AGENTCORE_GATEWAY_WEBSEARCHGW_URL=<your-gateway-url>`（这个文件不提交）。
- [ ] **Step 7: 端到端** 在仓库根目录后台运行 `agentcore dev`，然后执行 `agentcore invoke --runtime agent --local --payload '{"prompt":"搜索一下今天 AWS 的最新新闻，给出处"}'` → 预期流式事件里有 `web-search___WebSearch` 的工具调用，最终答案带链接。
- [ ] **Step 8:** README 的 "What's here"/"Extending" 改成 harness 的用法：新增 agent = 在 `agents/` 加一个 AgentSpec + 新 runtime 设置 `AGENT_NAME`（在 `cdk-stack.ts` 里用 `runtime('<name>').addEnvironmentVariable('AGENT_NAME', ...)`）；新增本地工具放 `tools/`；新增 skill 放 `skills/<name>/SKILL.md`；Gateway 工具直接写 MCP 工具名。
- [ ] **Step 9:** `git commit -m "feat: agent registry, web-research skill, lazy agent build" -- app/agent`
