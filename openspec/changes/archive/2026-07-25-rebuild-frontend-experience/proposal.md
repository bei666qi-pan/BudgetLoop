## Why

BudgetLoop already exposes the full task lifecycle, but its current frontend presents that lifecycle as several dense, loosely connected technical screens. A coherent product shell, clearer action hierarchy, and stronger budget/safety explanations are needed so operators can create, supervise, and evaluate agent runs quickly on desktop and mobile without losing technical depth.

## What Changes

- Rebuild the task dashboard as an operational home with a persistent product shell, clear primary action, useful task-state summaries, local search/filtering, and trustworthy empty/error/loading states.
- Replace the single dense task form with a guided creation experience that groups task intent, workspace/safety, and budget controls, adds inline validation and budget guidance, and retains the existing create-task API payload.
- Recompose the run detail page as a command center that prioritizes live state, remaining budget, current activity, approvals, timeline, and LLM diagnostics while preserving all existing monitoring data.
- Rework the final report into an answer-first outcome view with acceptance status, resource efficiency, changed files, unresolved issues, recommendations, and authenticated exports.
- Establish a responsive, accessible frontend design system with shared navigation, controls, semantic status treatment, typography, spacing, focus behavior, reduced-motion support, and mobile layouts.
- Add focused frontend tests for navigation, filtering, form validation and submission, run-state presentation, report states, and shared formatting behavior.
- Preserve budget and safety semantics: limits, pressure, reservation, approval, terminal state, and partial-completion information remain explicit and are never hidden behind purely decorative UI.

## Capabilities

### New Capabilities

- `operator-workspace`: Product shell and task dashboard behavior, including primary navigation, task discovery, status filtering, and resilient page states.
- `guided-task-creation`: Guided task setup, inline validation, progressive budget configuration, safety controls, and API-compatible submission behavior.
- `run-command-center`: Live run supervision behavior, including phase/status hierarchy, budget pressure, event timeline, diagnostics, approvals, and responsive information access.
- `outcome-reporting`: Answer-first completion reporting, acceptance evidence, resource totals, file/diff inspection, unresolved work, recommendations, and authenticated exports.
- `frontend-experience-system`: Shared visual, responsive, accessibility, motion, semantic-status, and trustworthy-error requirements across the frontend.

### Modified Capabilities

None. No existing main specifications are present; this change introduces the frontend experience requirements as new capabilities.

## Impact

- Primary code impact: `web/app`, `web/components`, `web/lib`, Tailwind/design tokens, and frontend tests.
- API contract: no endpoint or payload changes are intended. Existing task, run, observation, event, approval, report, and export endpoints remain the source of frontend data.
- Budget and safety: presentation and validation improve, but orchestration rules, budget enforcement, approval policy, credentials, and security boundaries remain backend-owned and unchanged.
- Data and migrations: no PostgreSQL schema or data migration is required.
- Dependencies: reuse the current Next.js, React, Tailwind, and Lucide stack unless a small, justified frontend-only dependency is required.
- Non-goals: no changes to FastAPI contracts, workers, LiteLLM/OpenHands behavior, PostgreSQL ownership, deployment topology, provider credentials, or agent decision policy.
