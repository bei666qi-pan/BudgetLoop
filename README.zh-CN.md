<br />
<p align="center">
  <picture>
    <img src="./web/app/icon.svg" width="120" alt="BudgetLoop">
  </picture>
</p>

<h1 align="center">BudgetLoop</h1>
<p align="center"><strong>预算感知的 Coding Agent 控制面</strong><br />规划 · 执行 · 验证 · 恢复 — 在你的边界内完成</p>

<p align="center">
  <a href="https://github.com/bei666qi-pan/BudgetLoop/releases/latest"><img src="https://img.shields.io/github/v/release/bei666qi-pan/BudgetLoop?style=flat&label=latest" alt="最新版本"></a>
  <a href="https://github.com/bei666qi-pan/BudgetLoop/actions/workflows/release.yml"><img src="https://img.shields.io/github/actions/workflow/status/bei666qi-pan/BudgetLoop/release.yml?style=flat&label=ci" alt="CI"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/github/license/bei666qi-pan/BudgetLoop?style=flat" alt="MIT"></a>
</p>

<p align="center"><a href="./README.md">English</a> · <strong>简体中文</strong></p>

---

## 一键启动

```bash
git clone https://github.com/bei666qi-pan/BudgetLoop.git && cd BudgetLoop && cp .env.example .env && docker compose up -d --build
```

打开 [http://localhost:3000](http://localhost:3000) · 编辑 `.env` 填入模型网关密钥后刷新：`docker compose up -d --build control-plane worker web`

---

## 这是什么

BudgetLoop 把自然语言需求转化为有预算、有证据、可审批的 Agent 执行闭环。它运行真实的 Agent 和工具，跟踪 Token/时间/调用/费用预算，在进展受阻时自我恢复，并在需要你决策时停下来等你。

> [!IMPORTANT]
> BudgetLoop 是实验性自托管系统。请只使用你信任的仓库、凭据和 Docker 环境。

## 能做什么

| | |
| --- | --- |
| **可信预算** | 围绕真实模型调用的原子化预留与结算 |
| **有证据，不表演** | 工具输出、测试结果、退出码、Diff、工件、时间线 |
| **Agent Team** | 引导式协作、可并行阶段、显式 Handoff、人工审批 |
| **安全隔离** | 每 Run 独立 Docker 工作区、服务端 Git Worktree、显式目录授权 |
| **诚实反馈** | 启动阶段可见、有界重试、可操作错误信息 |
| **自我恢复** | 按进展信号切换策略、回滚、最小修复或交付部分结果 |

## 开始使用

**前置条件：** Docker + Docker Compose v2 + Git

1. 在首页描述你想要的结果
2. 检查推荐的 Agent 团队、验收条件和预算
3. 点击**确认并启动**

预算只在确认后才开始消耗；草稿生成不扣费、不创建任务。

## 架构

```
Next.js Web UI  →  FastAPI 控制面  →  PostgreSQL + Valkey + Dramatiq
                                          ↓
        OpenHands / CLI 引擎  ←  每 Run Docker 工作区
                ↓
         New API / 兼容网关  →  LLM 服务商
```

| 层 | 技术 |
| --- | --- |
| 界面 | Next.js 15 · React 19 · TypeScript · Tailwind CSS |
| 控制面 | FastAPI · SQLAlchemy · PostgreSQL 16 |
| 任务队列 | Dramatiq · Valkey |
| Agent | OpenHands SDK · Codex · Gemini CLI |
| 隔离 | 每 Run Docker 工作区 · Git Worktree |
| 网关 | QuantumNous New API · 兼容 OpenAI/Anthropic |

## 安全

- **默认隔离** — 每 Run 只写自己的 Docker 卷
- **显式授权** — 直接读写本地文件夹需确认绝对路径
- **失败关闭** — 挂载或启动失败直接终止，不静默降级
- **凭据在服务端** — 前端永不接触网关或模型密钥
- **可审批** — 高风险写入、命令、网络操作可要求人工确认

## 开发

```bash
# 后端
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && pytest

# Web
cd web && npm ci && npm test && npm run build

# 版本一致性检查
python3 scripts/check_release_version.py
```

```
backend/   API · 编排 · 预算 · 策略 · Worker
web/       浏览器操作界面
openspec/  版本化产品需求与变更
docs/      发布与演示文档
```

## 贡献与许可

欢迎 Issue 和 PR。行为变更请附带测试，重要变更请同步 OpenSpec 规范。

MIT License · 第三方组件保留各自许可 · [NOTICE](./NOTICE)
