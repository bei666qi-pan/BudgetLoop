## Why

The conversational start flow currently presents a successful local fallback as a large warning-like block, can fall back even though the configured compatible gateway is healthy, and hides execution-engine choice behind advanced role editing. The home history and planning states also expose more implementation detail than a beginner needs, while lacking basic deletion and reliable keyboard submission.

## What Changes

- Make conversational planning genuinely AI-first through the configured gateway, diagnose and correct compatible-model request failures, and use deterministic local matching only when AI is disabled, unconfigured, unreachable, rejected, timed out, or returns invalid bounded output.
- Keep recommendation provenance truthful but reduce it to a compact secondary status with an optional detail disclosure instead of a prominent fallback card.
- Add a beginner-facing execution-engine selector for OpenHands, Codex, and Gemini CLI. Explicit operator choice always wins; otherwise coding work defaults to Codex and non-coding work defaults to OpenHands. Unavailable engines remain visible with a concise reason and cannot be selected.
- Simplify the home review and history surfaces around the primary next action, moving role, budget, topology, gateway, and safety implementation details behind progressive disclosure without changing their enforcement.
- Add confirmed deletion of standalone task history. Active tasks and tasks owned by an Agent Team cannot be deleted from the recent-history surface; deletion removes the selected terminal standalone task and its database-owned run history without affecting other tasks, containers, PostgreSQL, Valkey, New API, or external workspace files.
- Replace generic spinners in conversational Agent planning/creation with a BudgetLoop logo orbit/morph loading treatment, including an accessible text status and a reduced-motion alternative.
- Make Enter submit the conversational composer, Shift+Enter insert a newline, and IME composition/empty/busy states never submit accidentally.

## Capabilities

### New Capabilities

- `task-history-management`: Confirmed, scoped deletion behavior for terminal standalone task history.

### Modified Capabilities

- `conversational-task-entry`: AI-first draft generation, task-kind-aware engine defaults, manual engine selection, compact provenance, reliable keyboard submission, and branded planning state.
- `execution-engine-registry`: Beginner-facing selection among the installed OpenHands, Codex, and Gemini CLI engines, with explicit-choice precedence and task-kind defaults.
- `operator-workspace`: Reduced default information density, progressive disclosure, history deletion controls, and accessible branded loading feedback.

## Impact

- Backend/API: task-draft classification/default selection, compatible-gateway recommendation payload handling, and an authenticated task deletion endpoint with lifecycle/ownership guards. Existing creation requests remain backward compatible; no data migration is required.
- Frontend: conversational review/composer, execution selection, recent-task actions, compact status disclosure, loading animation, and focused responsive/accessibility states.
- Budget and safety: recommendation calls remain bounded and metered as before; execution budgets, approval policy, folder authorization, managed-runtime credential boundaries, and per-engine preflight stay authoritative. Deletion is explicit, terminal-only, and scoped to one standalone task.
- Dependencies/infrastructure: no new runtime dependency, service, AI router, database, or credential surface. The design reuses the existing pinned OpenHands and Codex engines and Gemini CLI registry entry; it does not change Postgres, Valkey, New API, Docker workspace, or upstream-key persistence behavior.
- Non-goals: deleting Agent Team containers/sessions, deleting active jobs, deleting external files/worktrees/artifacts, changing provider configuration, adding automatic Gemini routing, or redesigning the application information architecture.
