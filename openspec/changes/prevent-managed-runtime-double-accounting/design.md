## Context

Managed agent-server requests pass through `POST /api/runtime/ai/v1/chat/completions`. That trusted proxy reserves and settles the task budget once for every upstream LLM request. The worker also reserves one outer BudgetLoop iteration before OpenHands starts and currently settles that reservation with OpenHands' cumulative token usages afterward. A real run produced seven persisted LLM calls totaling 86,820 tokens, while `task_budgets` reported eight calls and 173,640 tokens.

## Goals / Non-Goals

**Goals:**

- Make persisted budget totals equal the actual managed-runtime requests and observed usage.
- Preserve a bounded outer reservation while OpenHands is active.
- Keep failure rollback and reservation release deterministic.
- Preserve non-managed transport accounting.

**Non-Goals:**

- Historical data repair, pricing configuration, gateway changes, or a new accounting service.

## Decisions

### Managed-runtime requests settle only at the proxy boundary

The orchestrator records whether the active server conversation uses the provisioned `BUDGETLOOP_AI_MANAGED=1` runtime. Each proxy request remains responsible for its own atomic reserve/settle pair because that boundary sees the actual upstream response and usage.

After OpenHands completes, the worker still normalizes and persists its response-scoped metrics for observability, but it releases the outer iteration reservation instead of calling `settle` with the same cumulative usage. For CLI/non-managed transports, the worker retains its existing settlement behavior.

The alternative of disabling proxy settlement was rejected because it would weaken per-request hard-limit enforcement, lose accurate accounting on partial agent failure, and make generated applications unmetered. Removing the outer reservation entirely was also rejected because it is the worker's in-flight loop guard.

### Recovery derives accounting mode from the workspace handle

The managed marker is read from the provisioned or reattached workspace runtime environment before both new-conversation and existing-conversation paths. No capability value is persisted or logged; only a boolean worker state controls finalization.

### Completed-run UI uses terminal copy

The command center labels a missing phase as `已结束` for terminal runs and `准备中` only for non-terminal runs. This is a targeted trustworthy-behavior correction and does not change layout or visual direction.

## Risks / Trade-offs

- [Outer reservation release races with proxy settlement] → proxy calls commit independently; the outer release only subtracts its own estimate and never modifies used totals.
- [A non-managed transport is misclassified] → default remains false and the marker must be explicitly present on the workspace handle.
- [Observation persistence fails after real proxy calls] → rollback observations, release the outer reservation, and retain already committed proxy usage.

## Migration Plan

1. Add the managed-accounting marker and focused tests.
2. Rebuild only the stateless worker/web services.
3. Verify a real run reports matching budget and observatory totals with zero reservations.
4. Roll back the stateless images if required; no database migration is involved.

## Open Questions

None.
