## 1. Product and Visual Foundation

- [x] 1.1 Capture the current route inventory, API-driven states, visible copy, and core operator paths for dashboard, creation, run, and report surfaces
- [x] 1.2 Generate readable coordinated visual concepts for all four primary surfaces and extract the approved design system, copy lock, responsive rules, and icon inventory
- [x] 1.3 Implement global design tokens, typography, focus/reduced-motion behavior, semantic status treatments, and shared page/control primitives
- [x] 1.4 Implement the responsive application shell with route-aware navigation, primary task action, and API health communication
- [x] 1.5 Add focused tests for shared status, navigation, feedback, and responsive-safe component behavior that can be verified in the test environment

## 2. Operator Workspace

- [x] 2.1 Rebuild the task dashboard with lifecycle-oriented hierarchy, task summaries, continuation actions, and trustworthy loading/error/empty states
- [x] 2.2 Add client-side task search, status filters, filter reset, and distinct no-task versus no-match states
- [x] 2.3 Add focused tests for task search/filtering, status presentation, retry behavior, and primary task actions

## 3. Guided Task Creation

- [x] 3.1 Recompose task creation into intent, workspace/safety, budget, and review sections while preserving the existing create-task payload
- [x] 3.2 Add budget presets/guidance, editable advanced limits, inline validation, idempotent submission, and duplicate-submit protection
- [x] 3.3 Preserve form state on failure and add accessible field/error/focus behavior and responsive layouts
- [x] 3.4 Add focused tests for presets, validation, request payload, safety setting, success navigation, and retryable submission failure

## 4. Run Command Center

- [x] 4.1 Rebuild the run summary around live status, current activity, connection state, next action, and terminal-state reporting
- [x] 4.2 Recompose budget/pressure supervision with explicit used, reserved, remaining, limit, and partial-data semantics
- [x] 4.3 Organize timeline, LLM calls, phase budgets, reallocations, and metadata as progressively disclosed but fully accessible diagnostics
- [x] 4.4 Upgrade approval handling for prominent risk context, approve/reject/modify actions, failure recovery, keyboard use, and small screens
- [x] 4.5 Add focused tests for active/terminal status, budget pressure and missing data, diagnostic switching, connection degradation, and approval outcomes

## 5. Outcome Reporting

- [x] 5.1 Rebuild the report around acceptance outcome, achieved work, resource efficiency, unresolved work, and recommended next actions
- [x] 5.2 Preserve changed-file, diff, strategy-switch, issue, suggestion, and optional-data evidence with clear disclosure and empty states
- [x] 5.3 Replace unauthenticated report export links with authenticated downloads and visible failure feedback
- [x] 5.4 Add focused tests for success/partial/exhausted/unavailable reports, optional evidence, and authenticated export outcomes

## 6. Verification and Completion

- [x] 6.1 Run frontend unit tests and production build, fixing all regressions introduced by the change
- [x] 6.2 Verify dashboard-to-create-to-run-to-report workflows in the browser with available API or deterministic mock data
- [x] 6.3 Verify desktop and approximately 390px mobile layouts, keyboard navigation, visible focus, reduced motion, overflow, and trustworthy errors
- [x] 6.4 Compare the latest browser renders against every accepted concept with `view_image`, record at least five fidelity checkpoints, and correct all material mismatches
- [x] 6.5 Run the required Mode 1 frontend design review, apply targeted verified corrections, and recheck affected workflows and breakpoints
- [x] 6.6 Validate the OpenSpec change, mark completed tasks, sync specifications to the main spec set, and archive the completed change
