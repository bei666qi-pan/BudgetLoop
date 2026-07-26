## Why

BudgetLoop currently bundles the official Codex and Gemini CLI sources and exposes them in the UI, but the local worker cannot actually run either engine. This leaves the promised replaceable-engine workflow incomplete and forces coding teams back to OpenHands even when Codex is the recommended default.

## What Changes

- Package pinned official Codex and Gemini CLI distributions into the worker image and make their runtime readiness observable.
- Extend BudgetLoop's short-lived managed AI capability from OpenAI Chat Completions to the upstream-native protocols needed by the bundled engines: OpenAI Responses and Gemini generateContent/streamGenerateContent.
- Route those protocol calls through the maintained New API gateway so protocol conversion and provider routing are reused rather than reimplemented.
- Inject only run-scoped BudgetLoop capability tokens into CLI engine processes; never expose or persist the upstream gateway key in an Agent home, workspace, transcript, or frontend response.
- Make the local default deployment enable the verified CLI runtimes while preserving fail-closed readiness and no-silent-fallback behavior.
- Keep task budgets authoritative across streamed and non-streamed native protocol calls, with conservative settlement when an upstream response omits usage.

## Capabilities

### New Capabilities

- `managed-cli-engine-runtime`: Runnable, pinned Codex and Gemini CLI worker distributions using run-scoped BudgetLoop AI inheritance and verified sandbox/lifecycle boundaries.

### Modified Capabilities

- `execution-engine-registry`: Runtime availability must reflect packaged, authenticated, sandbox-ready managed CLI engines rather than source presence alone.
- `ai-api-gateway`: Managed application/runtime access expands to bounded Responses and Gemini-native protocol routes through New API while preserving the secret boundary and budget accounting.

## Impact

- Affects the backend worker image, execution-engine preflight, CLI environment generation, managed runtime API, gateway forwarding, Docker Compose defaults, API documentation, and frontend readiness copy/tests.
- Adds official pinned npm distributions from `openai/codex` and `google-gemini/gemini-cli`; New API remains the protocol conversion and routing foundation.
- No PostgreSQL business migration is required. Existing tasks, runs, budgets, Keychain data, gateway configuration, and OpenHands behavior remain compatible.
- Budget impact: every managed native-protocol call reserves against the existing TaskRun budget before forwarding and settles or releases afterward.
- Safety impact: runtime capability tokens remain run/model scoped and short lived; upstream keys stay server side; unsupported methods, paths, models, oversized bodies, terminal runs, and unverified runtimes fail closed.
- Non-goals: implementing a new general-purpose model gateway, adding arbitrary host command execution, silently substituting engines, changing New API's database, or enabling OpenCode host execution.
