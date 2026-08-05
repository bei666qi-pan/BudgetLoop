## Context

The v0.3.1 launcher currently derives a repository URL even when no valid checkout is found; for an app installed in `/Applications` that fallback is `/`. After Compose refresh, `WebWindowController` immediately loads `http://localhost:3000` without a navigation delegate, loading state, timeout, retry, or rendered failure state. The 2026-07-30 desktop acceptance run reproduced both failures while the same page returned HTTP 200 and rendered correctly in Chromium at `http://127.0.0.1:3000`.

The change is limited to the native macOS host. PostgreSQL remains the business source of truth, the web and backend API contracts stay unchanged, and the existing native folder-picker authorization boundary remains authoritative.

The path-boundary design follows OpenAI Codex's established explicit-root and canonicalization approach rather than inferring broad filesystem authority: see `vendor/agent-engines/codex/codex-rs/sandboxing/src/seatbelt_tests.rs` and `vendor/agent-engines/codex/codex-rs/protocol/src/permissions.rs`. Web navigation recovery uses the system WebKit `WKNavigationDelegate` lifecycle rather than a new browser abstraction or dependency.

## Goals / Non-Goals

**Goals:**

- Find a valid local checkout when the signed app is run beside the repository or from `/Applications` on the same user's Mac.
- Never treat `/`, the home directory, or an unvalidated directory as the repository fallback.
- Make the native transition from launcher health checks to the Web UI observable and bounded.
- Retry transient loopback navigation failures and give persistent failures a readable retry/exit surface.
- Preserve native folder selection and complete a real-model, full-access acceptance run against a unique timestamped project below `/Users/qi/Desktop/测试`, with genuinely parallel role worktrees followed by one controlled integration and publication step.
- Make the acceptance run repeatable without deleting or overwriting any earlier run.

**Non-Goals:**

- Redesigning the Next.js UI or changing its information architecture.
- Changing the task-draft, Agent Team, workspace, or AI-gateway APIs.
- Adding auto-update, remote checkout download, credential migration, or a general-purpose filesystem search.
- Expanding sandbox or folder permissions, or weakening the existing high-risk acknowledgement.

## Decisions

### 1. Extract bounded checkout discovery into a testable Foundation helper

Discovery will evaluate candidates in a deterministic order: explicit `BUDGETLOOP_REPO`, bundle parent/adjacent/grandparent, then fixed user locations such as `~/Desktop/BudgetLoop`, `~/Documents/BudgetLoop`, `~/Developer/BudgetLoop`, and `~/Projects/BudgetLoop`. A candidate is accepted only after standardization/canonicalization and project-marker validation (`docker-compose.yml`, `.env` or `.env.example`, and `desktop/Info.plist`). Sensitive roots are rejected. Failure returns the attempted locations and stops before Docker or environment mutation.

Alternative considered: recursively search the home directory. Rejected because it is slow, privacy-invasive, nondeterministic, and could select an unrelated or malicious checkout. Alternative considered: keep falling back to a parent directory. Rejected because the observed `/` fallback violates fail-closed behavior.

### 2. Use one canonical IPv4 loopback URL for native health and presentation

The native host will use `http://127.0.0.1:3000` for WebKit and web health checks, while the trusted-page guard will accept only `127.0.0.1` or `localhost` on port 3000. This removes local DNS/proxy/PAC ambiguity without broadening the bridge to non-loopback origins.

Alternative considered: continue using `localhost` and only add retries. Rejected because the reproducible desktop failure did not occur in Chromium at the canonical IPv4 loopback URL, and retrying the same ambiguous resolution is weaker than removing it.

### 3. Gate the native web handoff on `WKNavigationDelegate`

`WebWindowController` will show an AppKit loading overlay until main-frame navigation finishes. Transient loopback failures trigger a bounded retry with short backoff. A watchdog covers the case where WebKit neither finishes nor reports failure. Exhaustion replaces the overlay with a failure title, sanitized local error, Retry, and Exit controls. Retry resets the bounded attempt state; successful navigation cancels the watchdog and removes the overlay.

Alternative considered: silently call `reload()` on a timer forever. Rejected because it hides failures, can loop indefinitely, and gives the operator no trustworthy state.

### 4. Verify helper behavior plus the actual packaged application

A dependency-free Swift test executable will exercise candidate ordering, marker validation, sensitive-root rejection, and retry limits. Packaging checks will continue to validate version and code signature. The final gate is a real desktop interaction: launch the built app, choose a fresh `/Users/qi/Desktop/测试/budgetloop-real-ai-<timestamp>-<marker>` directory through the native picker, submit the fixed marker-bearing static-site request, require AI provenance rather than local fallback, confirm full access, wait for every required Agent run to complete, and inspect the host-folder artifacts.

The E2E evidence will redact provider credentials and will not include Keychain values or `.env` contents.

### 6. Keep native authorization real while automating deterministic verification

A standard-library Python driver will expose three stable commands. `prepare` checks Docker, the signed application copies, Web health, gateway health, and OpenHands readiness before creating a unique run directory and non-secret manifest. `observe` discovers the container by its unique marker and records session/workspace/terminal state without approving actions. `verify` requires AI recommendation provenance, successful real-model calls, completed sessions, and one completed `整合发布` delivery worktree.

Managed-runtime capabilities use a domain-separated HMAC derived only from the
BudgetLoop service API token shared by worker and control-plane. The upstream AI
credential is intentionally excluded: the worker may receive it from an
environment variable while the launcher/control-plane resolves the same gateway
through macOS Keychain. Binding signatures to those provider-specific secret
sources makes otherwise valid capabilities unverifiable. The upstream key remains
control-plane-only for gateway forwarding and is never placed in a capability.

An explicitly opted-in checkout may instead persist compatible-gateway values in
its local ignored `.env`. The launcher reads only the exact non-secret marker
`BUDGETLOOP_USE_PROJECT_AI_GATEWAY=true`; when present it passes no legacy
Application Support or Keychain overlay to Compose, so Compose loads the
project configuration unchanged. This marker is intentionally strict (comments
and lookalikes do not match), is never exposed to WebKit, and no `.env` content
is recorded in logs or E2E evidence.

For the native AI settings form, the trusted loopback bridge validates the same
bounded configuration fields and writes them to this project `.env` with
owner-only permissions. It serializes values safely for Compose, retains an
existing key when the form leaves it blank, and returns only redacted settings.
It does not write Keychain or Application Support gateway configuration.

The OpenAI Chat Completions compatibility path offloads its synchronous gateway
client to FastAPI's worker thread pool. Agent teams can make several long-running
model calls concurrently without blocking the control-plane event loop, so health,
observation, approval, and cancellation APIs remain responsive during execution.

The software-delivery preset assigns the platform-safe maximum 200,000-token hard ceiling to each role. Real OpenHands traces showed roughly 8,000–14,000 prompt tokens per tool turn; 60,000- and 120,000-token ceilings still rejected otherwise healthy Sessions before they could emit their final completion, while values above 200,000 are intentionally rejected by the product safety validator. The five-dollar, 20-call, 600-second active-runtime, and 1,200-second wall limits remain authoritative. A server-backed OpenHands step may wait for up to the same 600-second active-runtime limit instead of failing at an unrelated 300-second client timeout.
Real OpenHands accounting includes the repeated system and conversation context
on every model turn (about 8,000 tokens per turn in the acceptance run); the old
18,000–40,000 ceilings rejected otherwise healthy third or fourth calls before
non-delivery roles could report completion. Call-count, wall-time, active-time,
parallelism, and cost limits remain unchanged and fail closed.

Each implementation-capable role receives an isolated worktree and a stable, declared allowlist of paths. The fixed site acceptance task uses the following boundaries: 产品负责人 may add `REQUIREMENTS.md`; 架构设计 may add `ARCHITECTURE.md`; 后端实现 may add `assets/data/app-copy.json`; 前端体验 may create and modify `index.html`, `styles.css`, and `assets/**` except `assets/data/app-copy.json`; 测试验证 may add `TESTING.md`. No role may modify another role's owned paths, the root Git metadata, or server-owned `.budgetloop` metadata. The role prompt requires a checkpoint commit before completion and treats an out-of-bound write as a failed Session, rather than silently accepting it.

A dedicated `整合发布` role begins only after all five contributor roles have reached `COMPLETED`. Its isolated worktree starts from the same recorded baseline and receives a deterministic ordered list of the five contributor branches. Because independently changed branches cannot generally be fast-forwarded into one another, it performs a reviewed `git merge --no-ff --no-commit` for each clean contributor branch in the order 产品负责人 → 架构设计 → 后端实现 → 前端体验 → 测试验证, resolving only a conflict involving declared owned paths and committing the merge result. An order-dependent conflict outside ownership, missing/ambiguous branch, dirty worktree, unauthorized-path diff, or absent checkpoint commit is terminal and fails closed. It records the contributor branch heads, merge commits, resolution files (if any), and verification result in redacted evidence. The resulting integration branch is the only branch eligible for root publication with `git merge --ff-only`.

The driver validates every contributor worktree and commit before integration, validates the completed integration worktree after its checkpoint, requires a clean baseline (ignoring server-owned `.budgetloop` metadata), and publishes only the integration branch with `git merge --ff-only`. It will never choose among multiple integration branches, force a merge, reset the project, or synthesize website files. A separate Playwright gate will serve the published static site locally and check desktop/mobile rendering, semantics, keyboard focus, console failures, external requests, and required landing-page structure.

Container discovery first uses the explicit marker and then the exact confirmed `project_dir`, because a valid AI planner may summarize the marker-bearing request before persisting the container title and goal. Workspace health checks and subsequent Agent Server API calls bypass inherited HTTP proxy variables for the Docker-published `host.docker.internal` control channel; otherwise a corporate proxy can return a false 502 even after Agent Server is healthy.

When multiple full-access Sessions enter a previously empty directory together, Git baseline initialization is serialized with an atomic lock directory stored under server-owned `.budgetloop` metadata. Waiters accept only a repository with a committed `HEAD`; timeout remains fail-closed. This prevents concurrent `git init` template and index races without broadening filesystem authority.

The native WKWebView and `NSOpenPanel` remain part of the acceptance path and are operated through the real packaged app. The repository driver deliberately does not add a test-only folder-picker bypass or a production API.

### 7. Retry one schema-invalid planning response without weakening validation

If a healthy real model returns syntactically valid output that fails the trusted task-draft parser, the planner will make at most one repair request to the same configured model. The repair request identifies only the public validation code, repeats the exact bounded JSON contract, and asks for a complete replacement object. The replacement passes through the same preset, field, length, confidence, and signal validation as the first response. A second invalid response or any gateway error retains the existing deterministic fallback and public fallback reason.

This follows the bounded structured-output repair pattern used by mature schema-driven AI clients while keeping BudgetLoop's local catalog authoritative. It changes neither the public task-draft request/response shape nor folder authorization, and it adds at most one model call only when the first model response is unusable.

### 5. Use Docker Desktop's bundled BuildKit Dockerfile frontend

The backend Dockerfile will not force `# syntax=docker/dockerfile:1.7`, because that directive resolves Docker Hub metadata even when every application layer is cached. Docker Desktop 29.6 and Buildx 0.35 provide a stable bundled frontend that supports the Dockerfile's existing cache mounts and heredoc. This follows Docker BuildKit's established default-frontend behavior and removes one avoidable network dependency without changing image contents or adding a custom builder.

Alternative considered: pin the remote frontend by digest. Rejected because BuildKit must still resolve/fetch that separate frontend when it is absent or registry access is degraded. Alternative considered: disable BuildKit. Rejected because the Dockerfile intentionally uses cache mounts and heredoc.

## Risks / Trade-offs

- [A user has multiple valid checkouts in fixed locations] → deterministic priority is documented; `BUDGETLOOP_REPO` remains the explicit override.
- [A valid checkout lives elsewhere] → fail with the attempted paths and an actionable override remedy instead of scanning broadly.
- [WebKit reports a non-transient application error] → do not retry indefinitely; present the native failure surface and preserve launcher logs.
- [A transient Compose restart exceeds the retry window] → the operator can retry in place after services stabilize, without restarting data services.
- [Canonical IPv4 loopback differs from existing `localhost` assumptions] → bridge trust explicitly permits only the two equivalent loopback hosts and tests reject all others.
- [Real AI execution consumes budget] → use the existing configured budgets and one acceptance request; no hidden model calls are added by navigation recovery.
- [A healthy model returns invalid structured planning JSON] → retry the same strict contract once, expose fallback if repair still fails, and never coerce an invalid preset or permission field.
- [Parallel contributors diverge, overlap, or leave uncommitted work] → validate role path boundaries and clean commits, integrate only in a deterministic order, and fail visibly on ambiguity or a conflict outside declared ownership.
- [An Agent worktree contains the delivery but the selected project root does not] → publish only the completed integration branch with a verified fast-forward; ambiguous or conflicting branches fail visibly.
- [A previous acceptance run exists] → create a new timestamped child directory and preserve all prior directories and evidence.
- [An older Docker engine lacks the required default syntax] → the supported release path already requires current Docker Desktop; CI and the local build gate compile the unchanged cache-mount/heredoc instructions.

## Migration Plan

1. Add the helper and focused tests without changing persisted state.
2. Wire the launcher and WebKit controller to the helper/policy.
3. Build v0.3.1, verify signature/version, and replace the existing desktop and `/Applications` copies.
4. Regression-test both launch locations and the native folder/AI flow.
5. Roll back by restoring the prior app bundle or reverting the native-only commit; no database or configuration rollback is needed.

## Open Questions

None. The installed-app fallback is intentionally limited to conventional fixed locations plus the explicit environment override.
