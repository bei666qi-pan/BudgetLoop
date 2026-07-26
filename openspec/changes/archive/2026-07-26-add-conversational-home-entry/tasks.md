## 1. Permission and contract foundation

- [x] 1.1 Reconcile this change with the remaining `mac-launcher-folder-access` tasks and record the exact shared folder-policy and native-picker interfaces to reuse.
- [x] 1.2 Extract canonical `project_dir` and `folder_access` validation from the single-task API into one shared backend policy module without changing existing request behavior.
- [x] 1.3 Add focused backend tests for isolated defaults, canonical paths, sensitive-root rejection, full-access path requirements, and unchanged legacy single-task payloads.
- [x] 1.4 Define versioned backend/frontend `TaskSetupDraft`, refinement request, provenance, clarification, and workspace-access contracts with strict size and key bounds.

## 2. Stateless conversational draft backend

- [x] 2.1 Implement bounded AI draft messages and strict structured-output parsing that accepts only editable intent text and trusted preset identifiers without requesting hidden reasoning.
- [x] 2.2 Compose catalog-owned roles, tasks, budgets, activation topology, approval defaults, and engine facts into a complete server-validated draft.
- [x] 2.3 Implement deterministic local fallback draft generation using the existing LangGraph preset recommender and catalog task outputs.
- [x] 2.4 Add `POST /api/task-drafts` for initial and follow-up drafting with request replacement safety, at most two necessary clarifications, and no database or queue writes.
- [x] 2.5 Add sanitized draft observability for source, model alias, latency, status class, fallback code, selected preset ID, and validation outcome while excluding prompts, paths, credentials, and hidden reasoning.
- [x] 2.6 Add focused backend tests for valid AI output, malformed/unknown/oversized output, AI outage fallback, input bounds, follow-up bounds, public provenance, and zero persistence/dispatch side effects.

## 3. Folder-aware preset team creation

- [x] 3.1 Add backward-compatible `folder_access`, `project_dir`, and `full_access_acknowledged` fields to preset team creation and require a worktree policy for confirmed writable teams.
- [x] 3.2 Propagate the confirmed folder policy/path into every created run and the applied snapshot in the same team-creation transaction.
- [x] 3.3 Preserve isolated defaults and idempotent retry behavior for existing clients that omit all new fields.
- [x] 3.4 Harden worker provisioning so every full-access team session uses a unique server-generated worktree and contradictory persisted policy fails closed.
- [x] 3.5 Add API and worker tests for isolated teams, full-access teams, acknowledgement clearing/validation, unsafe combinations, atomic rollback, idempotent retry, mount failure, Git/worktree failure, and concurrent unique worktree identifiers.

## 4. Conversational home and confirmation UI

- [x] 4.1 Add shared frontend draft/refinement state, cancellation or sequence guards, request error mapping, retained idempotency keys, and catalog-derived aggregate helpers.
- [x] 4.2 Build the semantic home composer with example prompts, keyboard submission guidance, announced planning/needs-input/error states, and recoverable follow-up input.
- [x] 4.3 Build one editable setup review card for outcome, team, acceptance criteria, hard limits, AI/local provenance, engine readiness, approval, and final creation status.
- [x] 4.4 Build the separate folder-access control using isolated defaults, the macOS picker bridge, advanced browser path entry, canonical path display, `.git` warning, acknowledgement reset, and worktree explanation.
- [x] 4.5 Wire “确认并启动” to the extended idempotent preset-creation endpoint and preserve the draft/permission state on recoverable confirmation errors.
- [x] 4.6 Recompose `/` so conversational intake is primary and the existing attention summary, search, filters, task rows, and continuation actions remain directly usable below it.
- [x] 4.7 Reuse existing preset, role, budget, engine, and advanced configuration components rather than duplicating their validation or catalog logic.

## 5. Automated and visual verification

- [x] 5.1 Add Vitest coverage for idle, planning, stale-response suppression, needs-input, AI/local ready states, edits, advanced disclosure, permission isolation, acknowledgement reset, confirmation retry, and created navigation.
- [x] 5.2 Add frontend tests that retain task attention/search/filter behavior with a draft present and verify no fabricated success, path authorization, budget, or recommendation state.
- [x] 5.3 Verify semantic labels, focus order, `aria-live` feedback, reduced motion, keyboard-only confirmation, and approximately 390px responsive behavior with targeted automated checks.
- [x] 5.4 Run focused backend tests, the full relevant backend suite, frontend tests, and `npm run build`; record commands and any environment-limited checks.
- [x] 5.5 Run the complete UI locally and capture/inspect desktop and mobile states for empty, planning, ready-isolated, ready-full-access, error, and recent-work scenarios.
- [x] 5.6 After the UI is complete and runnable, run `frontend-design-review` in Mode 1 only for action hierarchy, design-token compliance, accessibility, responsive behavior, and trustworthy feedback; apply targeted verified fixes and recheck.
- [x] 5.7 Perform native macOS end-to-end checks proving that draft preview has no side effects, isolated confirmation does not modify a host folder, and acknowledged full-access confirmation creates unique worktrees and visible metering.

## 6. Documentation and completion

- [x] 6.1 Update API and user-facing setup documentation for the draft endpoint, additive team fields, recommendation provenance, permission boundary, native picker, fallback behavior, and advanced routes.
- [x] 6.2 Add a verification record mapping each OpenSpec scenario to automated or manual evidence and note the Codex/OpenHands source lineage used by the implementation.
- [x] 6.3 Re-run `openspec validate add-conversational-home-entry --strict`, resolve all findings, then sync the delta specs and archive the completed change through the project OpenSpec workflow.
