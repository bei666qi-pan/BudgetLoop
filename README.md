<p align="center">
  <img src="./web/app/icon.svg" width="112" alt="BudgetLoop logo" />
</p>

<h1 align="center">BudgetLoop</h1>

<p align="center">
  <strong>The controlled coordination layer for real Agent teams.</strong><br />
  Route · collaborate · verify · govern · deliver
</p>

<p align="center">
  <a href="https://github.com/bei666qi-pan/BudgetLoop/actions/workflows/release.yml"><img src="https://img.shields.io/github/actions/workflow/status/bei666qi-pan/BudgetLoop/release.yml?style=flat&label=CI" alt="CI" /></a>
  <a href="https://github.com/bei666qi-pan/BudgetLoop/releases/latest"><img src="https://img.shields.io/github/v/release/bei666qi-pan/BudgetLoop?style=flat&label=release" alt="Release" /></a>
  <a href="./LICENSE"><img src="https://img.shields.io/github/license/bei666qi-pan/BudgetLoop?style=flat" alt="MIT license" /></a>
</p>

<p align="center"><strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a></p>

---

## Why BudgetLoop?

BudgetLoop does **not** rebuild an Agent framework. It sits on top of execution engines such as **OpenHands, Codex and Gemini CLI**, selects the right engine through policy and availability-aware routing, and turns isolated runs into a governed delivery team.

Sessions exchange durable messages, draw on specialized Skills, and work within explicit workspace permissions. Budgets, audit trails and human intervention keep the process controllable. A system judge and a supervisor-model evaluation loop then coordinate evidence, request focused rework and approve only verifiable delivery.

> [!IMPORTANT]
> BudgetLoop runs real agents, commands and model calls. Use repositories, credentials and Docker environments you trust.

## What you get

| Capability | What it means in practice |
| --- | --- |
| **Smart engine routing** | Choose an available execution engine for the task while preserving its engine-specific sandbox model. |
| **Real team collaboration** | Product, architecture, implementation, QA and integration Sessions communicate through durable, observable messages—not a fixed prompt chain. |
| **Judge-led quality loop** | Deterministic gates run first; the judge model can approve, direct rework to selected Sessions, or block safely. |
| **Budgets that do not lie** | Track token, cost, call and time envelopes across retries and rework. Re-running cannot reset the cumulative budget. |
| **Evidence before approval** | Tests, artifacts, delivery acknowledgements, Git publication and model verdicts are persisted for inspection. |
| **Human control at boundaries** | Pause, adjust a Session budget, inspect evidence or resume a saved loop when a safety boundary is reached. |
| **Safe delivery roles** | Contributors work in isolated worktrees; the integration role is the only role allowed to publish the primary repository. |

## Five-minute start

### 1. Start the control plane

```bash
git clone https://github.com/bei666qi-pan/BudgetLoop.git
cd BudgetLoop
cp .env.example .env
docker compose up -d --build
```

Open [http://localhost:3000](http://localhost:3000). The control-plane API is available on [http://localhost:8000](http://localhost:8000), and the optional New API console is available on [http://localhost:3001](http://localhost:3001).

### 2. Connect an authorized model gateway

Edit `.env` with the gateway and model alias you are authorized to use. The default deployment uses [New API](https://github.com/QuantumNous/new-api) as an OpenAI-compatible gateway; LiteLLM remains available through the `legacy-litellm` profile. Secrets remain server-side and are never bundled into the web app.

### 3. Create a team, then observe the loop

1. Describe the outcome you want on the home page.
2. Review the generated acceptance criteria, Session roles and budget envelope.
3. Confirm and start the team.
4. Open **Agent Team** to inspect the three-column observatory: Sessions, round-grouped messages and controls.
5. Follow the system judge as it collects evidence, runs gates, asks selected agents for clarification and records a verdict.

Budget is reserved only after you confirm execution. Drafting a task does not create a run or consume model budget.

## How a controlled team delivers

```text
Request + acceptance criteria
            │
            ▼
Engine router ──► OpenHands / Codex / Gemini CLI
            │
            ▼
Specialist Sessions ── durable messages + Skills ──► QA evidence
            │                                                │
            └────────────── integration publishes ───────────┘
                                      │
                                      ▼
                       System judge: deterministic gates
                                      │
                 ┌────────────────────┼────────────────────┐
                 ▼                    ▼                    ▼
             approve          targeted rework          blocked / pause
```

The judge never invents a deterministic pass. Required roles, message acknowledgement, evidence, workspace compliance, publication, test/build success and deliverable presence must all pass before a real model evaluation can approve. Model timeout or invalid output becomes a visible blocked state, ready for operator recovery.

## Local development

Prerequisites: Docker + Docker Compose v2 + Git. For source development, use Python 3.12+ and Node.js 20+.

```bash
# backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest

# web (new terminal)
cd web
npm ci
npm test
npm run build
```

Useful checks:

```bash
cd backend && pytest -q
cd web && npm test && npm run build
openspec validate --all
```

## MCP control interface

BudgetLoop exposes an MCP server so capable coding tools can create tasks, inspect runs, handle approvals and read team state through the control plane.

```toml
# Kimi Code: .kimi/config.toml
[mcp_servers.budgetloop]
transport = "sse"
url = "http://localhost:3100/sse"
```

For other clients and standalone setup, see [`mcp/`](./mcp) and the static [OpenAPI specification](./docs/openapi.json).

## Repository map

```text
backend/    FastAPI control plane, orchestration, budgets, judge and workers
web/        Next.js observatory and operator experience
mcp/        MCP server for external coding tools
openspec/   Versioned product specifications and change history
docs/       OpenAPI and release documentation
vendor/     Reviewed execution-engine and gateway sources
```

## Contributing

Issues and pull requests are welcome. Please keep behavior changes covered by tests and record meaningful product changes in OpenSpec. Do not commit credentials, local engine state, generated worktrees or provider tokens.

MIT License · third-party components retain their own licenses · [NOTICE](./NOTICE)
