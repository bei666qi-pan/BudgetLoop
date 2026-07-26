## 1. Sangfor Local Profile

- [x] 1.1 Extend typed gateway settings and public redacted status with default model, reasoning effort, thinking enablement/budget and deployment label fields.
- [x] 1.2 Apply the configured maximum reasoning/thinking policy to bounded recommendation and managed-runtime requests without exposing hidden reasoning.
- [x] 1.3 Add authenticated local gateway settings APIs with atomic non-secret persistence, write-only macOS Keychain secret replacement and redacted provider/network/gateway/model preflight; keep all supplied Sangfor values out of product defaults.
- [x] 1.4 Document the normal web configuration flow, Keychain behavior, this installation's aTrust prerequisite and maximum reasoning profile, plus non-macOS/deployment fallback without adding a working credential.

## 2. Managed AI Application Runtime

- [x] 2.1 Implement signed, short-lived run/model/audience-scoped runtime capabilities with constant-time validation and no database or file persistence.
- [x] 2.2 Add a bounded OpenAI-compatible Chat Completions runtime proxy that enforces token scope, model allowlisting, reasoning policy, timeout/size limits and sanitized errors.
- [x] 2.3 Inject only scoped BudgetLoop proxy URL/token/model variables into CLI and Docker workspace processes when the default-on web setting is enabled, so generated AI applications need no project `.env` key and disabled mode injects nothing.
- [x] 2.4 Add safe generated-application guidance that requires browser clients to use their own server route and forbids writing runtime or upstream credentials into source.
- [x] 2.5 Add secret-free runtime observability and preserve live-run budget rejection/settlement behavior.

## 3. Beginner-first Status UI

- [x] 3.1 Add an authenticated AI settings page and extend frontend contracts/status treatment for write-only secret replacement, configurable provider/network readiness, model, maximum reasoning and default-on managed-app inheritance.
- [x] 3.2 Add focused UI tests for save/redaction, ready, route-unavailable and inherited-runtime enabled/disabled disclosures while preserving existing action hierarchy and light-blue design direction.

## 4. Verification and Preview

- [x] 4.1 Add backend tests for settings persistence/validation, write-only secret redaction, reasoning payloads, Keychain-independent preflight mapping, token tampering/expiry/scope, proxy bounds and enabled/disabled workspace injection.
- [x] 4.2 Run focused Ruff, Mypy and backend tests, then the complete backend suite and record environment-only skips.
- [x] 4.3 Run frontend tests and a clean production build.
- [x] 4.4 Start the local preview, verify the UI and redacted gateway state in the in-app Browser, and make no unbounded or paid model generation call.
- [x] 4.5 Run `frontend-design-review` Mode 1 after the UI is runnable, apply only verified targeted corrections and recheck.
- [x] 4.6 Strictly validate OpenSpec and update the verification record; leave the completed change ready for spec sync and archive.
