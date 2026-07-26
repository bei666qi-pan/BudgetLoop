## Context

BudgetLoop provisions each OpenHands agent-server in a Docker workspace. Provisioning already creates a run-scoped managed-runtime environment whose API key is a signed, short-lived `blrt1` capability. However, the worker creates the initial OpenHands conversation from the control plane's resolved gateway configuration, bypassing that environment and copying the reusable upstream key into the agent-server request.

The managed capability and runtime proxy are the existing design introduced by the archived `connect-sangfor-deepseek-runtime` change. This change closes the remaining agent-server path without adding a new gateway, protocol adapter, database table, or user-facing key flow.

## Goals / Non-Goals

**Goals:**

- Keep the upstream credential inside BudgetLoop's trusted control-plane boundary.
- Use the provisioned workspace handle as the sole source of agent-server LLM URL, capability, and model.
- Fail closed before creating an agent-server conversation when capability inheritance is unavailable or malformed.
- Preserve current CLI execution-engine behavior, which already supplies the scoped runtime environment directly to its child process.

**Non-Goals:**

- Changing OpenHands APIs, the OpenAI-compatible runtime proxy, model routing, workspace network policy, or database schema.
- Adding a second credential UI, persisting a capability, or exposing capability values through APIs, logs, or browser state.

## Decisions

### Pass the workspace handle into conversation setup

`_run_inner` will provide the `WorkspaceHandle` to `_ensure_conversation` rather than only its working directory. For server transport the method reads `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` from `handle.runtime_env`; this makes the actual conversation configuration exactly match the workspace's injected process-only configuration.

The alternative—reissuing a capability in the orchestrator—would duplicate issuance policy, make attach/recovery less deterministic, and increase the chance of policy drift. The handle already contains the single provisioned runtime context.

### Fail closed for server transport

Before `create_conversation`, server transport requires all three managed variables and a `BUDGETLOOP_AI_MANAGED=1` marker. Missing or disabled inheritance raises a sanitized `WorkspaceError`; no agent-server request occurs. A caller can explicitly enable inheritance in the existing web settings flow, but the system never silently falls back to the upstream key.

### Retain CLI behavior

CLI clients continue passing empty LLM URL/key arguments to their own client method and use `engine_environment` to pass the capability to the engine subprocess. The change branches by the existing `transport` value so that different high-star execution engines remain replaceable.

## Risks / Trade-offs

- [A capability expires before a resumed conversation is created] → attach already rebuilds the handle runtime environment; the failure is clear and produces no credential fallback.
- [An OpenHands API requires its LLM credentials in its conversation payload] → it receives only the proxy URL and scoped capability, which are designed for that payload; the control plane validates and meters the eventual request.
- [Tests accidentally inspect a real secret] → tests use distinct sentinel strings and mock the resolved gateway configuration; assertions prove inequality without reading runtime configuration.

## Migration Plan

1. Change worker conversation setup and add unit coverage.
2. Rebuild/recreate stateless control-plane and worker services; persisted Postgres, Valkey, and New API services remain untouched.
3. Verify an OpenHands workspace can complete a managed-runtime call through the Sangfor relay and inspect redacted observability counters.
4. Roll back by redeploying the prior stateless worker/control-plane image; no migration or persisted credential state requires reversal.

## Open Questions

None. Existing managed-runtime settings already default to enabled and expose the user-controlled disable switch.
