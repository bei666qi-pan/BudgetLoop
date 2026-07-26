## Context

BudgetLoop already has a typed OpenAI-compatible gateway client and keeps the real gateway token server-side. Local configuration currently relies on process environment variables and recommendation calls do not express a reasoning profile. Worker workspaces receive an execution engine but there is no explicit capability for an AI application created inside that workspace to reuse BudgetLoop's configured gateway without copying the upstream key into project files.

The requested Sangfor endpoint is reachable only through the operator's authorized aTrust environment. On this Mac the aTrust client and core agent are running and the UI shows an authenticated green state, but the initial `/v1/models` TLS preflight timed out. The implementation must distinguish this environmental route state from invalid configuration and must not weaken or automate corporate access controls.

## Goals / Non-Goals

**Goals:**

- Configure this installation's Sangfor-compatible profile through an authenticated web settings page and run a local BudgetLoop preview from the saved settings.
- Use `deepseek-v4-pro-202606` with the strongest configured reasoning effort and enabled thinking budget, failing visibly rather than silently reducing the requested profile.
- Let server-side AI applications created in BudgetLoop workspaces use the configured upstream through a BudgetLoop proxy without their own `.env` API key, with inheritance enabled by default and disableable in web settings.
- Keep upstream credentials out of generated source trees, browser bundles, PostgreSQL, API responses, transcripts and logs.
- Preserve request bounds, model allowlisting, budget accounting and auditable sanitized failure facts.

**Non-Goals:**

- Bypassing aTrust login, MFA, policy, TLS checks or network controls.
- Building protocol conversion or a second semantic model router.
- Giving generated browser JavaScript a durable credential; browser-facing apps must call their own server route.
- Making the scoped runtime proxy a general Internet-accessible relay.

## Decisions

### 1. Treat Sangfor values as local web-managed personalization

The authenticated settings page accepts gateway kind, URL, model aliases, deployment/network labels, reasoning policy and the managed-app inheritance switch. This operator can enter the supplied Sangfor URL and DeepSeek model, but product defaults and source constants remain provider-neutral. BudgetLoop continues to speak OpenAI-compatible HTTP and does not add provider-specific protocol conversion.

### 2. Persist non-secrets locally and the secret in macOS Keychain

An authenticated local-only settings API validates and atomically stores non-secret personalization under the user's BudgetLoop application-support directory. Its write model accepts an optional password field only for replacement; its read model returns `secret_configured` and never the value. On macOS the backend writes that value to a generic Keychain item and reads it only while resolving server-side gateway configuration. The AppleScript prompt used for initial bootstrap writes the same Keychain service. No secret-bearing `.env`, generated file or terminal output is created. Non-macOS and deployed environments retain the existing server-secret environment contract.

Settings resolution is deterministic: an explicit local saved value overrides the corresponding process default, Keychain supplies the local secret when configured, and environment-only deployments continue unchanged. Invalid local files fail closed with a sanitized configuration state.

### 3. Represent maximum reasoning as explicit typed request policy

Gateway configuration gains a default model plus `reasoning_effort=max`, thinking enabled and a bounded maximum thinking-token budget. Calls add these extension fields only when configured. If the Sangfor surface rejects the profile, BudgetLoop reports a sanitized rejected-request state; it does not silently downgrade. Hidden reasoning text remains excluded from public output and transcripts, while usage counters may retain aggregate reasoning-token facts.

### 4. Broker access for generated AI applications instead of copying the upstream key

BudgetLoop issues an HMAC-signed, short-lived capability containing version, run identifier, allowed model, audience and expiry. The signing material is derived server-side from the existing BudgetLoop API token and configured upstream key, so no new project secret or business-table record is required. Validation uses constant-time comparison and rejects malformed, expired, wrong-audience or wrong-model tokens.

When the general inheritance toggle is enabled, workspace provisioning injects process-only variables such as `OPENAI_BASE_URL`, `OPENAI_API_KEY` and `OPENAI_MODEL` that point to the BudgetLoop runtime proxy. The value named `OPENAI_API_KEY` is the scoped BudgetLoop capability, never the upstream key. CLI child processes and Docker workspaces inherit it in memory; generated repositories and `.env` files do not. When disabled, none of these managed runtime variables are injected and the proxy does not issue capabilities.

### 5. Keep the runtime proxy narrow and fail closed

The proxy exposes only the OpenAI-compatible operations explicitly required by generated server-side applications, beginning with Chat Completions and model metadata. It validates the scoped token before reading the bounded body, overwrites the model with the allowlisted model when omitted, rejects a different model, applies configured reasoning policy, uses hard connect/read limits and returns sanitized errors. It never reflects upstream headers or raw exceptions.

### 6. Preserve budget and observability ownership

Every runtime call records run/model/status-class/duration/usage facts without prompt, completion or credential content. Calls without a live BudgetLoop run scope fail closed. Existing run budgets remain authoritative; the proxy reserves and settles usage through the same control-plane boundary where a run is available.

## Risks / Trade-offs

- **[aTrust route is unavailable]** → Preview starts with a redacted degraded state and local recommendation fallback; no TLS bypass or alternate Internet route is attempted.
- **[Sangfor rejects `max` extension fields]** → Surface a sanitized configuration incompatibility and keep the requested maximum profile visible; do not silently lower effort.
- **[Scoped token leaks from a child process]** → Restrict audience/model/run/expiry, keep it out of files and logs, and invalidate it when the BudgetLoop API token or upstream key changes.
- **[Browser code attempts direct use]** → Document and enforce server-side use; do not embed runtime capabilities in Next.js public variables or static bundles.
- **[Proxy becomes an unmetered relay]** → Require a live run-scoped capability, bound request/response/time, allowlist the model and preserve budget settlement.
- **[Local Keychain lookup fails]** → Settings/status reports a beginner-readable secret-store state and refuses remote calls; existing environment-only deployment paths are unaffected.

## Migration Plan

1. Add typed reasoning and managed-runtime configuration with inheritance enabled by default but no provider URL/model defaults.
2. Add authenticated web settings, local non-secret persistence, Keychain secret handling and provider-labelled preflight; document this installation's Sangfor values without making them product constants.
3. Add scoped token and proxy code, then inject only scoped runtime variables into workspaces.
4. Add redacted UI/API status and focused security tests.
5. Start the local preview, verify non-secret health and fallback behavior, and retry Sangfor model preflight after aTrust routing is available.

Rollback removes the local launcher/runtime-proxy feature flag and returns to the prior compatible gateway configuration. Existing New API and LiteLLM profiles require no data migration.

## Open Questions

- This local Sangfor endpoint must confirm whether it accepts both `reasoning_effort=max` and the configured thinking object. Until the aTrust route responds, the implementation treats rejection as a visible compatibility failure rather than guessing a lower tier.
