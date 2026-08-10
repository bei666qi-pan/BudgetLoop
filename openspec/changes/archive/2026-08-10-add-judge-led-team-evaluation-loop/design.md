# Design: Judge-Led Team Evaluation Loop

## Architecture

BudgetLoop extends its existing WorkContainer, WorkSession, TaskRun, durable message/SSE outbox, budget ledger and LangGraph-based team activation. The judge is a system-managed `WorkSession` (`session_kind=judge`) rather than a parallel team abstraction. A durable conditional round service implements the loop:

`evidence -> deterministic gates -> model evaluation -> approve | targeted rework | blocked`

Rework messages create new TaskRuns on the responsible Session's existing branch. The integration Session remains the only role allowed to publish the primary desktop repository. No additional orchestration dependency is introduced.

## Design lineage

- LangGraph `libs/langgraph/langgraph/graph/state.py`: conditional state/edge semantics used by existing BudgetLoop activation and the judge phase transition design.
- AutoGen `_selector_group_chat.py` and manager: evidence-driven recipient selection rather than fixed round-robin turns.
- MetaGPT review actions: structured findings, evidence references and directed review/rework.
- OpenAI Codex sandbox modes: `workspace-write` contributor isolation; only the system-owned full-access integration role can receive `danger-full-access` for real Git publication. Contributor CLI worktrees receive only their Git metadata directory in addition to their worktree.

## Persistence

The migration adds `judge_policies`, `judge_rounds`, `judge_gate_results` and `judge_findings`. The existing WorkSession stores judge identity/lifecycle and the existing `llm_calls`/TaskBudget rows store model and billing evidence. Each round stores evidence payload/references, phase, gate rows, findings, feedback message IDs, pending Session IDs, structured model verdict and final verdict.

## Decision rules

1. Consume durable Agent replies and mark real acknowledgement.
2. Persist each deterministic gate and emit a team SSE event.
3. If any gate fails, persist `rework`, create evidence-linked feedback for selected Sessions and create cumulative-budget TaskRuns.
4. If all gates pass, call the configured real model with a strict JSON contract.
5. The server rejects approval when gates fail; invalid/unavailable model output becomes `blocked` and is audited.
6. Budget/deadline/safety limits save state and require authenticated operator recovery. An operator may add only a bounded number of recovery rounds per request.

## Public interfaces

- `GET /api/work-containers/{id}/judge`
- `POST /api/work-containers/{id}/judge/resume` (idempotency key supported)
- Existing Session budget patch endpoint for budget adjustments
- Existing team SSE replay stream with judge event types:
  `judge_state_changed`, `judge_gate_completed`, `judge_feedback_dispatched`, `judge_verdict_recorded`

## UI

`JudgeRounds` is embedded in the existing three-column observatory and mobile structure. It renders durable loading/phase labels, gate chips, structured model summary, prior-round history, round-grouped communication and recovery controls. The Session rail pins and labels the system judge. Raw prompts, hidden reasoning and private context are never rendered.

The completed UI receives a Mode 1 design review limited to action hierarchy, token/design-system use, accessibility, responsive behavior and trustworthy error/AI transparency.

## Verification and formal delivery

The real team uses product, architecture, logic, UI, QA, integration and judge Sessions. Contributors work in independent worktrees; primary publication is a real fast-forward merge by the integration Session. The standalone tracker is served at `127.0.0.1:4173`; BudgetLoop is served at `127.0.0.1:3000`.

Acceptance evidence includes backend coverage, web tests/build, OpenSpec validation, a real model `llm_calls` judge approval, in-app observatory inspection, and HTTP Playwright desktop/390px interaction, persistence, keyboard, deletion, console/network and overflow checks.
