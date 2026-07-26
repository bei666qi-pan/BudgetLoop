## Why

The OpenHands agent-server conversation path currently receives the configured upstream gateway credential directly. This breaks BudgetLoop's managed-runtime boundary: an agent workspace must use a short-lived, budget-scoped capability, never the operator's reusable provider key.

## What Changes

- Route OpenHands agent-server conversations through the existing managed AI runtime URL, scoped capability, and selected model held in the workspace handle.
- Fail closed with a clear workspace error when managed-runtime inheritance is disabled or cannot issue a complete capability for an agent-server run.
- Add regression coverage proving that agent-server requests never receive the upstream gateway credential and CLI engine behavior remains unchanged.

## Capabilities

### New Capabilities

- `managed-agent-server-runtime`: Secure managed-runtime credential handling for agent-server conversations executed in BudgetLoop workspaces.

### Modified Capabilities

- `ai-api-gateway`: Extend the server-side secret boundary to agent-server execution requests.

## Impact

- Affected code: worker orchestrator conversation setup and backend tests.
- Safety: upstream credentials remain limited to BudgetLoop's control plane; the workspace receives only a short-lived capability bound to its run and model.
- API and migration impact: no public API or data migration changes.
- Non-goals: changing gateway protocol conversion, modifying CLI execution-engine credential behavior, or adding a second key configuration surface.
