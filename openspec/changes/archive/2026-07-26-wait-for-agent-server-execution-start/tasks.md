## 1. Execution synchronization

- [x] 1.1 Extend the OpenHands wait contract to distinguish pre-start idle from completed idle with a bounded startup timeout and usage evidence fallback.
- [x] 1.2 Require start evidence from the server-transport orchestrator path while preserving CLI behavior and existing reservation release on errors.
- [x] 1.3 Use the official two-stage OpenHands server lifecycle (`send run=false`, explicit `/run`) while preserving direct CLI execution and inbox delivery semantics.
- [x] 1.4 Treat usage-free pre-start `finished` as ambiguous until execution evidence or startup timeout, while preserving unambiguous terminal errors.
- [x] 1.5 Require an actual token-usage record for usage-backed instant completion instead of accepting ancillary latency/cost placeholders.
- [x] 1.6 Qualify managed OpenHands models with LiteLLM's `openai/` provider at the conversation boundary and fail fast on `error`/`stuck` execution states.
- [x] 1.7 Treat OpenHands `/run` 409 already-running responses as idempotent scheduling success without weakening other HTTP conflict handling.
- [x] 1.8 Normalize response-scoped OpenHands cost/latency objects by response ID and protect observation settlement with rollback plus reservation release.
- [x] 1.9 Configure server conversations with OpenHands' official terminal, file-editor, and task-tracker tools.

## 2. Verification

- [x] 2.1 Add focused tests for idle-before-running, running-to-idle, instant terminal completion, usage-backed idle completion, and never-started timeout.
- [x] 2.2 Run focused backend tests, Ruff, and strict OpenSpec validation.
- [x] 2.3 Add transport-specific orchestration tests, including explicit-run failure leaving collaboration messages queued, and rerun focused verification.
- [x] 2.4 Add focused stale-finished synchronization tests and rerun verification.
- [x] 2.5 Add a regression test proving latency/cost-only metrics do not establish execution completion.
- [x] 2.6 Add focused tests for provider qualification and terminal execution error reservation release.
- [x] 2.7 Add focused client coverage for endpoint-specific 409 handling and rerun verification.
- [x] 2.8 Add metric-object and observation-failure reservation regression tests and rerun verification.
- [x] 2.9 Add focused request-body coverage for the official OpenHands coding tool descriptors and rerun verification.
- [x] 2.10 Rebuild the stateless worker and repeat the real full-access Sangfor task without exposing credentials.
