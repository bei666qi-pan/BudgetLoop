## 1. Checkout Discovery

- [x] 1.1 Extract bounded, canonical checkout discovery with explicit-override and sensitive-root validation
- [x] 1.2 Wire launcher startup to fail before Docker mutation when checkout discovery fails
- [x] 1.3 Add dependency-free Swift coverage for candidate order, marker validation, and invalid override behavior

## 2. Native Web Handoff

- [x] 2.1 Use the canonical IPv4 loopback URL while keeping the native bridge restricted to trusted loopback pages
- [x] 2.2 Add WebKit navigation delegate loading, bounded retry, watchdog, and readable retry/exit failure UI
- [x] 2.3 Add focused retry-policy tests and launcher logging assertions where practical

## 3. Build and Regression Verification

- [x] 3.1 Remove the forced remote Dockerfile-frontend lookup and verify a cached local Compose refresh
- [x] 3.2 Run Swift launcher tests, build the macOS bundle, and verify version, signature, and release-version consistency
- [x] 3.3 Install the corrected bundle to the desktop and `/Applications`, then verify both launch locations reach rendered content
- [x] 3.4 Run Web unit/build checks and confirm the native bridge rejects non-loopback origins

## 4. Real AI Desktop Acceptance

- [x] 4.1 Extend and test the reusable `prepare` / `observe` / `verify` driver with unique target directories, redacted evidence, real-model/session assertions, contributor path/commit gates, deterministic integration, and fail-closed fast-forward publication
- [x] 4.2 Add the generated-site Playwright desktop/mobile, accessibility, console, network, and content gate and document the complete local workflow
- [x] 4.3 Add one bounded strict-schema repair attempt for otherwise healthy real-AI task planning and cover success/failure behavior
- [x] 4.4 Use the native picker to select the prepared timestamped directory, submit the fixed marker-bearing app landing-page request, and verify AI-backed planning without local fallback and with contributor plus integration roles
- [x] 4.5 Confirm the reviewed full-access configuration, run every contributor and the integration workflow to `COMPLETED`, publish the verified integration branch, and inspect root artifacts
- [x] 4.6 Record redacted screenshots/log evidence, apply verified Mode 1 frontend design-review corrections if any, and document remaining risk
