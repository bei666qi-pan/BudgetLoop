## Why

OpenHands agent-server separates message submission from conversation execution. The real Sangfor E2E showed that relying on `SendMessageRequest(run=true)` can accept the event while never issuing the official conversation `/run` request; polling then observes a pre-execution terminal/idle state, rapidly consumes the call budget, and produces no model usage or file changes.

## What Changes

- Follow the official OpenHands two-stage server lifecycle: submit the message with `run=false`, then call `POST /api/conversations/{id}/run` explicitly. Preserve the CLI transport's single-call `run=true` behavior.
- Require an agent-server run to demonstrate execution start, an unambiguous failure/pause result, or completed usage before plain `idle` or usage-free `finished` can end the wait.
- Mark queued collaboration messages delivered only after both server-side message submission and explicit run scheduling succeed.
- Adapt the managed OpenAI-compatible model name to OpenHands/LiteLLM's required `openai/` provider form at the conversation boundary, without changing the upstream gateway model configured by the user.
- Fail the run immediately on agent-server `error` or `stuck` instead of consuming further BudgetLoop iterations.
- Configure the OpenHands conversation with its official terminal, file-editor, and task-tracker tools so the selected coding engine can actually inspect, modify, and verify the workspace.
- Fail the run with a sanitized synchronization error when OpenHands never starts within a bounded startup window instead of burning the remaining LLM-call budget.
- Add regression tests for idle/finished-before-running, normal running-to-idle, unambiguous instant terminal completion, usage-backed completion, and never-started behavior.

## Capabilities

### New Capabilities

- `agent-server-execution-synchronization`: Reliable synchronization between asynchronous OpenHands run scheduling and BudgetLoop iteration accounting.

### Modified Capabilities

- None.

## Impact

- Affected code: OpenHands client wait logic, orchestrator invocation, and focused backend tests.
- Budget impact: prevents false call settlement when no agent execution occurred; normal reservation and actual usage accounting remain unchanged.
- Safety and API impact: no public API, credential, database, or migration changes; errors remain sanitized.
- Open-source lineage: the explicit run call follows OpenHands' vendored V1 resume implementation in `vendor/agent-engines/openhands/frontend/src/api/conversation-service/v1-conversation-service.api.ts`.
- Non-goals: changing OpenHands itself, changing the execution engine, or redefining one BudgetLoop iteration.
