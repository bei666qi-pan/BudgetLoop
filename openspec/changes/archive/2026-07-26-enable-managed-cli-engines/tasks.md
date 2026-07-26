## 1. Native managed AI protocol boundary

- [x] 1.1 Refactor shared runtime capability, live-run, request-size and budget reservation checks so Chat Completions and native routes use one fail-closed policy.
- [x] 1.2 Add allowlisted OpenAI Responses forwarding through New API with streaming support, model enforcement, sanitized headers/errors and conservative usage settlement.
- [x] 1.3 Add allowlisted Gemini generateContent and streamGenerateContent forwarding through New API with path-model enforcement, query-token stripping and conservative usage settlement.
- [x] 1.4 Add focused tests for authorization, terminal runs, model mismatch, size/budget rejection, upstream failures, streaming/non-streaming usage and secret-free forwarding/logging.

## 2. Runnable official CLI engines

- [x] 2.1 Pin and package official Codex and Gemini CLI distributions in the worker image and verify both command versions at build time.
- [x] 2.2 Extend managed runtime environment generation with protocol-specific OpenAI Responses and Gemini variables while keeping capabilities process-only and engine-scoped.
- [x] 2.3 Generate isolated Codex provider configuration and Gemini CLI environment/sandbox configuration from each live run capability without persisting upstream credentials.
- [x] 2.4 Update execution-engine preflight so verified managed inheritance satisfies authentication, while missing commands/protocols/sandbox or disabled inheritance remains fail closed.
- [x] 2.5 Add adapter, environment, preflight and command-construction tests for managed Codex/Gemini plus disabled-inheritance and no-silent-fallback cases.

## 3. Gateway and local deployment

- [x] 3.1 Keep the fixed maintained New API release matching the reviewed source, back up its separate data/schema, route Sangfor through New API and verify health plus Responses and Gemini native routes.
- [x] 3.2 Enable only verified Codex and Gemini CLI runtimes in the local Compose profile without changing PostgreSQL, Valkey, workspace or Keychain persistence.
- [x] 3.3 Update gateway/engine API documentation and beginner-facing readiness copy to distinguish installed, managed-ready and unavailable states.

## 4. Verification and delivery

- [x] 4.1 Run focused and full backend tests, Ruff, frontend tests and the Next.js production build.
- [x] 4.2 Rebuild the control-plane/worker/web images while preserving the live local gateway environment and verify redacted health/readiness APIs.
- [x] 4.3 Run bounded real Codex and Gemini CLI smoke tasks through the Sangfor DeepSeek managed runtime and verify budget, transcript, workspace and secret boundaries.
- [x] 4.4 Recheck desktop/mobile engine selection in the browser, then rebuild/sign the macOS app and refresh the Desktop shortcut.
- [x] 4.5 Strict-validate this OpenSpec change and complete the full-objective evidence audit.
