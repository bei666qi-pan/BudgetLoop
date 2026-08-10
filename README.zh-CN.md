<p align="center">
  <img src="./web/app/icon.svg" width="112" alt="BudgetLoop 标志" />
</p>

<h1 align="center">BudgetLoop</h1>

<p align="center">
  <strong>真实 Agent 团队的可控协同层</strong><br />
  智能路由 · Session 互通 · 证据验收 · 预算治理 · 可控交付
</p>

<p align="center">
  <a href="https://github.com/bei666qi-pan/BudgetLoop/actions/workflows/release.yml"><img src="https://img.shields.io/github/actions/workflow/status/bei666qi-pan/BudgetLoop/release.yml?style=flat&label=CI" alt="CI" /></a>
  <a href="https://github.com/bei666qi-pan/BudgetLoop/releases/latest"><img src="https://img.shields.io/github/v/release/bei666qi-pan/BudgetLoop?style=flat&label=release" alt="Release" /></a>
  <a href="./LICENSE"><img src="https://img.shields.io/github/license/bei666qi-pan/BudgetLoop?style=flat" alt="MIT 许可证" /></a>
</p>

<p align="center"><a href="./README.md">English</a> · <strong>简体中文</strong></p>

---

## BudgetLoop 是什么

BudgetLoop **不重新打造 Agent 框架**。它建立在 **OpenHands、Codex、Gemini CLI** 等执行引擎之上，通过策略与可用性路由自动选型；再以可互通的 Session 和专业 Skills 组建交付团队。

它用预算、审计、工作区权限与人工介入把真实 Agent 执行留在可控边界内；再由系统裁判和主管模型汇总证据、定向调度返工，并且只对可验证的成果给出通过。

> [!IMPORTANT]
> BudgetLoop 会运行真实 Agent、命令与模型调用。请只在你信任的仓库、凭据和 Docker 环境中使用。

## 核心特点

| 能力 | 你实际得到什么 |
| --- | --- |
| **智能执行引擎路由** | 根据任务和可用性选择 OpenHands、Codex 或 Gemini CLI，并保持各自的沙箱语义。 |
| **真正的团队互通** | 产品、架构、实现、QA、整合角色通过可追溯消息协作，不是固定的一次性提示词链。 |
| **裁判主导闭环** | 确定性门禁先行；裁判模型可批准、定向要求返工，或在异常时安全阻塞。 |
| **不会重置的预算** | Token、成本、调用次数和时间预算跨重试与返工累计，重跑不能“洗掉”用量。 |
| **证据而非表演** | 测试、工件、消息送达、Git 发布、退出码和模型裁决全部可审计。 |
| **人工始终可介入** | 可暂停、调高某个 Session 的预算、查看证据并从保存现场恢复。 |
| **受控发布** | 贡献者在隔离 worktree 中工作；只有整合发布角色可将分支快进发布到主工作区。 |

## 5 分钟上手

### 1. 启动控制面

```bash
git clone https://github.com/bei666qi-pan/BudgetLoop.git
cd BudgetLoop
cp .env.example .env
docker compose up -d --build
```

打开 [http://localhost:3000](http://localhost:3000)。控制面 API 在 [http://localhost:8000](http://localhost:8000)，可选的 New API 控制台在 [http://localhost:3001](http://localhost:3001)。

### 2. 配置已获授权的模型网关

编辑 `.env`，填写你有权使用的网关和模型别名。默认部署使用 [New API](https://github.com/QuantumNous/new-api) 提供 OpenAI 兼容网关；也可通过 `legacy-litellm` profile 使用 LiteLLM。密钥只在服务端使用，不会进入浏览器包。

### 3. 创建团队并观察协作

1. 在首页描述希望交付的结果。
2. 检查生成的验收标准、Session 角色与预算信封。
3. 确认并启动团队。
4. 进入 **Agent Team**：左侧看角色，中间看按裁判轮次组织的通信，右侧做控制。
5. 观察系统裁判收集证据、执行硬门禁、向指定 Agent 追问或返工，并记录最终裁决。

只有确认执行后才会预留预算；创建草稿不创建任务，也不消耗模型预算。

## 从需求到可交付成果

```text
需求 + 验收标准
       │
       ▼
智能路由 ──► OpenHands / Codex / Gemini CLI
       │
       ▼
专业 Session ── 可追溯消息 + Skills ──► QA 证据
       │                                      │
       └──────────── 整合角色发布 ────────────┘
                         │
                         ▼
                 系统裁判执行确定性门禁
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
        通过        定向返工        阻塞 / 暂停
```

裁判不会伪造确定性通过。必要角色完成、消息确认、证据、工作区合规、集成发布、测试/构建成功和目标工件存在，必须全部通过，才会调用真实模型进行质量判断。模型超时或返回无效结构会公开进入阻塞状态，等待人工恢复。

## 本地开发

前置条件：Docker、Docker Compose v2、Git；源码开发建议 Python 3.12+ 与 Node.js 20+。

```bash
# 后端
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest

# 前端（新终端）
cd web
npm ci
npm test
npm run build
```

常用校验：

```bash
cd backend && pytest -q
cd web && npm test && npm run build
openspec validate --all
```

## MCP 控制接口

BudgetLoop 提供 MCP Server，让支持 MCP 的编码工具经由控制面创建任务、查看运行、处理审批和读取团队状态。

```toml
# Kimi Code: .kimi/config.toml
[mcp_servers.budgetloop]
transport = "sse"
url = "http://localhost:3100/sse"
```

更多客户端配置请见 [`mcp/`](./mcp)，接口可见 [OpenAPI 规范](./docs/openapi.json)。

## 目录结构

```text
backend/    FastAPI 控制面、编排、预算、裁判与 Worker
web/        Next.js 团队观测台与操作界面
mcp/        外部编码工具使用的 MCP Server
openspec/   版本化产品规范与变更历史
docs/       OpenAPI 与发布文档
vendor/     审核过的执行引擎与网关来源
```

## 贡献

欢迎 Issue 和 PR。行为变更请附带测试，重要产品变更请同步 OpenSpec。请勿提交凭据、本地引擎状态、生成的 worktree 或提供商 Token。

MIT License · 第三方组件保留各自许可证 · [NOTICE](./NOTICE)
