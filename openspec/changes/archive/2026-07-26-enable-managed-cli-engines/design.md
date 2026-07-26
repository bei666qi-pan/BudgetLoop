## Context

BudgetLoop already has a typed execution-engine registry and CLI adapter lifecycle, but the production worker image contains only Python. `ENABLE_CLI_ENGINES` defaults to false, preflight requires a separate engine credential, and the managed AI runtime only implements `/chat/completions`. Consequently the official Codex and Gemini CLI checkouts are supply-chain references rather than usable execution engines.

The official Codex revision now requires the OpenAI Responses wire API (`openai/codex`, `codex-rs/model-provider-info/src/lib.rs`), while Gemini CLI supports an operator gateway through `GOOGLE_GEMINI_BASE_URL` (`google-gemini/gemini-cli`, `docs/reference/configuration.md`). QuantumNous New API already owns `/v1/responses` and `/v1beta/models/{model}:generateContent|streamGenerateContent` routing (`router/relay-router.go`). BudgetLoop must therefore authorize and meter these surfaces without implementing protocol translation itself.

PostgreSQL remains authoritative for TaskRun state and budget. The existing signed runtime capability remains the only credential given to generated applications and CLI engines. The Sangfor/New API upstream key remains in Keychain-backed server configuration.

## Goals / Non-Goals

**Goals:**

- Make pinned official Codex and Gemini CLI binaries available inside the local worker image.
- Let both engines inherit BudgetLoop AI through run/model-scoped short-lived credentials by default.
- Forward Responses and Gemini-native requests byte-for-byte through New API after method, path, size, run, model and budget validation.
- Support streaming without buffering complete model output or recording prompt/completion content.
- Keep readiness truthful, fail closed, and preserve manual engine choice without silent fallback.
- Preserve OpenHands behavior, existing data and web-configured gateway settings.

**Non-Goals:**

- Reimplementing Responses/Gemini conversion, tool-call semantics or model routing.
- Passing the upstream gateway key to a workspace or engine process.
- Enabling unreviewed arbitrary host execution or OpenCode host mode.
- Guaranteeing that every third-party model supports every native engine feature; readiness and runtime errors remain explicit.

## Decisions

### 1. Package official distributions in a dedicated Node build stage

The backend Dockerfile will use a pinned Node LTS build stage to install exact official `@openai/codex` and `@google/gemini-cli` package versions, then copy only Node, the global modules and command links into the Python worker image. Version pins will be documented beside the vendored source revisions and verified during image build with `codex --version` and `gemini --version`.

This reuses upstream release artifacts and platform packages. Building Codex's full Rust workspace and Gemini's monorepo in every local image was rejected because it materially increases build time and creates a second build/release pipeline. Floating `latest` installs were rejected because they break supply-chain reproducibility.

### 2. Extend the managed runtime as an authenticated reverse proxy, not a converter

BudgetLoop will add narrowly routed endpoints for:

- `POST /api/runtime/ai/v1/responses`
- `POST /api/runtime/ai/v1beta/models/{model}:generateContent`
- `POST /api/runtime/ai/v1beta/models/{model}:streamGenerateContent`

After capability, live-run, request-size, model and budget validation, the control plane forwards to the configured New API path. It removes the caller's capability from headers/query parameters and injects the server-side gateway authorization only on the upstream hop. New API performs all protocol conversion, routing, retry and rate limiting.

Arbitrary paths, methods, model names and proxy headers are not accepted. This keeps the runtime a capability-scoped AI surface rather than an open proxy.

### 3. Stream upstream responses while collecting only bounded usage metadata

Native engine clients use SSE. The proxy will return status, safe content type and stream bytes as they arrive. A bounded incremental parser observes only usage fields in Responses/Gemini completion events; it does not persist content. When exact usage is present, the existing budget reservation is settled to actual tokens. When a successful native response omits usage, the conservative reserved estimate is settled as consumed rather than released. Failed upstream calls release the reservation.

Disconnects and parser failures are logged with run/model/status facts only. They never include request bodies, SSE payloads, credentials or prompts.

### 4. Treat a valid managed runtime as the CLI credential

Preflight will accept either an explicit engine-scoped login/configuration or enabled managed AI inheritance. For managed Codex, the worker writes an isolated runtime-only `config.toml` selecting a Responses provider whose base URL is the BudgetLoop runtime URL and whose credential is the short-lived token. For managed Gemini CLI, it exports `GEMINI_API_KEY=<capability>`, `GOOGLE_GEMINI_BASE_URL=<BudgetLoop runtime origin>` and `GEMINI_MODEL=<allowed model>` only in the child process environment.

The per-run capability is generated immediately before execution and is not used as a global worker readiness secret. Preflight additionally requires the command and verified sandbox/lifecycle configuration. Manual engine-scoped credentials continue to work when inheritance is disabled.

### 5. Enable only the verified local worker profile

The checked-in Docker Compose local profile will enable Codex and Gemini CLI after their build-time commands and managed protocol smoke tests pass. Other deployments remain controlled by `ENABLE_CLI_ENGINES` and explicit sandbox settings. Gemini uses its official sandbox mode; Codex continues to receive the existing BudgetLoop/Codex sandbox policy. No unavailable engine becomes selectable merely because source exists.

### 6. Keep the local gateway on a pinned, verified New API path

The deployed `v1.0.0-rc.21` image and its reviewed source expose both Responses and Gemini native routes. The earlier Gemini shell response was caused by BudgetLoop's local gateway configuration pointing directly at the Sangfor OpenAI-compatible endpoint, which bypassed New API's native protocol routing. The change will keep a fixed New API release, back up its separate data, configure Sangfor as a New API channel, point BudgetLoop at New API, and verify both protocol surfaces before enabling Gemini CLI.

Rollback keeps the New API database volume, restores the previous local gateway configuration and disables CLI flags. BudgetLoop business tables require no migration.

## Risks / Trade-offs

- **[Native model incompatibility]** DeepSeek may not implement every Codex/Gemini tool feature even after New API conversion. → Run real non-destructive engine smoke tasks and report engine-specific upstream errors without fallback.
- **[Longer worker image builds]** Node and two CLIs increase image size. → Use a multi-stage build, exact package pins and build cache; keep engine source outside the image.
- **[Streaming budget uncertainty]** Some streams omit usage or disconnect after output. → Charge the conservative reservation on successful usage-less responses and release only definite upstream failures.
- **[Gateway configuration drift]** A direct compatible-provider URL can bypass New API's native conversion while still returning HTTP 200 HTML. → Back up New API data, pin the image, require the local BudgetLoop gateway URL to target New API, and verify response content types plus both native routes.
- **[Capability exposure through child inspection]** Any process can inspect its own environment. → Use short TTL, one run/model/audience scope, never persist it, and revoke usefulness when the run becomes terminal.
- **[Gemini base URL semantics]** Gemini CLI expects an origin before `/v1beta`. → Derive and test a protocol-specific runtime origin rather than reusing the OpenAI `/v1` base verbatim.

## Migration Plan

1. Add native-route tests and managed environment/preflight tests before enabling any runtime.
2. Add pinned CLI packages to the worker image and verify command versions.
3. Back up New API's separate data/schema, configure the Sangfor channel through New API, point local BudgetLoop settings at New API, then verify `/api/status`, Responses and Gemini native calls.
4. Deploy the control plane with native runtime routes while CLI engines remain disabled; exercise scoped non-stream and stream tests.
5. Enable Codex and Gemini CLI in the local worker, recreate only control-plane/worker/web as needed while preserving gateway environment, and run one bounded smoke task per engine.
6. If verification fails, disable CLI engines and restore the prior New API image; existing OpenHands runs and business data remain valid.

## Open Questions

- The exact official package versions and deployed New API release/digest will be recorded during implementation from the pinned source/release metadata; no floating tag is acceptable.
- Gemini CLI will be marked available only if the official sandbox is demonstrably active in the worker environment and the native DeepSeek route completes a real smoke request.
