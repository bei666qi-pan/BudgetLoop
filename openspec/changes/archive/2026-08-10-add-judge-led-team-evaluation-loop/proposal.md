# Proposal: Add Judge-Led Team Evaluation Loop

## Summary

Introduce a **Judge-led evaluation loop** that orchestrates multi-agent team
reviews through a LangGraph-based deterministic gate → structured model
evaluation → verdict pipeline. Every team receives a system-managed, visible,
independently-billed, and non-closable judge session. The loop enforces hard
gating (never approve on gate failure), supports rework with budget
accumulation, and persists full evaluation provenance.

## Motivation

- Teams currently lack a structured, deterministic review mechanism that
  combines hard evidence gates with authentic model-driven evaluation.
- Without a judge session, evaluation is ad-hoc, non-reproducible, and
  invisible to stakeholders.
- Existing tools (LangGraph, AutoGen, MetaGPT) offer reusable architectural
  primitives, but no integrated loop ties them into a budget-aware, verdict-
  producing pipeline within BudgetLoop.

## Proposed Change

Add a new capability `judge-evaluation-loop` with:

- **JudgeSession lifecycle**: auto-created per team, visible, independently
  billed, non-closable; idempotent backfill for teams without a terminal
  session.
- **LangGraph evaluation cycle**: Phase delivery → Evidence collection →
  Deterministic hard gate → Structured model evaluation (judge dynamically
  selects and queries multiple agents, waits for real confirmations, never
  fixed linear rounds) → approve / rework / blocked verdict.
- **Hard gate enforcement**: gate failure → no approve; model or evidence
  anomaly → blocked.
- **Rework & budget**: rework spawns a new TaskRun but accumulates budget
  against the original session; hitting the boundary pauses for human
  recovery.
- **Persistence**: JudgeRound, DetermineisticGateResult, JudgeFinding,
  verdict, and llm_calls are all persisted.
- **API**: GET /judge (state/rounds), POST /judge/resume, four SSE judge
  event streams.
- **UI**: Per-round loading, side-by-side multi-agent communication,
  delivery/confirmation/reply indicators, gate result and model evaluation
  summaries, explicit pause/resume controls. Hidden reasoning never exposed.

## Impact

- **Backend**: New judge service, LangGraph graph definition, persistence
  models, API routes, SSE endpoints.
- **Frontend**: Judge panel component in the team workspace, real-time
  communication views, verdict and gate summaries.
- **Persistence**: New tables/collections for judge rounds, gates, findings,
  verdicts, and LLM call logs.
- **E2E & QA**: Dynamic real E2E tests, Playwright acceptance, frontend-
  design-review Mode1 on the completed UI.
- **Desktop**: Delivered through the formal desktop budget-tracker team
  release pipeline.

## References

- LangGraph `libs/langgraph/langgraph/graph/state.py` — state-graph
  execution model.
- AutoGen `_selector_group_chat.py` / `manager` — dynamic agent selection
  and multi-agent conversation routing.
- MetaGPT `review` actions — structured review and verdict patterns.
- OpenAI Codex sandbox-mode model (`vendor/agent-engines/codex`) — write-
  permission isolation semantics.
