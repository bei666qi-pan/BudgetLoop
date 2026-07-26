## Context

The worker sends each OpenHands iteration with `run=true`, then immediately polls the conversation. The real deployment demonstrated that the event may be accepted without the agent-server starting the conversation: no `POST /api/conversations/{id}/run` appeared in the agent-server log, every iteration returned without agent events, and no model call occurred. Even when execution is scheduled, the first poll can still return the pre-run `idle` state.

The real Sangfor E2E reproduced both failure modes: twelve iterations completed with zero usage, every status poll returned idle/finished, no agent events or model usage were recorded, and the host file was unchanged.

## Goals / Non-Goals

**Goals:**

- Distinguish pre-start idle from post-execution idle for agent-server transport.
- Explicitly schedule server execution through the official conversation `/run` endpoint after message submission.
- Allow normal running-to-idle and instant terminal completion.
- Fail within a short startup bound when execution never starts, releasing the reservation through the orchestrator's existing exception path.
- Preserve CLI engine behavior and the overall step timeout.

**Non-Goals:**

- Changing OpenHands scheduling, adding a protocol extension, or changing budget accounting semantics.

## Decisions

### Use OpenHands' explicit two-stage server lifecycle

For server transport, each iteration performs these operations in order:

1. `send_message(instruction, run=False)` to persist the user event;
2. `run_conversation()` to call `POST /api/conversations/{id}/run`;
3. `wait_until_idle(require_execution_start=True)` to observe real execution.

This follows the OpenHands implementation vendored at `vendor/agent-engines/openhands/frontend/src/api/conversation-service/v1-conversation-service.api.ts`, where resuming a V1 conversation is an explicit `/run` request. CLI transport keeps `send_message(..., run=True)` because its adapter executes the process synchronously and does not implement a separate run endpoint.

Queued collaboration messages are marked delivered only after both server operations succeed. If `/run` fails, the inbox remains queued and the existing orchestrator exception path releases the reservation.

OpenHands documents `409` from the conversation run endpoint as “already running.” This is an idempotent scheduling success: it can occur when message submission and explicit scheduling race with the server's own start transition. `run_conversation()` therefore accepts only this endpoint's 409 and proceeds to the same execution wait; all other HTTP conflicts remain errors.

### Require explicit start evidence only for the server orchestrator path

`wait_until_idle` gains `require_execution_start` and `start_timeout_seconds`. The OpenHands orchestrator passes `require_execution_start=True`; existing diagnostic callers can retain immediate-idle behavior.

Start/completion evidence is one of:

- any non-idle running state was observed and a later idle state arrives;
- OpenHands returns an unambiguous terminal state such as `paused`, `error`, `stuck`, or `waiting_for_confirmation`;
- the conversation reports at least one token-usage record, which proves an LLM execution completed before the first poll.

Plain `idle` or usage-free `finished` without evidence is polled until the smaller startup deadline. The real agent-server returned stale `finished` and placeholder latency/cost arrays immediately after each successful `/run` response without producing any token usage or agent events, so neither status nor ancillary metric arrays alone are reliable start evidence. This avoids relying on arbitrary consecutive-state counts while still covering executions that finish between polls through actual token-usage evidence.

### Fail rather than settle an empty iteration

If no start evidence appears within 15 seconds, the client raises a sanitized `AgentServerError`. The orchestrator already releases reserved budget and transitions the run to failed through its normal exception path. This prevents rapid false call consumption and makes a broken agent-server contract visible.

The same fail-fast path applies when OpenHands returns `error` or `stuck`. These states are execution outcomes, not successful empty iterations, so the worker releases the current reservation and stops the run instead of executing tests and advancing phases repeatedly.

### Adapt managed model names at the OpenHands boundary

OpenHands' agent SDK delegates model resolution to LiteLLM. Its own profiles and tests use provider-qualified names such as `openai/gpt-4o`; the vendored provider assignment logic is documented in `vendor/agent-engines/openhands/openhands/app_server/utils/llm.py`. A real run confirmed that a bare custom model name fails with `LLM Provider NOT provided` before any network call.

BudgetLoop's managed runtime exposes an OpenAI-compatible endpoint, so the server-transport conversation receives `openai/<managed-model>`. LiteLLM consumes this prefix to select the protocol and sends the original managed model in the OpenAI request body. The capability claim, gateway configuration, frontend value, and generated-app `OPENAI_MODEL` remain unchanged; the adaptation exists only in the OpenHands conversation configuration.

### Normalize current OpenHands metric records transactionally

The current agent-server serializes response latency and optional cost as response-scoped objects (`{model, latency/cost, response_id}`), while older fixtures used plain numeric arrays. BudgetLoop correlates metric objects to token usage by `response_id`, falls back to the same index for legacy arrays, and extracts only finite numeric values.

Observation, metric recording, settlement, and their commit form one protected unit. If normalization or persistence fails, the worker rolls back uncommitted observations and releases the already committed outer iteration reservation before failing the run. This prevents a parser compatibility error from leaving `reserved_calls` stranded.

### Load OpenHands' official coding tools

The agent-server OpenAPI `Agent-Input` schema documents class-name examples, but the running OpenHands SDK 1.37.1 tool registry exposes the corresponding official serialized names as `terminal`, `file_editor`, and `task_tracker`. BudgetLoop uses those registry names in `agent.tools`, following `openhands-tools/openhands/tools/preset/default.py` and each tool's registered `Tool.name` in OpenHands' `software-agent-sdk` v1.37.1. A real E2E confirmed that omitting these entries lets the model reason but leaves read, edit, and shell calls unavailable; using the stale class names fails message restoration because no such registry entry exists.

BudgetLoop passes those three official OpenHands tool descriptors with empty params. Execution remains wholly inside the vendored/replaced OpenHands engine; BudgetLoop does not implement a parallel file or command tool. Workspace mount permissions and the existing approval/risk layers remain the authorization boundary.

## Risks / Trade-offs

- [An execution finishes instantly and OpenHands reports idle/finished] → actual token-usage records are accepted as completion evidence.
- [OpenHands exposes latency/cost placeholders without an LLM call] → only a real token-usage record counts as completed usage.
- [OpenHands returns error/stuck immediately] → fail once and release the reservation rather than advancing the loop.
- [A bare custom model has no LiteLLM provider] → qualify only the OpenHands-side model as `openai/<model>` because the managed endpoint is OpenAI-compatible.
- [Metric arrays contain response-scoped objects] → correlate by `response_id`, support legacy numeric entries, and never coerce an object directly with `float()`.
- [Observation recording fails] → rollback the observation unit and release the outstanding reservation before propagating the error.
- [OpenHands defaults to reasoning-only tools] → load its official registered `terminal`, `file_editor`, and `task_tracker` descriptors in the conversation request.
- [A zero-usage local agent action finishes instantly] → it may hit the startup bound; failing is safer than silently consuming the task's full call budget.
- [Agent-server startup is unusually slow] → the 15-second bound is configurable per wait call and remains below the overall step timeout.

## Migration Plan

1. Add the explicit server send/run lifecycle, wait-state tests, and orchestrator wiring.
2. Rebuild only the stateless worker image/service.
3. Repeat the real full-access Sangfor task and inspect usage, events, and host changes.
4. Rollback is a worker image rollback; no persisted schema or task data changes.

## Open Questions

None.
