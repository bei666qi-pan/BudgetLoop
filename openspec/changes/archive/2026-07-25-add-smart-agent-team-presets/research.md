# High-star multi-agent pattern review

Snapshot date: 2026-07-25. GitHub repository metadata was queried through the GitHub API. All selected sources exceed 10,000 stars, are not archived or disabled, expose an OSI or content license, and showed recent repository activity at review time.

| Repository | Stars | License | Recent push | Pattern used in BudgetLoop |
| --- | ---: | --- | --- | --- |
| [FoundationAgents/MetaGPT](https://github.com/FoundationAgents/MetaGPT) | 69,503 | MIT | 2026-01-21 | SOP-driven specialist roles and software-company handoffs |
| [microsoft/autogen](https://github.com/microsoft/autogen) | 59,956 | CC-BY-4.0 | 2026-04-15 | Managed group conversation, reviewer and human-in-the-loop patterns |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | 56,103 | MIT | 2026-07-24 | Role, goal and task-oriented crews with sequential or managed coordination |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 38,095 | MIT | 2026-07-25 | Explicit workflow graphs, supervisor routing, durable state and checkpoints |
| [microsoft/semantic-kernel](https://github.com/microsoft/semantic-kernel) | 28,362 | MIT | 2026-07-24 | Enterprise agent orchestration, approvals and controlled routing |
| [camel-ai/camel](https://github.com/camel-ai/camel) | 17,488 | Apache-2.0 | 2026-07-22 | Role-playing societies, task decomposition and cooperative refinement |

## Compatibility and safety decision

- BudgetLoop directly installs LangGraph as the state-graph runtime. Existing OpenHands execution, PostgreSQL state, budgets, approvals and explicit Handoff semantics remain authoritative.
- Presets use CrewAI-compatible YAML role/goal/task fields and MetaGPT-style SOP stages. CrewAI and MetaGPT themselves are not installed because their full LLM runtimes would duplicate OpenHands and introduce provider configuration.
- LangGraph nodes are adapted to existing WorkSession/TaskRun identifiers; BudgetLoop does not implement a competing graph engine.

## Execution engine source review (verified 2026-07-25)

| Engine | Canonical repository | Stars | License boundary | Latest push | Decision |
|---|---|---:|---|---|---|
| OpenHands | `OpenHands/OpenHands` | 82,021 | MIT core; `enterprise/` separate and excluded | 2026-07-25 | Default compatibility engine and server transport |
| Codex | `openai/codex` | 101,301 | Apache-2.0 | 2026-07-25 | Bundled CLI adapter and local source snapshot |
| Gemini CLI | `google-gemini/gemini-cli` | 106,162 | Apache-2.0 | 2026-07-25 | Bundled CLI adapter and local source snapshot |
| OpenCode | `anomalyco/opencode` | 189,513 | MIT | 2026-07-25 | Bundled CLI adapter and local source snapshot |

All four repositories were unarchived and actively maintained at review time. BudgetLoop treats them as replaceable execution engines, not control-plane frameworks. The manifest pins exact commits, engine credentials remain separate, and availability failures do not trigger hidden fallback.
- Recommendation runs locally over bounded goal/preferences and does not transmit project text to GitHub or a model service.
- Template versions are immutable identifiers so a future catalog edit cannot silently change an already-created team's provenance.

## Initial product mapping

- Software delivery: MetaGPT SOP + LangGraph staged supervisor.
- Game development: MetaGPT specialist pipeline + CrewAI managed crew + LangGraph review gates.
- Business growth: CrewAI role crew + CAMEL role-play refinement + AutoGen reviewer.
- Product launch: CrewAI managed execution + LangGraph launch gates + AutoGen critic.
- Brand content: CrewAI sequential production + CAMEL creator/critic exchange.
- Market research: AutoGen researcher/reviewer + LangGraph evidence checkpoints.
- Data analysis: LangGraph deterministic workflow + Semantic Kernel approval boundary.
- Customer support: Semantic Kernel controlled routing + LangGraph escalation graph.
