## Context

BudgetLoop currently sends agent traffic to a LiteLLM Proxy configured through `LITELLM_*` settings. The team-preset endpoint separately runs a deterministic LangGraph keyword graph and advertises that it never calls a model. This is safe but cannot understand goals outside the curated keyword vocabulary, and the single OpenAI-compatible gateway assumption does not provide an operator-facing path for native OpenAI Responses, Claude Messages, Gemini or custom upstream channels.

`QuantumNous/new-api` is an actively maintained AI gateway with approximately 43k GitHub Stars on 2026-07-25. Release `v1.0.0-rc.21` resolves to commit `bde9b2f44887d34ec54799ae191d50f97914359e`, is AGPL-3.0, exposes OpenAI Chat/Responses, Claude Messages and Gemini endpoints, and already implements channel priority/weight, retries, rate limits, accounting and an administration UI. It therefore supplies the gateway behavior instead of BudgetLoop recreating it.

The gateway is infrastructure, not a business source of truth. PostgreSQL remains authoritative for BudgetLoop Tasks, Runs, budgets, approvals, events and Handoffs. New API retains only its own channel, token, accounting and gateway administration data in a separate logical database.

## Goals / Non-Goals

**Goals:**

- Make a pinned New API deployment the default gateway for new BudgetLoop installations while keeping LiteLLM as an explicit compatibility mode.
- Let an operator configure legal upstream channels and protocol conversion in the upstream New API console rather than in newly written BudgetLoop forms.
- Expose a redacted, beginner-readable gateway capability and health contract to the BudgetLoop UI.
- Use a bounded AI call to rank only trusted built-in team presets, with strict structured-output validation and deterministic local fallback.
- Keep recommendation provenance, failure reason and remote-call behavior transparent.
- Retain BudgetLoop's existing budget and control-plane boundaries.

**Non-Goals:**

- Forking or rewriting New API, LiteLLM, protocol converters, provider SDKs, billing, channel routing or gateway authentication.
- Storing provider credentials in the BudgetLoop database, frontend, logs or recommendation snapshots.
- Adding a semantic LLM router whose only job is choosing another LLM.
- Exposing New API as a public resale/payment service or relaxing upstream authorization requirements.
- Removing LiteLLM configuration in this change.

## Decisions

### 1. Run pinned New API as a separate service

The repository will vendor the audited New API source under `vendor/ai-gateways/new-api` and pin Compose to release `v1.0.0-rc.21` rather than `latest`. Its AGPL source, license, upstream URL, revision, reviewed Star count and review date will be recorded in NOTICE and a vendor manifest. The service communicates with BudgetLoop over HTTP and uses a separate `newapi` database plus Valkey; no New API code is linked into the MIT control plane.

Alternative considered: extend the current custom LiteLLM callback and configuration into a multi-protocol administration plane. Rejected because New API already provides the requested protocol surfaces and channel console and because doing so would recreate gateway functionality.

### 2. Introduce one typed gateway boundary with legacy aliases

Settings will add `AI_GATEWAY_TYPE` (`new-api`, `litellm`, `compatible`), `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY`, `AI_GATEWAY_CONSOLE_URL`, `AI_GATEWAY_RECOMMENDATION_MODEL`, `AI_RECOMMENDATION_ENABLED` and strict connect/read timeout bounds. If the new variables are absent, existing `LITELLM_BASE_URL` and `LITELLM_MASTER_KEY` continue to work in `litellm` compatibility mode. Public serialization reports type, configured/healthy state, protocol capabilities, routing mode, source provenance and actionable reason, but never the key or raw exception text.

`GatewayClient` owns URL normalization, `/v1/models` preflight and the bounded OpenAI-compatible recommendation request. It deliberately does not implement Claude/Gemini translation; those native endpoints are a declared capability of the deployed New API service.

Alternative considered: persist gateway settings and encrypted provider keys through BudgetLoop UI. Rejected because New API already provides an audited administration console and duplicating credential custody would widen BudgetLoop's attack surface.

### 3. AI-first recommendation is a validated augmentation of the catalog

The endpoint validates user input before any remote call. When AI recommendation is enabled and gateway preflight succeeds, it sends a bounded prompt containing only the user's submitted goal/preferences and a compact public projection of the built-in preset catalog. The prompt asks for JSON containing at most three preset IDs, confidence, short reason and public matched signals. It requests no chain of thought.

The response parser enforces byte, item, string and numeric bounds, rejects unknown/duplicate preset IDs and reconstructs full presets from the trusted local catalog. A completely invalid, timed-out or unavailable response invokes the existing LangGraph rule graph. A partially valid response keeps only valid entries and fills no invented presets. Every response adds `source` (`ai` or `local_fallback`), public explanation, gateway type and a sanitized fallback code.

AI recommendation is advisory: it does not create a container, change a budget, select an execution engine or dispatch a Run. The existing creation validation remains authoritative.

Alternative considered: make AI failure an endpoint error. Rejected because recommendation must stay usable with no provider and the existing local graph is a safe deterministic fallback.

### 4. Use gateway-native routing instead of a second AI router

New API's channel priority, weighted selection, retry, rate limiting and model mapping are the routing layer. BudgetLoop addresses stable purpose aliases such as `budgetloop-recommendation`; operators map those aliases to authorized channels in New API. This is predictable, auditable and does not spend an extra model call to choose a model.

LiteLLM (approximately 54k Stars at review time) remains available for deployments that already depend on its routing, but BudgetLoop does not chain LiteLLM and New API in the default path. Chaining two gateways would duplicate accounting, retries and failure semantics.

### 5. Health checks are bounded and UI state is truthful

`GET /api/ai-gateway/status` returns cached redacted configuration and a bounded live preflight. Recommendation does its own fresh bounded request and never trusts UI state as authorization. The Agent Team page displays one of: AI recommendation ready, local fallback because unconfigured, or local fallback after a sanitized runtime failure. The New API console link is shown only for a configured safe HTTP(S) URL and opens separately.

Structured logs record gateway type, result source, duration, response status class and fallback code without prompt text, model output or secrets. Tests use mocked transports and never call a paid provider.

## Risks / Trade-offs

- [AGPL obligations or accidental code linking] → Run New API as a separate process, preserve source/license notices and communicate only over HTTP.
- [Release candidate instability] → Pin both release and commit, provide a health check, document rollback, and avoid depending on undocumented internal APIs.
- [Gateway becomes a single point of failure] → Keep deterministic local recommendation and fail closed for execution calls; expose clear health facts.
- [Prompt injection alters preset selection] → Treat the goal as untrusted data, constrain output to known preset IDs, validate every field and never execute model-supplied instructions.
- [Recommendation prompt leaks project text] → Disclose AI use before/with results, send only the submitted recommendation fields, bound content, and make local-only operation possible by disabling AI.
- [Double accounting during migration] → Exactly one gateway type is active; New API and LiteLLM are never chained by default.
- [Existing LiteLLM users break] → Preserve legacy variables and an explicit compatibility mode, with additive API fields and documented migration.
- [Health checks overload the gateway] → Cache status briefly and apply hard timeouts; recommendation requests remain independently bounded.

## Migration Plan

1. Vendor and verify the pinned New API release and add license/provenance records.
2. Add the `newapi` logical database and pinned Compose service without deleting the LiteLLM profile.
3. Add `AI_GATEWAY_*` settings and legacy LiteLLM resolution; deploy with AI recommendation disabled until a New API token/model alias exists.
4. Configure legal upstream channels and a `budgetloop-recommendation` alias in the New API console, then enable AI recommendation.
5. Deploy the additive status and recommendation contracts, followed by the frontend transparency state.
6. Roll back by setting `AI_RECOMMENDATION_ENABLED=false` and `AI_GATEWAY_TYPE=litellm`; local recommendation and existing agent execution remain available.

## Open Questions

None for this change. Per-user gateway credentials and semantic model routing require separate security and evaluation work and are intentionally excluded.
