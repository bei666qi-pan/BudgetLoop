## Why

BudgetLoop needs a secure local preview connected to Sangfor's internal DeepSeek V4 Pro through aTrust, with the strongest supported reasoning settings and without placing the supplied API key in the repository. AI applications created by BudgetLoop also need a zero-configuration way to use the operator's already configured gateway instead of asking beginners to create a second project-specific `.env` secret.

## What Changes

- Add a normal authenticated web settings flow for gateway URL, model, deployment label, reasoning policy and managed-app inheritance; save this operator's Sangfor values as local personalization rather than product defaults or hardcoded constants.
- Accept a gateway token through a write-only password field and store it in macOS Keychain for this local installation; keep environment-secret compatibility for deployed/non-macOS installations.
- Add typed default model, reasoning-effort and thinking-budget settings so DeepSeek V4 Pro requests use the strongest supported `max`/enabled reasoning profile while preserving bounded timeouts and budgets.
- Add a redacted gateway readiness treatment that can distinguish aTrust/Sangfor client presence, secure-route reachability, authentication and model availability when those labels are configured, without hardcoding one enterprise provider or exposing the API key/raw internal errors.
- Add a BudgetLoop-managed AI application runtime contract: generated applications receive a loopback BudgetLoop gateway URL and short-lived scoped runtime credential, while the real upstream API key remains owned by BudgetLoop and is never written into the generated project or its `.env` files.
- Add a server-side OpenAI-compatible runtime proxy for generated applications with model allowlisting, request-size/time bounds, scope validation and existing budget/observability hooks; it is not a general public forwarding proxy.
- Start and verify a local BudgetLoop preview from the saved web configuration without making an unbounded or paid generation call.

## Capabilities

### New Capabilities

- `managed-ai-app-runtime`: Secure zero-configuration gateway inheritance for AI applications created and run by BudgetLoop.

### Modified Capabilities

- `ai-api-gateway`: Add web-managed local configuration, maximum reasoning settings, Keychain secret storage and provider-labelled redacted readiness; the supplied Sangfor/DeepSeek values remain local personalization.
- `operator-workspace`: Make the inherited AI runtime and connection state understandable without asking beginners for a second API key.

## Impact

- Affects gateway settings/client code, local preview scripts, authenticated API routes, generated workspace runtime configuration, frontend status copy, tests and operator documentation.
- The upstream key remains outside PostgreSQL, browser bundles, generated repositories, transcripts and logs. It traverses the authenticated local settings request only to be written into Keychain and is never returned. Generated applications receive only a short-lived, scoped BudgetLoop credential and a local proxy URL.
- The managed-app inheritance switch is a general product setting, enabled by default and independently disableable in the web UI.
- Existing New API, LiteLLM and compatible deployments remain supported. The Sangfor profile is local opt-in and requires the operator's aTrust authorization.
- Budget, request-size, timeout, model allowlist and audit constraints continue to apply to inherited runtime calls. Hidden reasoning content remains excluded from public transcripts.
- Non-goals: changing aTrust security policy, bypassing Sangfor authentication/MFA, building a new protocol converter, or exposing the corporate gateway directly to generated browser code.
