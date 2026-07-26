## Why

BudgetLoop already has capable task forms, Agent Team recommendations, and Codex-derived folder controls, but a first-time user must discover separate routes and understand implementation concepts before work can begin. The home page should instead accept a plain-language goal, turn it into one trustworthy reviewable setup, and require only an explicit confirmation before creating the recommended team.

## What Changes

- Replace the home page's task-dashboard-first hierarchy with a persistent conversational intake composer followed by recent work, so both empty and returning users can start by describing an outcome in their own words.
- Add a stateless, bounded task-draft API that turns the description into a validated title, goal, acceptance criteria, trusted Agent Team preset, role/task details, starter budgets, approval setting, and explainable recommendation provenance; use the existing deterministic local recommendation path whenever AI is unavailable or invalid.
- Present the result as one editable confirmation card rather than a mandatory multi-step form. Nothing is persisted or dispatched until the user confirms, and retries use the existing idempotent team-creation contract.
- Integrate the macOS folder picker and existing Codex-derived `isolated` / `full_access` modes into the confirmation card. Isolation remains the default; AI cannot select or escalate host-folder access; full access requires an operator-selected absolute path and an explicit high-risk acknowledgement.
- Extend preset-based Agent Team creation to propagate the confirmed folder policy and project path into every created run, with server-side validation, auditable public snapshot data, fail-closed provisioning, and worktree isolation for concurrent agents using a writable host project.
- Preserve the current task dashboard, detailed task form, preset browser, manual container path, run monitoring, budget controls, and approval system as secondary or advanced paths.
- Non-goals: replacing the AI gateway, introducing a new orchestration framework or sandbox, adding cloud file storage, allowing model-selected permissions, changing provider credentials, or redesigning the run/report experience.

## Capabilities

### New Capabilities

- `conversational-task-entry`: Plain-language home-page intake, validated draft generation, progressive clarification, confirmation, retry, and no-side-effect guarantees.

### Modified Capabilities

- `operator-workspace`: Make conversation the primary home action while retaining recent task discovery and advanced creation routes.
- `guided-task-creation`: Allow a generated setup draft to populate the existing safe creation contract and remain editable before submission.
- `agent-team-presets`: Generate and instantiate a complete recommended team draft with explainable AI/local provenance and confirmed folder settings.
- `isolated-session-workspaces`: Apply selected-folder access and per-session worktrees safely to preset-created teams without silent permission fallback.
- `frontend-experience-system`: Add accessible conversational, draft-review, permission-summary, and responsive confirmation states using the existing design system.

## Impact

- Frontend: `web/app/page.tsx`, shared home-intake/review components, team/task draft types, API helpers, macOS picker bridge, navigation copy, and Vitest coverage.
- Backend/API: one additive draft endpoint plus additive folder fields on preset team creation; existing recommendation and creation endpoints remain compatible. Structured AI output is bounded and catalog-validated; no provider keys reach the browser.
- Worker/security: reuse the folder validation and `WorkspaceManager` policy/enforcer path from `mac-launcher-folder-access`; no new sandbox mechanism. Full-access team runs fail closed if the selected path or worktree cannot be honored.
- Persistence/migration: no draft table and no required schema migration; confirmed public folder-policy metadata is stored in existing run `model_config` and preset snapshot JSONB fields. Budgets and approval defaults remain hard server-enforced limits.
- Dependencies/infrastructure: no new external runtime dependency or service. The design will cite the vendored, pinned Codex/OpenHands and existing high-star preset research rather than adding another framework.
