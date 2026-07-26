## Why

Work containers currently require operators to understand roles, per-session goals, budgets, worktree policy and collaboration boundaries before they can start a useful team. That is too much configuration for a first-time user, while mature open-source multi-agent projects already demonstrate reusable supervisor, role-play, workflow-graph and software-company patterns.

## What Changes

- Add a versioned CrewAI-compatible YAML catalog of common Agent Team presets covering software delivery, game development, business growth, product launch, brand content, market research, data analysis and customer support.
- Use LangGraph directly as the state-graph runtime for recommendation and team activation plans, CrewAI's role/goal/task configuration model for declarative teams, and MetaGPT's SOP-style stages for specialist handoffs.
- Add a bundled LangGraph recommendation graph that interprets the operator's stated goal and optional industry, pace and risk preferences, returns ranked presets with concise reasons and never sends goal text to an external recommender.
- Add an explicit one-click creation operation that atomically creates the work container and all preset sessions with safe workspace, approval, budget, role-goal, private-context and skill defaults; the operator may either enqueue the sessions immediately or create them paused for review.
- Replace the manual-only container creation screen with a beginner-first guided flow that supports smart recommendation, preset browsing, transparent source attribution, role/budget editing and a clear no-third-party-configuration promise.
- Preserve advanced manual creation as an available path and preserve all existing task, run, container, session, Handoff and worktree contracts.
- Establish BudgetLoop as the multi-Agent control plane and add a versioned execution-engine registry for interchangeable OpenHands, Codex, Gemini CLI and OpenCode workers, backed by locally downloaded, license-audited upstream source snapshots.
- Let presets and operators select an execution engine without changing BudgetLoop's TaskRun, budget, approval, workspace, event or Handoff contracts; OpenHands remains the compatibility default.
- **Non-goals:** delegating PostgreSQL authority, budgets or approvals to an execution engine; silently sharing provider credentials between engines; modifying upstream engine source; enabling unrestricted agent-to-agent communication; auto-merging worktrees; provisioning new model-provider credentials or infrastructure.

## Capabilities

### New Capabilities

- `agent-team-presets`: CrewAI-compatible versioned preset catalog, LangGraph-backed goal-to-team recommendations and activation plans, high-star source provenance, safe overrides and zero-configuration instantiation.
- `execution-engine-registry`: High-star, license-audited OpenHands/Codex/Gemini CLI/OpenCode source snapshots, typed capabilities and a stable adapter boundary owned by the BudgetLoop control plane.

### Modified Capabilities

- `work-container-lifecycle`: Add explicit preset provenance and atomic container-plus-initial-session creation while retaining the existing empty-container creation behavior.
- `operator-workspace`: Make Agent Team creation beginner-first with recommendation, browsing, preview, edit and start-later paths.

## Impact

- Backend: new YAML preset loader, LangGraph recommendation/topology adapters, execution-engine registry and authenticated preset list, recommend and instantiate endpoints; reuse existing task/run/budget/session creation primitives and queue dispatch.
- Persistence: additive nullable preset provenance fields on `work_containers` with an Alembic migration and reversible downgrade; no existing row requires backfill.
- Frontend: new typed preset/engine contracts, recommendation/presentation helpers and a redesigned `/containers/new` route with engine choice; container detail and legacy routes remain compatible.
- API contract: additive endpoints and optional container response fields; bounded request text, override counts and budgets are validated server-side.
- Budget and safety: every role receives bounded starter budgets, approvals remain enabled, explicit Handoff isolation remains unchanged, and immediate start is an explicit operator action.
- Dependencies and source: add pinned-compatible `langgraph` and `PyYAML` packages plus shallow, revision-pinned upstream source checkouts for OpenHands core, Codex, Gemini CLI and OpenCode. CrewAI/MetaGPT configurations remain declarative pattern sources; engines keep separate credential requirements and never become state authorities.
