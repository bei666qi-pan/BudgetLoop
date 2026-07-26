## Why

A real managed OpenHands run showed that the runtime proxy already settles every upstream LLM request, after which the orchestrator settles the same accumulated usage again. The command center therefore reports exactly doubled tokens and one extra call, undermining both budget enforcement and operator trust.

## What Changes

- Make the managed runtime proxy the sole source of token, call, and cost settlement for agent-server LLM requests.
- Retain the orchestrator's outer reservation as a bounded in-flight guard, but release it without adding a synthetic call or duplicating accumulated usage after managed execution completes.
- Preserve existing settlement for CLI or non-managed transports that do not meter through the runtime proxy.
- Add regression coverage proving command-center budget totals match persisted LLM-call observations for managed agent-server runs.

## Capabilities

### New Capabilities

- `managed-runtime-budget-accounting`: Single-source budget accounting for LLM requests routed through BudgetLoop's managed AI runtime.

### Modified Capabilities

None.

## Impact

- Affected code: orchestrator managed-runtime state, reservation finalization, focused backend tests, and completed-run phase copy in the existing run command center.
- Budget impact: removes duplicate token/call settlement; hard limits continue to be enforced by the managed runtime per upstream request and by the outer in-flight reservation.
- Safety impact: no credential, capability, sandbox, or network changes.
- API impact: no schema or endpoint changes; existing budget fields become accurate.
- Migration impact: none; historical rows are not rewritten.
- Non-goals: changing gateway pricing, adding a new meter, altering non-managed CLI accounting, or redesigning the run page.
