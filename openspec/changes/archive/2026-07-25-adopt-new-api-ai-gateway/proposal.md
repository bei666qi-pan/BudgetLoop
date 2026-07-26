## Why

BudgetLoop currently assumes one OpenAI-compatible LiteLLM endpoint and performs team recommendation entirely with local rules, so operators cannot use one audited gateway for OpenAI, Claude, Gemini and custom upstream protocols or benefit from AI-assisted intent understanding. The product should adopt a mature open-source gateway and use AI when it is actually available while retaining a deterministic, zero-provider fallback.

## What Changes

- Adopt the actively maintained, AGPL-3.0 `QuantumNous/new-api` project (about 43k GitHub Stars at review time) as the default separately deployed AI gateway, pinned to an audited release and source revision instead of implementing protocol conversion, channel management or load balancing in BudgetLoop.
- Preserve LiteLLM as an explicitly selected legacy gateway mode for existing deployments; do not silently rewrite existing credentials or gateway URLs.
- Add typed BudgetLoop gateway configuration and health/capability reporting for New API, LiteLLM and an operator-supplied compatible gateway. Provider secrets remain server-side and are redacted from all public responses and logs.
- Support the gateway's OpenAI Chat/Responses, Claude Messages and Gemini native protocol surfaces and custom authorized upstream channels through New API. BudgetLoop's own recommendation caller uses the stable OpenAI-compatible surface and does not duplicate protocol adapters.
- Use New API's built-in channel priority/weight, retries, rate limiting and accounting as the provider-routing layer. BudgetLoop selects auditable purpose aliases and does not add a second LLM-based semantic router.
- Change team recommendation to AI-first structured ranking when a configured gateway and recommendation model are healthy, then validate results against the trusted built-in catalog. On timeout, malformed output, unavailable gateway or missing credentials, fall back to the existing local LangGraph rules and disclose which path produced the result.
- Add beginner-readable gateway and recommendation status in the Agent Team creation experience, including a link to the bundled New API console and transparent local-fallback messaging.
- Vendor the pinned New API source and record repository, revision, license, release, reviewed Star count and review date for supply-chain auditability.

## Capabilities

### New Capabilities

- `ai-api-gateway`: Defines the replaceable, protocol-compatible AI gateway boundary, server-side configuration, health/capability disclosure, secure secret handling and gateway-native routing behavior.

### Modified Capabilities

- `agent-team-presets`: Changes recommendation from local-only to validated AI-first ranking with a deterministic local fallback and public provenance.
- `operator-workspace`: Adds beginner-readable AI gateway/recommendation availability and fallback state to Agent Team creation.

## Impact

- Infrastructure: Docker Compose gains a pinned New API service and persistent data volume; the current LiteLLM service becomes an opt-in compatibility profile rather than the default request path.
- Backend: configuration, gateway client/health API, recommendation graph and API response contracts gain additive fields. No provider key is persisted in BudgetLoop's business database or returned to the frontend.
- Frontend: Agent Team creation displays gateway health, AI/local recommendation provenance and recovery guidance without exposing secrets.
- Supply chain and license: New API runs as a separately deployed AGPL-3.0 service with its source and notices preserved; BudgetLoop remains MIT and communicates with it over HTTP.
- Budgets and safety: recommendation calls use strict timeout, output-size and model bounds and are recorded as recommendation metadata; TaskRun budget authority remains in BudgetLoop. Gateway routing never changes control-plane state, approvals or Handoffs.
- Migration: existing LiteLLM environment variables remain accepted. New deployments use `AI_GATEWAY_*` settings and can intentionally select `litellm` during migration.
- Non-goals: reimplementing gateway protocol conversion, billing, user management, channel selection or load balancing; placing provider keys in browser storage; building a model-resale/payment product; or adding an LLM call solely to choose another LLM.
