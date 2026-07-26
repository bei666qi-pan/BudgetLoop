## 1. Pinned Gateway Supply Chain

- [x] 1.1 Add a revision-pinned New API source checkout/bootstrap under `vendor/ai-gateways`, excluding transient build artifacts and verifying the expected release commit.
- [x] 1.2 Record New API repository, release, revision, AGPL boundary, reviewed Star count/date and supported protocol/routing provenance in the vendor manifest, NOTICE and documentation.
- [x] 1.3 Add a pinned New API Compose service, separate logical database/volume, health check and safe defaults; move LiteLLM to an explicit compatibility profile without deleting its configuration.
- [x] 1.4 Update `.env.example` and initialization scripts for New API secrets, URL, console, model alias and AI recommendation flags without introducing working default credentials.

## 2. Gateway Boundary and Status API

- [x] 2.1 Add typed gateway settings and deterministic resolution for `new-api`, `litellm` and `compatible` modes, including legacy LiteLLM environment fallback and bounded timeout validation.
- [x] 2.2 Implement a small HTTP gateway client for URL normalization, redacted `/v1/models` preflight and bounded OpenAI-compatible structured recommendation calls without protocol conversion logic.
- [x] 2.3 Add public gateway provenance/capability models, safe console URL handling and stable sanitized health/failure reason codes.
- [x] 2.4 Add an authenticated `/api/ai-gateway/status` endpoint with short-lived health caching and no secret/raw-exception exposure.
- [x] 2.5 Add focused configuration, client, status endpoint, timeout, authentication, URL and secret-redaction tests.

## 3. AI-first Team Recommendation

- [x] 3.1 Refactor the existing LangGraph recommender into an explicit deterministic local fallback while preserving current ranking results and public generic fallback behavior.
- [x] 3.2 Build a bounded catalog projection and injection-resistant recommendation prompt that requests no hidden reasoning and only known preset identifiers.
- [x] 3.3 Implement strict AI JSON parsing/validation for item count, identifiers, duplicates, confidence, reasons and matched signals, reconstructing all team facts from the local catalog.
- [x] 3.4 Update the recommendation endpoint to attempt AI only when configured, fall back on disabled/unconfigured/timeout/upstream/invalid-output states and return additive source, gateway and sanitized fallback metadata.
- [x] 3.5 Add structured secret-free recommendation observability for source, duration, status class and fallback code without logging goal or model output.
- [x] 3.6 Add tests for successful AI ranking, unknown preset injection, malformed/oversized/partial output, all gateway failure classes, AI-disabled behavior, invalid input before remote call and deterministic local parity.

## 4. Beginner-first Frontend and Documentation

- [x] 4.1 Extend TypeScript API contracts and client helpers for redacted gateway status and recommendation provenance.
- [x] 4.2 Add a compact Agent Team gateway status treatment for AI-ready, local-unconfigured and runtime-fallback states with safe New API console linking.
- [x] 4.3 Update recommendation copy and result provenance so the UI never claims local-only operation after an AI call and never treats local fallback as a blocking error.
- [x] 4.4 Preserve responsive behavior, keyboard semantics, action hierarchy and the existing light-blue visual direction.
- [x] 4.5 Add frontend tests for AI-ready disclosure, console link safety, local fallback, runtime fallback and unchanged creation actions.
- [x] 4.6 Replace LiteLLM-default README guidance with New API setup/migration/protocol/routing instructions while retaining an explicit legacy section and lawful-upstream warning.

## 5. Verification and Delivery

- [x] 5.1 Run focused Ruff, Mypy and gateway/recommendation backend tests, then run the full backend suite and record environment-only skips.
- [x] 5.2 Run frontend Vitest and a clean production build.
- [x] 5.3 Run the application in the in-app Browser and verify AI-ready and local-fallback recommendation paths, status transparency, safe console action, responsive overflow and console health without making a paid model call.
- [x] 5.4 After the runnable UI is complete, run `frontend-design-review` Mode 1, apply only verified targeted findings and recheck the corrected experience.
- [x] 5.5 Strictly validate OpenSpec, update the verification record, sync delta specs and archive the completed change.
