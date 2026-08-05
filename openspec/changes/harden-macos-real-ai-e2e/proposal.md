## Why

The v0.3.1 macOS launcher can report the local stack as ready while presenting a permanently blank WKWebView, and an app copied into `/Applications` falls back to `/` when it cannot find the adjacent checkout. Both failures block the real desktop path from native folder selection through AI-backed task execution, while giving the operator no trustworthy recovery action.

## What Changes

- Resolve the local BudgetLoop checkout from explicit configuration, bundle-adjacent locations, and a bounded set of safe user checkout locations; fail with the attempted locations instead of silently choosing `/`.
- Make the native web window observe navigation success and failure, retry transient loopback failures within a bounded window, and replace a persistent blank page with a readable recovery state.
- Let cached local image refreshes use Docker Desktop's bundled stable BuildKit frontend instead of forcing a remote Dockerfile-frontend metadata lookup on every launch.
- Add focused launcher tests for repository discovery and web-navigation recovery behavior.
- Rebuild and install the versioned macOS app, then record a real-AI desktop acceptance run using a unique child directory below `/Users/qi/Desktop/测试` and a fixed, marker-bearing Apple-platform app landing-page instruction.
- Add a reusable local `prepare` / `observe` / `verify` driver that fails closed on unhealthy AI, local fallback, non-terminal Agent runs, missing real-model calls, unsafe role-branch integration/publication, or an unusable generated site.
- Preserve the existing web information architecture, AI gateway secret boundary, Docker data services, execution budgets, and folder-authorization confirmation flow.  Role work remains genuinely parallel: each role works in its own Git worktree with a declared path boundary, and a dedicated integration role is solely responsible for assembling the final release branch.

Non-goals: changing the task or AI API contracts, changing model-provider configuration, redesigning the web UI, altering sandbox semantics, restarting or migrating persistent data services, or expanding filesystem permissions beyond the folder explicitly confirmed by the operator.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mac-app-launcher`: require installed-app checkout discovery to fail closed and require the native web surface to recover from or visibly report loopback navigation failures.
- `macos-launcher-loading-experience`: extend the readable launcher failure contract to the native web-loading handoff so a blank page is never treated as ready.

## Impact

- Affected code: `desktop/Sources/LauncherCore.swift`, `desktop/Sources/Windows.swift`, `desktop/Sources/main.swift`, `backend/Dockerfile`, the macOS build/test path, focused launcher tests, and the local E2E driver/docs.
- API and migration impact: none; no request/response contract or database migration changes.
- Budget impact: bounded loopback retries add only local HTTP navigation attempts and no model calls.
- Safety impact: checkout discovery remains bounded to validated directories containing `docker-compose.yml`; AI credentials remain in Keychain/process environment and are never exposed to WebKit JavaScript or test evidence.
- Dependencies: system Swift/AppKit/WebKit only; no new third-party runtime or packaging dependency.
